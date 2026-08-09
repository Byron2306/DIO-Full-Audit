/*
 * ARDA LSM Loader
 *
 * Phase 1 goal:
 * provide one canonical loader artifact path for Arda's BPF LSM, so sovereign
 * mode can converge on a first-class loader instead of an implicit BCC attach.
 *
 * This loader is intentionally minimal:
 * - open a compiled BPF object
 * - load it with libbpf
 * - attach the first program via bpf_program__attach()
 * - keep the link alive until signalled
 *
 * Build example:
 *   cc -O2 -Wall -Wextra -o arda_lsm_loader arda_lsm_loader.c -lbpf
 *
 * Usage:
 *   ./arda_lsm_loader ./arda_physical_lsm.o [--timeout-seconds N] [--pin-root /sys/fs/bpf/arda] [--enforcement-mode legacy_inode|audit|fsverity_strict]
 */

#include <errno.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include <bpf/bpf.h>
#include <bpf/libbpf.h>

static volatile sig_atomic_t keep_running = 1;

#define ARDA_MODE_AUDIT 0
#define ARDA_MODE_LEGACY_INODE 1
#define ARDA_MODE_FSVERITY_STRICT 2

struct arda_map_pin_spec {
    const char *map_name;
    const char *pin_basename;
};

struct arda_policy_state {
    __u64 generation_hash_prefix;
    __u32 redline_rule_count;
    __u32 projection_flags;
};

struct arda_last_deny_event {
    __u64 cgroup_id;
    __u64 active_generation;
    unsigned long inode;
    unsigned int dev;
    __u32 enforcement_mode;
    __u32 deny_reason;
};

static const struct arda_map_pin_spec arda_map_pins[] = {
    { "arda_harmony_map", "harmony_map" },
    { "arda_state_map", "state_map" },
    { "arda_deny_count", "deny_count" },
    { "arda_verity_identity_map", "verity_identity_map" },
    { "arda_active_generation_map", "active_generation_map" },
    { "arda_measured_exec_map", "measured_exec_map" },
    { "arda_policy_state_map", "policy_state_map" },
    { "arda_lockdown_map", "lockdown_map" },
    { "arda_last_deny_event_map", "last_deny_event_map" },
};

static void handle_signal(int sig) {
    (void)sig;
    keep_running = 0;
}

static void raise_memlock_limit(void) {
    struct rlimit limit = {0};
    if (getrlimit(RLIMIT_MEMLOCK, &limit) != 0) {
        fprintf(stderr, "ARDA_LOADER: getrlimit(RLIMIT_MEMLOCK) failed: %s\n", strerror(errno));
        return;
    }

    if (limit.rlim_cur == RLIM_INFINITY) {
        return;
    }

    limit.rlim_cur = limit.rlim_max;
    if (setrlimit(RLIMIT_MEMLOCK, &limit) != 0) {
        fprintf(
            stderr,
            "ARDA_LOADER: setrlimit(RLIMIT_MEMLOCK=%llu) failed: %s\n",
            (unsigned long long)limit.rlim_cur,
            strerror(errno)
        );
    }
}

static int ensure_directory(const char *path) {
    if (mkdir(path, 0755) == 0 || errno == EEXIST) {
        return 0;
    }
    fprintf(stderr, "ARDA_LOADER: mkdir(%s) failed: %s\n", path, strerror(errno));
    return -1;
}

static void describe_object_maps(struct bpf_object *obj) {
    struct bpf_map *map = NULL;
    bool first = true;

    fprintf(stderr, "ARDA_LOADER: object maps:");
    bpf_object__for_each_map(map, obj) {
        const char *name = bpf_map__name(map);
        fprintf(stderr, "%s%s", first ? " " : ", ", name ? name : "<unnamed>");
        first = false;
    }
    if (first) {
        fprintf(stderr, " <none>");
    }
    fprintf(stderr, "\n");
}

static struct bpf_map *find_required_map(struct bpf_object *obj, const struct arda_map_pin_spec *spec) {
    struct bpf_map *map = bpf_object__find_map_by_name(obj, spec->map_name);
    if (map) {
        return map;
    }
    if (strcmp(spec->map_name, spec->pin_basename) != 0) {
        map = bpf_object__find_map_by_name(obj, spec->pin_basename);
        if (map) {
            fprintf(
                stderr,
                "ARDA_LOADER: map alias resolved %s -> %s\n",
                spec->map_name,
                spec->pin_basename
            );
            return map;
        }
    }
    return NULL;
}

