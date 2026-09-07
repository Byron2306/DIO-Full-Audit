import json
from pathlib import Path


CONFIG_PATH = Path("experiments/metamorphic_adaptation/config/native_bindings.v1.json")


def _load_config():
    assert CONFIG_PATH.exists(), "native bindings config is missing"
    return json.loads(CONFIG_PATH.read_text())


def _script_from_argv(argv):
    return next((part for part in argv if part.startswith("scripts/") and part.endswith(".py")), None)


def test_native_bindings_config_declares_real_entrypoints():
    cfg = _load_config()

    assert cfg["binding_version"] == "DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1"
    assert cfg["adaptation_episodes"], "must declare adaptation episodes"
    assert cfg["transfer_executors"], "must declare transfer executors"

    missing = []

    for episode in cfg["adaptation_episodes"]:
        assert episode["episode_id"]
        assert episode["factor_pressure"]
        assert episode["commands"]

        for command in episode["commands"]:
            script = _script_from_argv(command["argv"])
            assert script, f"{command['label']} does not declare a repository script"
            if not Path(script).exists():
                missing.append((command["label"], script))

    for command in cfg["transfer_executors"]:
        script = _script_from_argv(command["argv"])
        assert script, f"{command['label']} does not declare a repository script"
        if not Path(script).exists():
            missing.append((command["label"], script))

    assert missing == []


def test_native_bindings_do_not_smuggle_external_commands():
    cfg = _load_config()

    allowed_prefixes = ("python", "{python}")

    for episode in cfg["adaptation_episodes"]:
        for command in episode["commands"]:
            assert command["argv"][0] in allowed_prefixes

    for command in cfg["transfer_executors"]:
        assert command["argv"][0] in allowed_prefixes


def test_native_bindings_define_all_factor_state_roots():
    cfg = _load_config()

    assert set(cfg["state_roots"]) == {"semantic", "market", "beast"}

    for factor, roots in cfg["state_roots"].items():
        assert roots, f"{factor} must have at least one declared state root"
        assert all(isinstance(root, str) and root for root in roots)


def test_native_bindings_keep_authority_under_separate_custody():
    cfg = _load_config()

    authority_roots = cfg["authority_roots"]
    assert authority_roots
    assert "authority" in authority_roots
    assert "governance" in authority_roots

    flattened_state_roots = {
        root
        for roots in cfg["state_roots"].values()
        for root in roots
    }

    assert not set(authority_roots) & flattened_state_roots
