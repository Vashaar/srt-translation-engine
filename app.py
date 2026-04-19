from __future__ import annotations

import json
import uuid
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

import streamlit as st

from parsers.srt_parser import parse_srt
from translator.config import load_config
from translator.models import LanguageArtifacts
from translator.pipeline import translate_project_with_artifacts
from translator.text import is_rtl_language

APP_DIR = Path(__file__).resolve().parent
RUNS_DIR = APP_DIR / "outputs" / "gui_runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

APP_CONFIG = load_config(APP_DIR / "config.yaml")
LANGUAGE_OPTIONS = [(item.code, item.label) for item in APP_CONFIG.supported_languages()]
STYLE_OPTIONS = ["literal", "balanced", "natural"]


_PROVIDER_OPTIONS = ["lmstudio", "ollama", "argos"]
_PROVIDER_LABELS = {
    "lmstudio": "LM Studio",
    "ollama": "Ollama",
    "argos": "Argos + LM Studio",
}

_VRAM_GUIDANCE = (
    "**VRAM guidance**\n\n"
    "- **4 GB** → Qwen2.5:3b-instruct *(limited quality on Arabic/Urdu)*\n"
    "- **8 GB** → Qwen2.5:7b-instruct *(good)*\n"
    "- **12 GB** → Qwen2.5:14b-instruct Q4 *(very good)*\n"
    "- **16 GB** → Qwen2.5:14b-instruct *(best local quality)*"
)


