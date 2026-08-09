#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define OVERLAYFS_SUPER_MAGIC 0x794C764F
#define ARDA_MAX_VERITY_DIGEST_SIZE 64

#define ARDA_MODE_AUDIT 0
#define ARDA_MODE_LEGACY_INODE 1
#define ARDA_MODE_FSVERITY_STRICT 2

struct arda_identity {
    unsigned long inode;
    unsigned int dev;
};

/*
 * Sovereign executable identity.  The algorithm is part of the identity:
 * digest bytes are not meaningful without it.  The layout intentionally
 * matches a fixed-size struct fsverity_digest buffer so
 * bpf_get_fsverity_digest() can fill it directly.
 */
struct arda_verity_identity {
    __u16 digest_algorithm;
    __u16 digest_size;
    __u8 digest[ARDA_MAX_VERITY_DIGEST_SIZE];
};

/*
 * A content identity is authorized only inside the appraised cgroup and only
 * for its currently active generation.  Staged generations are unreachable
 * until the single active-generation map value is flipped.
 */
struct arda_verity_generation_identity {
    __u64 cgroup_id;
    __u64 generation;
    struct arda_verity_identity identity;
};

// Exec allowlist: keyed by {inode, dev}, value 1 = harmonic (permitted).
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, struct arda_identity);
    __type(value, __u32);
} arda_harmony_map SEC(".maps");

/* Legacy non-generation map retained for audit/compatibility inspection. */
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, struct arda_verity_identity);
    __type(value, __u32);
} arda_verity_harmony_map SEC(".maps");

/* Production content allowlist: cgroup + generation + fs-verity identity. */
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 65536);
    __type(key, struct arda_verity_generation_identity);
    __type(value, __u32);
} arda_verity_generation_map SEC(".maps");

/* Per-cgroup activation pointer. A missing/zero generation fails closed. */
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 4096);
    __type(key, __u64);
    __type(value, __u64);
} arda_active_generation_map SEC(".maps");

// Global enforcement mode: 0=audit, 1=legacy inode compatibility,
// 2=strict fs-verity digest enforcement.
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u32);
} arda_state_map SEC(".maps");

// Cumulative denial counter for telemetry/evidence. Index 0 = total vetoes.
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} arda_deny_count SEC(".maps");

// Network veto map: keyed by PID (u32), value 1 = deny all outbound connects.
// Populated by Tulkas on CONTAIN/PURGE/EXILE postures for fallen nodes.
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 4096);
    __type(key, __u32);
    __type(value, __u32);
} arda_network_deny_map SEC(".maps");

// ── Exec gate (bprm_check_security) ─────────────────────────────────────────

SEC("lsm/bprm_check_security")
int BPF_PROG(arda_sovereign_ignition, struct linux_binprm *bprm, int ret)
{
    if (ret != 0) return ret;

    struct arda_identity key = {0};
    key.inode = bprm->file->f_inode->i_ino;
    key.dev = bprm->file->f_inode->i_sb->s_dev;

    __u32 index = 0;
    __u32 *state = bpf_map_lookup_elem(&arda_state_map, &index);

    // AUDIT mode (default) — never block, even if unlisted.
    // Prevents lockout when seeding is incomplete.
    if (!state || *state == 0) {
        return 0;
    }

    __u32 *harmonic = NULL;

    if (*state == ARDA_MODE_FSVERITY_STRICT) {
        struct arda_verity_identity verity = {0};
        struct arda_verity_generation_identity generation_key = {0};
        struct bpf_dynptr digest_ptr;

        if (bpf_dynptr_from_mem(&verity, sizeof(verity), 0, &digest_ptr) != 0) {
            goto veto;
        }
        if (bpf_get_fsverity_digest(bprm->file, &digest_ptr) != 0) {
            /* A non-verity executable has no sovereign content identity. */
            goto veto;
        }
        if (verity.digest_size == 0 ||
            verity.digest_size > ARDA_MAX_VERITY_DIGEST_SIZE) {
            goto veto;
        }
        generation_key.cgroup_id = bpf_get_current_cgroup_id();
        __u64 *active_generation = bpf_map_lookup_elem(
            &arda_active_generation_map, &generation_key.cgroup_id
        );
        if (!active_generation || *active_generation == 0) {
            goto veto;
        }
        generation_key.generation = *active_generation;
        __builtin_memcpy(&generation_key.identity, &verity, sizeof(verity));
        harmonic = bpf_map_lookup_elem(&arda_verity_generation_map, &generation_key);
    } else if (*state == ARDA_MODE_LEGACY_INODE) {
        harmonic = bpf_map_lookup_elem(&arda_harmony_map, &key);
    } else {
        /* Unknown modes fail closed instead of accidentally becoming audit. */
        goto veto;
    }

    if (harmonic && *harmonic != 0) {
        return 0;
    }

veto:
    {
        __u32 cidx = 0;
        __u64 *cnt = bpf_map_lookup_elem(&arda_deny_count, &cidx);
        if (cnt) {
            __sync_fetch_and_add(cnt, 1);
        }
        bpf_printk("ARDA_VETO: execve denied ino=%lu dev=%u\n", key.inode, key.dev);
        return -1; /* -EPERM */
    }
}

// ── Network gate (socket_connect) ───────────────────────────────────────────
// Blocks outbound connect() for any PID explicitly marked fallen by Tulkas.
// Only active when arda_network_deny_map has an entry for the calling PID.
// The exec gate guards what runs; this guards where fallen processes can reach.

SEC("lsm/socket_connect")
int BPF_PROG(arda_network_veto, struct socket *sock, struct sockaddr *address, int addrlen)
{
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    __u32 *deny = bpf_map_lookup_elem(&arda_network_deny_map, &pid);
    if (deny && *deny) {
        __u32 cidx = 0;
        __u64 *cnt = bpf_map_lookup_elem(&arda_deny_count, &cidx);
        if (cnt) {
            __sync_fetch_and_add(cnt, 1);
        }
        bpf_printk("ARDA_NET_VETO: connect denied for PID %u\n", pid);
        return -1; /* -EPERM */
    }
    return 0;
}

char _license[] SEC("license") = "GPL";
