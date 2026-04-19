from translator.config import AppConfig
from translator.factory import build_provider


def test_build_provider_prefers_runtime_model_over_provider_config() -> None:
    config = AppConfig(
        raw={
            "provider": "lmstudio",
            "model": "top-level-model",
            "providers": {
                "lmstudio": {
                    "base_url": "http://127.0.0.1:1234/v1",
                    "model": "configured-provider-model",
                }
            },
        }
    )

    provider = build_provider("lmstudio", "selected-runtime-model", config=config)

    assert provider.model == "selected-runtime-model"