def _fetch_ollama_models() -> list[str] | None:
    try:
        with urllib_request.urlopen("http://localhost:11434/api/tags", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [str(m["name"]) for m in data.get("models", [])]
    except Exception:
        return None


def _fetch_lmstudio_models() -> list[str] | None:
    try:
        with urllib_request.urlopen("http://localhost:1234/v1/models", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [str(m["id"]) for m in data.get("data", [])]
    except Exception:
        return None


def save_uploaded_file(upload, destination: Path) -> Path:
    destination.write_bytes(upload.getbuffer())
    return destination


def language_label(code: str) -> str:
    language = APP_CONFIG.language_config(code)
    return f"{language.label} ({language.code})"


def render_preview(language: str, artifacts: LanguageArtifacts) -> None:
    st.subheader(f"Preview: {language_label(language)}")
    blocks = parse_srt(artifacts.srt_path)
    preview_blocks = blocks[:8]
    if is_rtl_language(language):
        html = "".join(
            f"<p><strong>{block.index}</strong><br>{block.text.replace(chr(10), '<br>')}</p>"
            for block in preview_blocks
        )
        st.markdown(f"<div dir='rtl' style='text-align:right'>{html}</div>", unsafe_allow_html=True)
    else:
        for block in preview_blocks:
            st.markdown(f"**{block.index}**  \n{block.text}")


def render_flags(language: str, artifacts: LanguageArtifacts) -> None:
    if not artifacts.report.issues:
        st.success(f"{language_label(language)}: no issues flagged.")
    else:
        st.warning(f"{language_label(language)} flagged issues")
        flags_text = "\n".join(
            (
                f"[{issue.severity.upper()}] "
                f"{f'Block {issue.block_index}' if issue.block_index else 'Global'} "
                f"{issue.code}: {issue.message}"
            )
            for issue in artifacts.report.issues
        )
        st.code(flags_text, language="text")


def render_downloads(language: str, artifacts: LanguageArtifacts) -> None:
    st.download_button(
        label=f"Download {language}.srt",
        data=artifacts.srt_path.read_bytes(),
        file_name=artifacts.srt_path.name,
        mime="application/x-subrip",
        key=f"srt-{language}",
    )


def run_translation(
    srt_upload,
    script_upload,
    glossary_upload,
    languages: list[str],
    style_profile: str,
    review_mode: bool,
    provider: str,
    model: str,
) -> tuple[str, dict[str, LanguageArtifacts]]:
    config = load_config(APP_DIR / "config.yaml")
    config.raw["style_profile"] = style_profile
    config.raw["provider"] = provider
    config.raw["model"] = model

    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    srt_path = save_uploaded_file(srt_upload, run_dir / srt_upload.name)
    script_path = (
        str(save_uploaded_file(script_upload, run_dir / script_upload.name))
        if script_upload is not None
        else None
    )
    glossary_path = None
    if glossary_upload is not None:
        glossary_path = str(save_uploaded_file(glossary_upload, run_dir / glossary_upload.name))

    config.raw.setdefault("output", {})
    config.raw["output"]["output_dir"] = str(run_dir)

    artifacts = translate_project_with_artifacts(
        srt_path=str(srt_path),
        script_path=script_path,
        langs=languages,
        config=config,
        glossary_path=glossary_path,
        profile=style_profile,
        review_mode=review_mode,
    )
    return run_id, artifacts


def main() -> None:
    st.set_page_config(
        page_title="SRTranslate",
        page_icon="assets/app_logo.png",
        layout="wide",
    )
    st.title("SRTranslate")
    st.caption("Translate SRT subtitles with script-aware context and in-memory verification insights.")

    with st.sidebar:
        st.header("Inputs")
        srt_upload = st.file_uploader("Subtitle file (.srt)", type=["srt"])
        script_upload = st.file_uploader("Script file (.pdf, .txt, .md) — optional", type=["pdf", "txt", "md"])
        glossary_upload = st.file_uploader("Glossary file (.yaml)", type=["yaml", "yml"])
        st.header("Settings")
        default_provider = APP_CONFIG.provider if APP_CONFIG.provider in _PROVIDER_OPTIONS else "lmstudio"
        selected_provider = st.selectbox(
            "Provider",
            _PROVIDER_OPTIONS,
            index=_PROVIDER_OPTIONS.index(default_provider),
            format_func=lambda provider: _PROVIDER_LABELS.get(provider, provider),
        )
        if selected_provider == "ollama":
            ollama_models = _fetch_ollama_models()
            if ollama_models is None:
                st.warning("Ollama is unreachable at localhost:11434.")
                selected_model = st.text_input("Model name", value=APP_CONFIG.model)
            elif not ollama_models:
                st.warning("Ollama has no models installed.")
                selected_model = st.text_input("Model name", value=APP_CONFIG.model)
            else:
                default_model_idx = ollama_models.index(APP_CONFIG.model) if APP_CONFIG.model in ollama_models else 0
                selected_model = st.selectbox("Model", ollama_models, index=default_model_idx)
        else:
            lmstudio_models = _fetch_lmstudio_models()
            if lmstudio_models is None:
                st.warning("LM Studio is unreachable at localhost:1234.")
                label = "Refinement model name" if selected_provider == "argos" else "Model name"
                selected_model = st.text_input(label, value=APP_CONFIG.model)
            elif not lmstudio_models:
                st.warning("LM Studio has no models loaded.")
                label = "Refinement model name" if selected_provider == "argos" else "Model name"
                selected_model = st.text_input(label, value=APP_CONFIG.model)
            else:
                default_model_idx = lmstudio_models.index(APP_CONFIG.model) if APP_CONFIG.model in lmstudio_models else 0
                label = "Refinement model" if selected_provider == "argos" else "Model"
                selected_model = st.selectbox(label, lmstudio_models, index=default_model_idx)
        if selected_provider == "argos":
            st.caption("Argos drafts each subtitle offline, then LM Studio refines one block at a time.")
        st.info(_VRAM_GUIDANCE)
        selected_languages = st.multiselect(
            "Target languages",
            options=[code for code, _ in LANGUAGE_OPTIONS],
            format_func=language_label,
        )
        style_profile = st.selectbox("Translation style", STYLE_OPTIONS, index=1)
        review_mode = st.toggle("Review mode (in-memory only)", value=True)
        run_clicked = st.button("Start translation", type="primary", use_container_width=True)

    if run_clicked:
        if srt_upload is None:
            st.error("Please upload an `.srt` subtitle file.")
            return
        if not selected_languages:
            st.error("Please select at least one target language.")
            return

        progress = st.progress(0, text="Preparing translation run...")
        status_box = st.empty()
        try:
            progress.progress(15, text="Running translation pipeline...")
            run_id, artifacts = run_translation(
                srt_upload=srt_upload,
                script_upload=script_upload,
                glossary_upload=glossary_upload,
                languages=selected_languages,
                style_profile=style_profile,
                review_mode=review_mode,
                provider=selected_provider,
                model=selected_model,
            )
            progress.progress(100, text="Translation complete.")
            status_box.success(f"Run {run_id} completed.")
        except Exception as exc:
            progress.progress(100, text="Run failed.")
            status_box.error(f"Translation failed: {exc}")
            return

        st.header("Outputs")
        for language in selected_languages:
            language_artifacts = artifacts[language]
            report = language_artifacts.report
            with st.container(border=True):
                st.subheader(language_label(language))
                c1, c2, c3 = st.columns(3)
                c1.metric("Passed", "Yes" if report.passed else "Needs review")
                c2.metric("Issues", int(report.summary.get("issue_count", len(report.issues))))
                c3.metric("Avg confidence", report.summary.get("average_confidence", "--"))
                render_downloads(language, language_artifacts)
                render_preview(language, language_artifacts)
                render_flags(language, language_artifacts)


if __name__ == "__main__":
    main()