static int configure_map_pins(struct bpf_object *obj, const char *pin_root) {
    char map_pin[4096];

    if (ensure_directory(pin_root) != 0) {
        return -1;
    }

    for (size_t i = 0; i < sizeof(arda_map_pins) / sizeof(arda_map_pins[0]); i++) {
        struct bpf_map *map = find_required_map(obj, &arda_map_pins[i]);
        if (!map) {
            fprintf(stderr, "ARDA_LOADER: required map missing: %s\n", arda_map_pins[i].map_name);
            describe_object_maps(obj);
            return -1;
        }

        snprintf(map_pin, sizeof(map_pin), "%s/%s", pin_root, arda_map_pins[i].pin_basename);
        if (bpf_map__set_pin_path(map, map_pin) != 0) {
            fprintf(stderr, "ARDA_LOADER: failed to set pin path %s\n", map_pin);
            return -1;
        }
        printf("ARDA_LOADER: map_pin %s -> %s\n", arda_map_pins[i].map_name, map_pin);
    }

    return 0;
}

static int initialize_runtime_maps(struct bpf_object *obj, const char *enforcement_mode) {
    const char *mode_name = enforcement_mode ? enforcement_mode : "audit";
    __u32 index = 0;
    __u32 mode_value = ARDA_MODE_AUDIT;
    __u64 deny_count_zero = 0;
    __u32 lockdown_disabled = 0;
    struct arda_policy_state policy_state_zero = {};
    struct arda_last_deny_event last_deny_zero = {};
    int state_map_fd = -1;
    int deny_count_map_fd = -1;
    int policy_state_map_fd = -1;
    int lockdown_map_fd = -1;
    int last_deny_map_fd = -1;

    if (strcmp(mode_name, "audit") == 0) {
        mode_value = ARDA_MODE_AUDIT;
    } else if (strcmp(mode_name, "legacy_inode") == 0) {
        mode_value = ARDA_MODE_LEGACY_INODE;
    } else if (strcmp(mode_name, "fsverity_strict") == 0) {
        mode_value = ARDA_MODE_FSVERITY_STRICT;
    } else {
        fprintf(stderr, "ARDA_LOADER: unsupported enforcement mode %s\n", mode_name);
        return -1;
    }

    state_map_fd = bpf_object__find_map_fd_by_name(obj, "arda_state_map");
    if (state_map_fd < 0) {
        state_map_fd = bpf_object__find_map_fd_by_name(obj, "state_map");
    }
    if (state_map_fd < 0) {
        fprintf(stderr, "ARDA_LOADER: state map fd lookup failed\n");
        describe_object_maps(obj);
        return -1;
    }
    if (bpf_map_update_elem(state_map_fd, &index, &mode_value, BPF_ANY) != 0) {
        fprintf(stderr, "ARDA_LOADER: failed to initialize state map: %s\n", strerror(errno));
        return -1;
    }

    deny_count_map_fd = bpf_object__find_map_fd_by_name(obj, "arda_deny_count");
    if (deny_count_map_fd < 0) {
        deny_count_map_fd = bpf_object__find_map_fd_by_name(obj, "deny_count");
    }
    if (deny_count_map_fd < 0) {
        fprintf(stderr, "ARDA_LOADER: deny_count map fd lookup failed\n");
        describe_object_maps(obj);
        return -1;
    }
    if (bpf_map_update_elem(deny_count_map_fd, &index, &deny_count_zero, BPF_ANY) != 0) {
        fprintf(stderr, "ARDA_LOADER: failed to initialize deny_count map: %s\n", strerror(errno));
        return -1;
    }

    policy_state_map_fd = bpf_object__find_map_fd_by_name(obj, "arda_policy_state_map");
    if (policy_state_map_fd < 0) {
        policy_state_map_fd = bpf_object__find_map_fd_by_name(obj, "policy_state_map");
    }
    if (policy_state_map_fd < 0) {
        fprintf(stderr, "ARDA_LOADER: policy_state map fd lookup failed\n");
        describe_object_maps(obj);
        return -1;
    }
    if (bpf_map_update_elem(policy_state_map_fd, &index, &policy_state_zero, BPF_ANY) != 0) {
        fprintf(stderr, "ARDA_LOADER: failed to initialize policy_state map: %s\n", strerror(errno));
        return -1;
    }

    lockdown_map_fd = bpf_object__find_map_fd_by_name(obj, "arda_lockdown_map");
    if (lockdown_map_fd < 0) {
        lockdown_map_fd = bpf_object__find_map_fd_by_name(obj, "lockdown_map");
    }
    if (lockdown_map_fd < 0) {
        fprintf(stderr, "ARDA_LOADER: lockdown map fd lookup failed\n");
        describe_object_maps(obj);
        return -1;
    }
    if (bpf_map_update_elem(lockdown_map_fd, &index, &lockdown_disabled, BPF_ANY) != 0) {
        fprintf(stderr, "ARDA_LOADER: failed to initialize lockdown map: %s\n", strerror(errno));
        return -1;
    }

    last_deny_map_fd = bpf_object__find_map_fd_by_name(obj, "arda_last_deny_event_map");
    if (last_deny_map_fd < 0) {
        last_deny_map_fd = bpf_object__find_map_fd_by_name(obj, "last_deny_event_map");
    }
    if (last_deny_map_fd < 0) {
        fprintf(stderr, "ARDA_LOADER: last_deny_event map fd lookup failed\n");
        describe_object_maps(obj);
        return -1;
    }
    if (bpf_map_update_elem(last_deny_map_fd, &index, &last_deny_zero, BPF_ANY) != 0) {
        fprintf(stderr, "ARDA_LOADER: failed to initialize last_deny_event map: %s\n", strerror(errno));
        return -1;
    }

    printf("ARDA_LOADER: enforcement_mode %s\n", mode_name);
    printf("ARDA_LOADER: deny_count initialized to 0\n");
    printf("ARDA_LOADER: policy_state initialized to zero\n");
    printf("ARDA_LOADER: lockdown initialized to disabled\n");
    printf("ARDA_LOADER: last_deny_event initialized to zero\n");
    return 0;
}

