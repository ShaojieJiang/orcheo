from __future__ import annotations
from orcheo_backend.app.routers import workflows


def test_required_plugins_from_metadata_prefers_required_plugins_key() -> None:
    """Legacy required_plugins list is honored when requiredPlugins is absent."""
    metadata = {"template": {"required_plugins": [" foo ", "", "bar"]}}
    result = workflows._required_plugins_from_metadata(metadata)
    assert result == ["foo", "bar"]


def test_required_plugins_from_metadata_rejects_non_list() -> None:
    """Non-list values are ignored rather than raising."""
    metadata = {"template": {"required_plugins": "not-a-list"}}
    assert workflows._required_plugins_from_metadata(metadata) == []


class DummyRunnableConfig:
    def __init__(self) -> None:
        self.called = False

    def model_dump(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.called = True
        return {"foo": "bar", "mode": args, "options": kwargs}


def test_serialize_runnable_config_invokes_model_dump() -> None:
    """Serializable runnable configs are normalized via json mode dumping."""
    config = DummyRunnableConfig()
    normalized = workflows._serialize_runnable_config(config)  # type: ignore[arg-type]
    assert normalized["foo"] == "bar"
    assert config.called
    assert workflows._serialize_runnable_config(None) is None
