import pytest

from insights.settings import Settings, SettingsError

REQUIRED = {"ELASTIC_URL": "https://example.es.io", "ELASTIC_API_KEY": "secret"}


def test_defaults_apply_when_only_credentials_are_given():
    settings = Settings.from_env(REQUIRED)
    assert (settings.owner, settings.index_prefix) == ("you", "")
    assert settings.inference_id == ".elser-2-elasticsearch"


def test_optional_values_override_defaults():
    settings = Settings.from_env({**REQUIRED, "OWNER_NAME": "Arav", "ELASTIC_INDEX_PREFIX": "arav-"})
    assert (settings.owner, settings.index_prefix) == ("Arav", "arav-")


def test_missing_and_blank_credentials_are_all_named():
    with pytest.raises(SettingsError) as error:
        Settings.from_env({"ELASTIC_URL": "  "})
    assert "ELASTIC_URL" in str(error.value)
    assert "ELASTIC_API_KEY" in str(error.value)


def test_secrets_stay_out_of_the_repr():
    assert "secret" not in repr(Settings.from_env(REQUIRED))