int main(int argc, char **argv) {
    struct bpf_object *obj = NULL;
    struct bpf_program *prog = NULL;
    struct bpf_link *link = NULL;
    const char *obj_path = NULL;
    const char *pin_root = NULL;
    const char *enforcement_mode = "audit";
    unsigned int timeout_seconds = 0;
    time_t start_time = 0;

    if (argc != 2 && argc != 4 && argc != 6 && argc != 8) {
        fprintf(
            stderr,
            "usage: %s <bpf_object.o> [--timeout-seconds N] [--pin-root /sys/fs/bpf/arda] [--enforcement-mode legacy_inode|audit|fsverity_strict]\n",
            argv[0]
        );
        return 1;
    }

    obj_path = argv[1];
    for (int i = 2; i + 1 < argc; i += 2) {
        if (strcmp(argv[i], "--timeout-seconds") == 0) {
            timeout_seconds = (unsigned int)strtoul(argv[i + 1], NULL, 10);
        } else if (strcmp(argv[i], "--pin-root") == 0) {
            pin_root = argv[i + 1];
        } else if (strcmp(argv[i], "--enforcement-mode") == 0) {
            enforcement_mode = argv[i + 1];
        } else {
            fprintf(stderr, "ARDA_LOADER: unknown option %s\n", argv[i]);
            return 1;
        }
    }
    raise_memlock_limit();

    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);

    obj = bpf_object__open_file(obj_path, NULL);
    if (!obj) {
        fprintf(stderr, "ARDA_LOADER: open failed for %s\n", obj_path);
        return 1;
    }

    if (pin_root) {
        if (configure_map_pins(obj, pin_root) != 0) {
            bpf_object__close(obj);
            return 1;
        }
    }

    if (bpf_object__load(obj) != 0) {
        fprintf(stderr, "ARDA_LOADER: load failed for %s\n", obj_path);
        bpf_object__close(obj);
        return 1;
    }

    if (initialize_runtime_maps(obj, enforcement_mode) != 0) {
        bpf_object__close(obj);
        return 1;
    }

    prog = bpf_object__next_program(obj, NULL);
    if (!prog) {
        fprintf(stderr, "ARDA_LOADER: no program found in %s\n", obj_path);
        bpf_object__close(obj);
        return 1;
    }

    link = bpf_program__attach(prog);
    if (!link) {
        fprintf(stderr, "ARDA_LOADER: attach failed for %s\n", obj_path);
        bpf_object__close(obj);
        return 1;
    }

    printf("ARDA_LOADER: attached %s\n", obj_path);
    if (pin_root) {
        printf("ARDA_LOADER: pin_root %s\n", pin_root);
    }
    fflush(stdout);
    start_time = time(NULL);

    while (keep_running) {
        sleep(1);
        if (timeout_seconds > 0 && time(NULL) - start_time >= (time_t)timeout_seconds) {
            fprintf(stderr, "ARDA_LOADER: timeout reached, auto-detaching\n");
            keep_running = 0;
        }
    }

    bpf_link__destroy(link);
    bpf_object__close(obj);
    printf("ARDA_LOADER: detached %s\n", obj_path);
    return 0;
}
