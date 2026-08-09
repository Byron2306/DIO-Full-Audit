/*
 * ARDA LSM Loader — Creates a BPF link for the LSM program.
 * bpftool can load LSM programs but on some kernels doesn't auto-attach.
 * This loader uses the BPF syscall directly to create a BPF_LINK.
 *
 * Usage: arda_lsm_loader <path_to_bpf_object.o>
 * The program stays alive while the link is active. Kill it to detach.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <sys/stat.h>
#include <dirent.h>
#include <bpf/libbpf.h>
#include <bpf/bpf.h>

static volatile int running = 1;
static struct bpf_object *obj = NULL;
static struct bpf_link  *bpf_lnk = NULL;
static struct bpf_link  *net_lnk = NULL;
static int state_map_fd = -1;
static int harmony_map_fd = -1;
static int verity_harmony_map_fd = -1;
static int verity_generation_map_fd = -1;
static int active_generation_map_fd = -1;
static int deny_count_map_fd = -1;
static int network_deny_map_fd = -1;
static int seeded_total = 0;

struct arda_identity {
    unsigned long inode;
    unsigned int dev;
};

#define ARDA_MAX_VERITY_DIGEST_SIZE 64
#define ARDA_MODE_AUDIT 0
#define ARDA_MODE_LEGACY_INODE 1
#define ARDA_MODE_FSVERITY_STRICT 2

struct arda_verity_identity {
    __u16 digest_algorithm;
    __u16 digest_size;
    __u8 digest[ARDA_MAX_VERITY_DIGEST_SIZE];
};

struct arda_verity_generation_identity {
    __u64 cgroup_id;
    __u64 generation;
    struct arda_verity_identity identity;
};

static __u64 verity_cgroup_id = 0;
static __u64 verity_generation = 1;

void cleanup(int sig) {
    (void)sig;
    running = 0;
}

static void set_enforcement(int enabled) {
    if (state_map_fd < 0) return;
    __u32 key = 0;
    __u32 val = enabled ? 1 : 0;
    (void)bpf_map_update_elem(state_map_fd, &key, &val, BPF_ANY);
}

static void set_enforcement_mode(__u32 mode) {
    if (state_map_fd < 0) return;
    __u32 key = 0;
    (void)bpf_map_update_elem(state_map_fd, &key, &mode, BPF_ANY);
}

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/* Format: <fs-verity-algorithm-id>:<hex-digest>, e.g. 1:abcd... */
static int seed_verity_digest(const char *spec) {
    if (verity_generation_map_fd < 0 || !spec || verity_cgroup_id == 0 || verity_generation == 0) return 0;
    char *end = NULL;
    unsigned long algorithm = strtoul(spec, &end, 10);
    if (!end || *end != ':' || algorithm > 0xffff) return 0;
    const char *hex = end + 1;
    size_t hex_len = strlen(hex);
    if (hex_len == 0 || (hex_len & 1) != 0 ||
        hex_len / 2 > ARDA_MAX_VERITY_DIGEST_SIZE) return 0;

    struct arda_verity_generation_identity key = {0};
    key.cgroup_id = verity_cgroup_id;
    key.generation = verity_generation;
    key.identity.digest_algorithm = (__u16)algorithm;
    key.identity.digest_size = (__u16)(hex_len / 2);
    for (size_t i = 0; i < key.identity.digest_size; i++) {
        int high = hex_nibble(hex[i * 2]);
        int low = hex_nibble(hex[i * 2 + 1]);
        if (high < 0 || low < 0) return 0;
        key.identity.digest[i] = (__u8)((high << 4) | low);
    }
    __u32 value = 1;
    if (bpf_map_update_elem(verity_generation_map_fd, &key, &value, BPF_NOEXIST) != 0) {
        if (errno == EEXIST) return 1;
        fprintf(stderr, "VERITY_SEED: map update failed: %s\n", strerror(errno));
        return 0;
    }
    return 1;
}

