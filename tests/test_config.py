from portfolio_checker.config import SPECS_BY_NAME, load_provider_configs


def names(configs):
    return [c.name for c in configs]


def test_no_keys_anywhere_returns_nothing(tmp_path):
    assert load_provider_configs(path=str(tmp_path / "missing.ini"), env={}) == []


def test_anthropic_environment_variable_configures_claude(tmp_path):
    configs = load_provider_configs(
        path=str(tmp_path / "missing.ini"), env={"ANTHROPIC_API_KEY": "env-key"}
    )

    assert names(configs) == ["claude"]
    assert configs[0].api_key == "env-key"
    assert configs[0].model == SPECS_BY_NAME["claude"].default_model
    assert configs[0].is_configured


def test_gemini_environment_variable_configures_gemini(tmp_path):
    configs = load_provider_configs(
        path=str(tmp_path / "missing.ini"), env={"GEMINI_API_KEY": "g-key"}
    )

    assert names(configs) == ["gemini"]
    assert configs[0].api_key == "g-key"
    assert configs[0].model == SPECS_BY_NAME["gemini"].default_model


def test_google_api_key_is_accepted_for_gemini(tmp_path):
    configs = load_provider_configs(
        path=str(tmp_path / "missing.ini"), env={"GOOGLE_API_KEY": "g-key"}
    )

    assert names(configs) == ["gemini"]


def test_gemini_api_key_wins_over_google_api_key(tmp_path):
    configs = load_provider_configs(
        path=str(tmp_path / "missing.ini"),
        env={"GEMINI_API_KEY": "preferred", "GOOGLE_API_KEY": "fallback"},
    )

    assert configs[0].api_key == "preferred"


def test_blank_environment_variable_is_treated_as_absent(tmp_path):
    assert load_provider_configs(path=str(tmp_path / "missing.ini"), env={"GEMINI_API_KEY": "  "}) == []


def test_config_file_supplies_keys_and_models(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text(
        "[claude]\napi_key = c-key\nmodel = claude-sonnet-5\n"
        "[gemini]\napi_key = g-key\nmodel = gemini-3.8-flash\n"
    )

    configs = load_provider_configs(path=str(path), env={})

    assert names(configs) == ["claude", "gemini"]
    assert configs[0].model == "claude-sonnet-5"
    assert configs[1].api_key == "g-key"


def test_only_the_configured_provider_is_returned(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[gemini]\napi_key = g-key\n")

    assert names(load_provider_configs(path=str(path), env={})) == ["gemini"]


def test_placeholder_keys_are_skipped(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[claude]\napi_key = sk-ant-...\n[gemini]\napi_key = real-key\n")

    # The untouched example value must not count as configured.
    assert names(load_provider_configs(path=str(path), env={})) == ["gemini"]


def test_environment_variable_wins_over_the_config_file(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[claude]\napi_key = file-key\n")

    configs = load_provider_configs(path=str(path), env={"ANTHROPIC_API_KEY": "env-key"})

    assert configs[0].api_key == "env-key"


def test_model_from_the_file_applies_even_when_the_key_comes_from_the_environment(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[claude]\nmodel = claude-sonnet-5\n")

    configs = load_provider_configs(path=str(path), env={"ANTHROPIC_API_KEY": "env-key"})

    assert configs[0].model == "claude-sonnet-5"


def test_unrelated_sections_are_ignored(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[other]\nvalue = 1\n")

    assert load_provider_configs(path=str(path), env={}) == []


def test_malformed_config_file_does_not_raise(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("this is not ini at all ][")

    configs = load_provider_configs(path=str(path), env={"GEMINI_API_KEY": "g-key"})

    assert names(configs) == ["gemini"]


def test_empty_model_setting_falls_back_to_the_default(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[gemini]\napi_key = k\nmodel =\n")

    assert load_provider_configs(path=str(path), env={})[0].model == SPECS_BY_NAME["gemini"].default_model


def test_providers_come_back_in_declaration_order(tmp_path):
    configs = load_provider_configs(
        path=str(tmp_path / "missing.ini"),
        env={"GEMINI_API_KEY": "g", "ANTHROPIC_API_KEY": "c"},
    )

    assert names(configs) == ["claude", "gemini"]
