from translator.models import BatchTranslationRequest
from translator.providers.argos_provider import (
    ArgosTranslationProvider,
    _looks_suspicious_refinement,
    _strip_plain_text_response,
)


def _request() -> BatchTranslationRequest:
    return BatchTranslationRequest(
        items=[],
        source_language="en",
        target_language="es",
        target_language_name="Spanish",
        style_profile="balanced",
        glossary_terms={"Allah": "Allah"},
        do_not_translate=["Allah"],
        protected_terms=["Qur'an"],
    )


def test_refinement_prompt_includes_context_and_semantic_guardrails() -> None:
    prompt = ArgosTranslationProvider._build_refinement_prompt(
        previous_text="Before this line.",
        source_text="Allah is merciful.",
        next_text="After this line.",
        rough_translation="Allah es misericordioso.",
        target_language="Spanish",
        request_payload=_request(),
    )

    assert "Previous English subtitle for context only" in prompt
    assert "Refine only the current subtitle" in prompt
    assert "Preserve the meaning of the English line exactly" in prompt
    assert "Do not translate protected Islamic terms" in prompt
    assert "Allah" in prompt


def test_plain_text_response_cleanup_strips_common_wrappers() -> None:
    assert _strip_plain_text_response('Refined translation: "Allah es misericordioso."') == (
        "Allah es misericordioso."
    )


def test_suspicious_refinement_rejects_prompt_echo_and_length_explosion() -> None:
    assert _looks_suspicious_refinement("Original English subtitle: hello", "hola")
    assert _looks_suspicious_refinement("x" * 100, "short draft")
    assert not _looks_suspicious_refinement("Allah es misericordioso.", "Allah es misericordioso")


def test_argos_provider_can_disable_lmstudio_refinement() -> None:
    provider = ArgosTranslationProvider(
        model="local-model",
        refine_with_lmstudio=False,
    )

    assert provider.refine_with_lmstudio is False
    assert provider.device == "CPU (Argos)"
    assert provider.precision == "offline"