static void set_network_deny_pid(int pid, int deny) {
    if (network_deny_map_fd < 0) return;
    __u32 key = (__u32)pid;
    __u32 val = deny ? 1 : 0;
    (void)bpf_map_update_elem(network_deny_map_fd, &key, &val, BPF_ANY);
}

static int is_executable_file_mode(mode_t mode) {
    if (!S_ISREG(mode)) return 0;
    return (mode & (S_IXUSR | S_IXGRP | S_IXOTH)) != 0;
}

static int seed_harmony_path(const char *path) {
    if (harmony_map_fd < 0 || !path || !*path) return 0;
    struct stat st;
    if (stat(path, &st) != 0) {
        fprintf(stderr, "SEED: stat failed for %s: %s\n", path, strerror(errno));
        return 0;
    }
    struct arda_identity key = {0};
    key.inode = (unsigned long)st.st_ino;
    key.dev = (unsigned int)st.st_dev;
    __u32 val = 1;
    if (bpf_map_update_elem(harmony_map_fd, &key, &val, BPF_ANY) != 0) {
        fprintf(stderr, "SEED: map update failed for %s (ino=%lu dev=%u): %s\n", path, key.inode, key.dev, strerror(errno));
        return 0;
    }
    printf("SEED_OK: %s ino=%lu dev=%u\n", path, key.inode, key.dev);
    fflush(stdout);
    return 1;
}

static void seed_exec_dir(const char *dir_path, int recursive, int max_entries, int *seeded) {
    if (harmony_map_fd < 0 || !dir_path || !*dir_path) return;
    if (*seeded >= max_entries) return;

    DIR *dir = opendir(dir_path);
    if (!dir) {
        fprintf(stderr, "SEED_DIR: cannot open %s: %s\n", dir_path, strerror(errno));
        return;
    }

    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL) {
        if (*seeded >= max_entries) break;
        if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0) continue;

        char full[4096];
        int n = snprintf(full, sizeof(full), "%s/%s", dir_path, ent->d_name);
        if (n <= 0 || (size_t)n >= sizeof(full)) continue;

        struct stat lst;
        if (lstat(full, &lst) != 0) continue;

        // Recurse into real directories only (not symlinks-to-dirs, to avoid loops).
        if (S_ISDIR(lst.st_mode) && recursive) {
            seed_exec_dir(full, recursive, max_entries, seeded);
            continue;
        }

        // Follow symlinks for the executability check so that alternatives
        // (python3 -> python3.12, java -> /etc/alternatives/java, etc.) are seeded.
        struct stat st;
        if (stat(full, &st) != 0) continue;
        if (!is_executable_file_mode(st.st_mode)) continue;
        if (seed_harmony_path(full)) (*seeded)++;
    }

    closedir(dir);
}

// Seed all executables currently running on the host by reading /host/proc/*/exe.
// This is the primary anti-lockout measure before enabling permanent enforcement:
// any process already running will have its binary in the harmony map.
static void seed_running_procs(int max_entries, int *seeded) {
    // Try host proc first (container with -v /:/host), then fall back to /proc.
    const char *proc_roots[] = { "/host/proc", "/proc", NULL };
    for (int r = 0; proc_roots[r]; r++) {
        DIR *proc = opendir(proc_roots[r]);
        if (!proc) continue;
        struct dirent *ent;
        while ((ent = readdir(proc)) != NULL && *seeded < max_entries) {
            char *end;
            long pid = strtol(ent->d_name, &end, 10);
            if (*end != '\0' || pid <= 0) continue;

            char exe_link[128];
            snprintf(exe_link, sizeof(exe_link), "%s/%ld/exe", proc_roots[r], pid);

            char target[4096];
            ssize_t n = readlink(exe_link, target, sizeof(target) - 1);
            if (n <= 0) continue;
            target[n] = '\0';

            // Strip " (deleted)" suffix — process may have replaced its binary.
            char *del = strstr(target, " (deleted)");
            if (del) *del = '\0';

            // For /host/proc the target is a host-absolute path; prepend /host.
            char host_path[4096];
            if (proc_roots[r][0] == '/' && proc_roots[r][1] == 'h') {
                if (snprintf(host_path, sizeof(host_path), "/host%s", target) >= (int)sizeof(host_path))
                    continue;
            } else {
                if (snprintf(host_path, sizeof(host_path), "%s", target) >= (int)sizeof(host_path))
                    continue;
            }

            if (seed_harmony_path(host_path)) (*seeded)++;
        }
        closedir(proc);
        break; // Only use the first proc root that opens successfully.
    }
}

