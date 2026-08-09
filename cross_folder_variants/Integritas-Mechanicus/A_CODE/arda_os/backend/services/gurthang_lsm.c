#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

/* The Steel of Anglachel: Map of pids -> resonance state */
struct resonance_map_t {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, __u32);
    __type(value, __u32); // 0: Harmonic, 1: Muted, 2: Fallen
} resonance_map SEC(".maps");

/* Gurthang's Severance: LSM Hook for execve */
SEC("lsm/bprm_check_security")
int BPF_PROG(restrict_exec, struct linux_binprm *bprm) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    __u32 *state = bpf_map_lookup_elem(&resonance_map, &pid);

    if (state && *state >= 1) {
        bpf_printk("Gurthang: DENIED exec for pid %d (Dissonant State Detected).\n", pid);
        return -1; // Return "Operation not permitted" at the kernel level
    }

    return 0; // Lawful motion
}

/* Gurthang's Girdle: LSM Hook for network connections */
SEC("lsm/socket_connect")
int BPF_PROG(restrict_connect, struct socket *sock, struct sockaddr *address, int addrlen) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    __u32 *state = bpf_map_lookup_elem(&resonance_map, &pid);

    if (state && *state >= 2) { // 2: Fallen (Total Network Severance)
        bpf_printk("Gurthang: SEVERED connection for pid %d.\n", pid);
        return -13; // EACCES
    }

    return 0;
}

char LICENSE[] SEC("license") = "GPL";