static __u64 read_deny_count(void) {
    if (deny_count_map_fd < 0) return 0;
    __u32 key = 0;
    __u64 val = 0;
    if (bpf_map_lookup_elem(deny_count_map_fd, &key, &val) != 0) return 0;
    return val;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <bpf_object.o> [--permanent] [--audit | --enforce] "
                "[--failsafe-seconds N] [--delay-seconds N] [--enforce-seconds N] "
                "[--seed-path PATH]... [--seed-verity-digest ALG:HEX]... [--verity-enforce] "
                "[--verity-cgroup-id ID] [--verity-generation N] "
                "[--seed-exec-dir DIR]... "
                "[--seed-exec-dir-recursive DIR]... [--seed-running-procs] "
                "[--max-seed N] [--min-seed N] [--confirm-permanent] [--no-failsafe] "
                "[--deny-pid PID] [--allow-pid PID] "
                "[--pin /sys/fs/bpf/arda_lsm]\n", argv[0]);
        return 1;
    }

    const char *obj_path = argv[1];
    const char *pin_path = NULL;
    const char *pin_root = NULL;
    int delay_seconds = 0;
    int enforce_seconds = 0;
    int force_enforce = 0;
    int force_audit = 0;
    int force_verity_enforce = 0;
    int force_permanent = 0;
    int confirm_permanent = 0;
    int no_failsafe = 0;
    int seed_running = 0;
    int failsafe_seconds = 120;
    int max_seed = 8000;
    int min_seed_for_enforce = 1;
    const char *seed_paths[256];
    int seed_count = 0;
    const char *verity_digests[1024];
    int verity_digest_count = 0;
    const char *seed_dirs[128];
    int seed_dir_count = 0;
    const char *seed_dirs_recursive[128];
    int seed_dir_recursive_count = 0;
    // PIDs to mark denied/allowed in network map at startup
    int deny_pids[256]; int deny_pid_count = 0;
    int allow_pids[256]; int allow_pid_count = 0;

    for (int i = 2; i < argc; i++) {
        const char *arg = argv[i];
        const char *next = (i + 1 < argc) ? argv[i + 1] : NULL;

        if (strcmp(arg, "--audit") == 0) { force_audit = 1; continue; }
        if (strcmp(arg, "--enforce") == 0) { force_enforce = 1; continue; }
        if (strcmp(arg, "--verity-enforce") == 0) { force_verity_enforce = 1; continue; }
        if (strcmp(arg, "--confirm-permanent") == 0) { confirm_permanent = 1; continue; }
        if (strcmp(arg, "--no-failsafe") == 0) { no_failsafe = 1; continue; }
        if (strcmp(arg, "--seed-running-procs") == 0) { seed_running = 1; continue; }

        // --permanent is intentionally not enough by itself. It must be paired
        // with --confirm-permanent, and it still gets a failsafe unless
        // --no-failsafe is also passed.
        if (strcmp(arg, "--permanent") == 0) {
            force_permanent = 1;
            force_enforce = 1;
            if (failsafe_seconds <= 0) failsafe_seconds = 300;
            seed_running = 1; // always pre-seed running procs in permanent mode
            continue;
        }

        if (!next) break;

        if (strcmp(arg, "--pin") == 0) { pin_path = next; i++; continue; }
        if (strcmp(arg, "--pin-root") == 0) { pin_root = next; i++; continue; }
        if (strcmp(arg, "--max-seed") == 0) { max_seed = atoi(next); i++; continue; }
        if (strcmp(arg, "--min-seed") == 0) { min_seed_for_enforce = atoi(next); i++; continue; }
        if (strcmp(arg, "--delay-seconds") == 0) { delay_seconds = atoi(next); i++; continue; }
        if (strcmp(arg, "--enforce-seconds") == 0) { enforce_seconds = atoi(next); i++; continue; }
        if (strcmp(arg, "--failsafe-seconds") == 0) { failsafe_seconds = atoi(next); i++; continue; }
        if (strcmp(arg, "--verity-cgroup-id") == 0) { verity_cgroup_id = strtoull(next, NULL, 10); i++; continue; }
        if (strcmp(arg, "--verity-generation") == 0) { verity_generation = strtoull(next, NULL, 10); i++; continue; }
        if (strcmp(arg, "--seed-path") == 0) {
            if (seed_count < 256) seed_paths[seed_count++] = next;
            i++; continue;
        }
        if (strcmp(arg, "--seed-verity-digest") == 0) {
            if (verity_digest_count < 1024) verity_digests[verity_digest_count++] = next;
            i++; continue;
        }
        if (strcmp(arg, "--seed-exec-dir") == 0) {
            if (seed_dir_count < 128) seed_dirs[seed_dir_count++] = next;
            i++; continue;
        }
        if (strcmp(arg, "--seed-exec-dir-recursive") == 0) {
            if (seed_dir_recursive_count < 128) seed_dirs_recursive[seed_dir_recursive_count++] = next;
            i++; continue;
        }
        if (strcmp(arg, "--deny-pid") == 0) {
            if (deny_pid_count < 256) deny_pids[deny_pid_count++] = atoi(next);
            i++; continue;
        }
        if (strcmp(arg, "--allow-pid") == 0) {
            if (allow_pid_count < 256) allow_pids[allow_pid_count++] = atoi(next);
            i++; continue;
        }
    }

    signal(SIGINT, cleanup);
    signal(SIGTERM, cleanup);

    /* Open the BPF object */
    obj = bpf_object__open(obj_path);
    if (!obj) {
        fprintf(stderr, "ERROR: Failed to open BPF object: %s\n", obj_path);
        return 1;
    }

    /* Load (verify) the BPF programs */
    if (bpf_object__load(obj)) {
        fprintf(stderr, "ERROR: Failed to load BPF object: %s\n", strerror(errno));
        bpf_object__close(obj);
        return 1;
    }
    if (pin_root) {
        if (mkdir(pin_root, 0700) != 0 && errno != EEXIST) {
            fprintf(stderr, "ERROR: cannot create BPF map pin root %s: %s\n", pin_root, strerror(errno));
            bpf_object__close(obj);
            return 1;
        }
        if (bpf_object__pin_maps(obj, pin_root) != 0) {
            fprintf(stderr, "ERROR: cannot pin BPF maps under %s: %s\n", pin_root, strerror(errno));
            bpf_object__close(obj);
            return 1;
        }
        printf("MAP_PIN_ROOT=%s\n", pin_root);
    }
    printf("BPF object loaded successfully.\n");

    /* Find the LSM program */
    struct bpf_program *prog = bpf_object__find_program_by_name(obj, "arda_sovereign_ignition");
    if (!prog) {
        fprintf(stderr, "ERROR: Program 'arda_sovereign_ignition' not found in object.\n");
        bpf_object__close(obj);
        return 1;
    }
    printf("Found LSM program: arda_sovereign_ignition\n");

    /* Attach as LSM — this creates a bpf_link */
    bpf_lnk = bpf_program__attach(prog);
    if (!bpf_lnk || libbpf_get_error(bpf_lnk)) {
        fprintf(stderr, "ERROR: Failed to attach LSM: %s\n", strerror(errno));
        bpf_object__close(obj);
        return 1;
    }
    printf("LSM hook ATTACHED — arda_sovereign_ignition is active (default=AUDIT unless enforcement is enabled).\n");

    /* Pin the link if requested */
    if (pin_path) {
        if (bpf_link__pin(bpf_lnk, pin_path)) {
            fprintf(stderr, "WARNING: Failed to pin link to %s: %s\n", pin_path, strerror(errno));
        } else {
            printf("Link pinned to %s\n", pin_path);
        }
    }

    /* Attach the network veto program (arda_network_veto) if present */
    struct bpf_program *net_prog = bpf_object__find_program_by_name(obj, "arda_network_veto");
    if (net_prog) {
        net_lnk = bpf_program__attach(net_prog);
        if (!net_lnk || libbpf_get_error(net_lnk)) {
            fprintf(stderr, "WARNING: Failed to attach network LSM hook: %s (non-fatal)\n", strerror(errno));
            net_lnk = NULL;
        } else {
            printf("NET_LSM: arda_network_veto attached (socket_connect gate active).\n");
        }
    }

    /* Find and report the map */
    struct bpf_map *map = bpf_object__find_map_by_name(obj, "arda_harmony_map");
    if (map) {
        harmony_map_fd = bpf_map__fd(map);
        printf("Harmony map FD: %d (use bpftool map show id <id> to inspect)\n", harmony_map_fd);

        /* Report map ID for seeding */
        struct bpf_map_info info = {};
        __u32 len = sizeof(info);
        if (bpf_map_get_info_by_fd(harmony_map_fd, &info, &len) == 0) {
            printf("MAP_ID=%u\n", info.id);
        }
    }

    struct bpf_map *verity_map = bpf_object__find_map_by_name(obj, "arda_verity_harmony_map");
    if (verity_map) {
        verity_harmony_map_fd = bpf_map__fd(verity_map);
        printf("Verity harmony map FD: %d\n", verity_harmony_map_fd);
    }

    struct bpf_map *verity_generation_map = bpf_object__find_map_by_name(obj, "arda_verity_generation_map");
    if (verity_generation_map) {
        verity_generation_map_fd = bpf_map__fd(verity_generation_map);
        printf("VERITY_GENERATION_MAP_ID=");
        struct bpf_map_info info = {};
        __u32 len = sizeof(info);
        if (bpf_map_get_info_by_fd(verity_generation_map_fd, &info, &len) == 0) printf("%u\n", info.id);
        else printf("0\n");
    }
    struct bpf_map *active_generation_map = bpf_object__find_map_by_name(obj, "arda_active_generation_map");
    if (active_generation_map) {
        active_generation_map_fd = bpf_map__fd(active_generation_map);
        struct bpf_map_info info = {};
        __u32 len = sizeof(info);
        if (bpf_map_get_info_by_fd(active_generation_map_fd, &info, &len) == 0)
            printf("ACTIVE_GENERATION_MAP_ID=%u\n", info.id);
    }

    /* State map controls enforcement: index 0 -> 0 audit/passthrough, 1 enforce */
    struct bpf_map *state_map = bpf_object__find_map_by_name(obj, "arda_state_map");
    if (state_map) {
        state_map_fd = bpf_map__fd(state_map);
        set_enforcement(0);
        printf("STATE_MAP_FD=%d (enforcement default=0)\n", state_map_fd);
    } else {
        printf("WARNING: arda_state_map not found; enforcement toggle unavailable.\n");
    }

    /* Network deny map */
    struct bpf_map *net_deny_map = bpf_object__find_map_by_name(obj, "arda_network_deny_map");
    if (net_deny_map) {
        network_deny_map_fd = bpf_map__fd(net_deny_map);
        struct bpf_map_info ndinfo = {};
        __u32 ndlen = sizeof(ndinfo);
        if (network_deny_map_fd >= 0 && bpf_map_get_info_by_fd(network_deny_map_fd, &ndinfo, &ndlen) == 0) {
            printf("NETWORK_DENY_MAP_ID=%u\n", ndinfo.id);
        }
    }

    struct bpf_map *deny_map = bpf_object__find_map_by_name(obj, "arda_deny_count");
    if (deny_map) {
        deny_count_map_fd = bpf_map__fd(deny_map);
        struct bpf_map_info dinfo = {};
        __u32 dlen = sizeof(dinfo);
        if (deny_count_map_fd >= 0 && bpf_map_get_info_by_fd(deny_count_map_fd, &dinfo, &dlen) == 0) {
            printf("DENY_COUNT_MAP_ID=%u\n", dinfo.id);
        }
        printf("DENY_COUNT_START=%llu\n", (unsigned long long)read_deny_count());
        fflush(stdout);
    }

    int seeded = 0;

    // Always seed running processes first in permanent mode — this is the
    // primary anti-lockout measure. Any binary currently executing will be
    // in the harmony map before enforcement turns on.
    if (seed_running) {
        int before = seeded;
        printf("SEED_RUNNING_PROCS: scanning /proc/*/exe...\n");
        fflush(stdout);
        seed_running_procs(max_seed, &seeded);
        printf("SEED_RUNNING_PROCS: +%d entries\n", seeded - before);
        fflush(stdout);
    }

    if (seed_count > 0) {
        printf("SEED_PATHS: %d\n", seed_count);
        for (int i = 0; i < seed_count && seeded < max_seed; i++) {
            if (seed_harmony_path(seed_paths[i])) seeded++;
        }
    }
    int verity_seeded = 0;
    if (verity_digest_count > 0) {
        printf("SEED_VERITY_DIGESTS: %d\n", verity_digest_count);
        for (int i = 0; i < verity_digest_count; i++) {
            if (seed_verity_digest(verity_digests[i])) verity_seeded++;
        }
    }
    if (seed_dir_count > 0) {
        printf("SEED_DIRS: %d\n", seed_dir_count);
        for (int i = 0; i < seed_dir_count && seeded < max_seed; i++) {
            seed_exec_dir(seed_dirs[i], 0, max_seed, &seeded);
        }
    }
    if (seed_dir_recursive_count > 0) {
        printf("SEED_DIRS_RECURSIVE: %d\n", seed_dir_recursive_count);
        for (int i = 0; i < seed_dir_recursive_count && seeded < max_seed; i++) {
            seed_exec_dir(seed_dirs_recursive[i], 1, max_seed, &seeded);
        }
    }
    seeded_total = seeded;
    printf("SEED_TOTAL: %d (max=%d min_enforce=%d)\n", seeded_total, max_seed, min_seed_for_enforce);
    printf("VERITY_SEED_TOTAL: %d\n", verity_seeded);
    fflush(stdout);

    /* Apply initial network deny/allow entries from CLI args */
    for (int i = 0; i < deny_pid_count; i++) set_network_deny_pid(deny_pids[i], 1);
    for (int i = 0; i < allow_pid_count; i++) set_network_deny_pid(allow_pids[i], 0);

    /* Print the program FD for external use */
    printf("PROG_FD=%d\n", bpf_program__fd(prog));
    fflush(stdout);

    if (force_audit && state_map_fd >= 0) {
        set_enforcement(0);
        printf("ENFORCEMENT_SET: AUDIT\n");
        fflush(stdout);
    }


    if (force_verity_enforce && (verity_seeded == 0 || verity_cgroup_id == 0)) {
        set_enforcement_mode(ARDA_MODE_AUDIT);
        printf("ENFORCEMENT_REFUSED: strict fs-verity mode has no appraised digest entries.\n");
        fflush(stdout);
        force_verity_enforce = 0;
    }

    if (force_permanent && !confirm_permanent) {
        set_enforcement(0);
        printf("ENFORCEMENT_REFUSED: --permanent requires --confirm-permanent; staying AUDIT.\n");
        fflush(stdout);
        force_permanent = 0;
        force_enforce = 0;
    }

    if ((force_permanent || force_enforce || enforce_seconds > 0) && seeded_total < min_seed_for_enforce) {
        set_enforcement(0);
        printf("ENFORCEMENT_REFUSED: seeded_total=%d below min_seed=%d; staying AUDIT to avoid lockout.\n",
               seeded_total, min_seed_for_enforce);
        fflush(stdout);
        force_permanent = 0;
        force_enforce = 0;
        enforce_seconds = 0;
    }

    if (force_verity_enforce && state_map_fd >= 0) {
        __u64 active = verity_generation;
        if (bpf_map_update_elem(active_generation_map_fd, &verity_cgroup_id, &active, BPF_ANY) != 0) {
            set_enforcement_mode(ARDA_MODE_AUDIT);
            fprintf(stderr, "ENFORCEMENT_REFUSED: active generation update failed: %s\n", strerror(errno));
            force_verity_enforce = 0;
        }
    }
    if (force_verity_enforce && state_map_fd >= 0) {
        set_enforcement_mode(ARDA_MODE_FSVERITY_STRICT);
        printf("ENFORCEMENT_SET: FSVERITY_STRICT\n");
        fflush(stdout);
        if (failsafe_seconds > 0) {
            sleep(failsafe_seconds);
            set_enforcement_mode(ARDA_MODE_AUDIT);
            printf("ENFORCEMENT_FAILSAFE: strict fs-verity enforcement disabled.\n");
            fflush(stdout);
        }
    } else if (force_permanent && state_map_fd >= 0) {
        set_enforcement(1);
        printf("ENFORCEMENT_SET: PERMANENT\n");
        if (!no_failsafe && failsafe_seconds > 0) {
            printf("ENFORCEMENT_FAILSAFE: permanent mode will auto-disable in %d second(s)\n", failsafe_seconds);
        }
        printf("LSM is ACTIVE. Mode=PERMANENT (exec gate on while failsafe permits).\n");
        printf("ESCAPE HATCH: docker stop arda-lsm-loader  — destroys the link and disables enforcement.\n");
        fflush(stdout);
        if (!no_failsafe && failsafe_seconds > 0) {
            sleep(failsafe_seconds);
            set_enforcement(0);
            printf("ENFORCEMENT_FAILSAFE: disabled permanent enforcement; loader remains AUDIT.\n");
            fflush(stdout);
        }
    } else if (force_enforce && state_map_fd >= 0) {
        set_enforcement(1);
        printf("ENFORCEMENT_SET: ENFORCE\n");
        fflush(stdout);
        if (failsafe_seconds > 0) {
            printf("ENFORCEMENT_FAILSAFE: will auto-disable in %d second(s)\n", failsafe_seconds);
            fflush(stdout);
            sleep(failsafe_seconds);
            set_enforcement(0);
            printf("ENFORCEMENT_FAILSAFE: disabled.\n");
            fflush(stdout);
        }
    } else if (enforce_seconds > 0 && state_map_fd >= 0) {
        if (delay_seconds > 0) {
            printf("ENFORCEMENT_PULSE: delay %d second(s) before enabling...\n", delay_seconds);
            fflush(stdout);
            sleep(delay_seconds);
        }
        printf("ENFORCEMENT_PULSE: enabling for %d second(s)...\n", enforce_seconds);
        fflush(stdout);
        set_enforcement(1);
        sleep(enforce_seconds);
        set_enforcement(0);
        printf("ENFORCEMENT_PULSE: disabled.\n");
        fflush(stdout);
        if (deny_count_map_fd >= 0) {
            printf("DENY_COUNT_END=%llu\n", (unsigned long long)read_deny_count());
            fflush(stdout);
        }
    } else {
        printf("LSM is ACTIVE. Mode=AUDIT (no blocks). Pass --permanent to enable permanent enforcement.\n");
    }

    while (running) {
        sleep(1);
    }

    printf("\nDetaching LSM hooks...\n");
    set_enforcement(0);
    if (net_lnk) bpf_link__destroy(net_lnk);
    if (bpf_lnk) bpf_link__destroy(bpf_lnk);
    if (obj) bpf_object__close(obj);
    printf("LSM hooks detached. Enforcement disabled.\n");
    return 0;
}
