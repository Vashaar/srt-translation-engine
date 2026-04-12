from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from parsers.srt_parser import parse_srt
from translator.config import load_config
from translator.models import LanguageArtifacts
from translator.pipeline import translate_project_with_artifacts
from translator.text import is_rtl_language

APP_DIR = Path(__file__).resolve().parent
RUNS_DIR = APP_DIR / "outputs" / "gui_runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

LANGUAGE_OPTIONS = [
    ("ur", "Urdu"),
    ("ar", "Arabic"),
    ("es", "Spanish"),
    ("id", "Indonesian"),
    ("tr", "Turkish"),
    ("fr", "French"),
    ("de", "German"),
    ("bn", "Bengali"),
    ("fa", "Persian"),
    ("ms", "Malay"),
]
STYLE_OPTIONS = ["literal", "balanced", "natural"]


@dataclass
class RunRecord:
    run_id: str
    languages: list[str]
    artifacts: dict[str, LanguageArtifacts]


class StreamlitLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))


def save_uploaded_file(upload, destination: Path) -> Path:
    destination.write_bytes(upload.getbuffer())
    return destination


def language_label(code: str) -> str:
    for lang_code, label in LANGUAGE_OPTIONS:
        if lang_code == code:
            return f"{label} ({code})"
    return code


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
    flags_text = artifacts.flags_path.read_text(encoding="utf-8")
    if flags_text.strip() == "No issues flagged.":
        st.success(f"{language_label(language)}: no issues flagged.")
    else:
        st.warning(f"{language_label(language)} flagged issues")
        st.code(flags_text, language="text")


def render_downloads(language: str, artifacts: LanguageArtifacts) -> None:
    st.download_button(
        label=f"Download {language}.srt",
        data=artifacts.srt_path.read_bytes(),
        file_name=artifacts.srt_path.name,
        mime="application/x-subrip",
        key=f"srt-{language}",
    )
    st.download_button(
        label=f"Download {language}.report.json",
        data=artifacts.report_path.read_bytes(),
        file_name=artifacts.report_path.name,
        mime="application/json",
        key=f"report-{language}",
    )
    st.download_button(
        label=f"Download {language}.flags.txt",
        data=artifacts.flags_path.read_bytes(),
        file_name=artifacts.flags_path.name,
        mime="text/plain",
        key=f"flags-{language}",
    )
    if artifacts.review_path is not None and artifacts.review_path.exists():
        st.download_button(
            label=f"Download {language}.review.csv",
            data=artifacts.review_path.read_bytes(),
            file_name=artifacts.review_path.name,
            mime="text/csv",
            key=f"review-{language}",
        )


def load_report_summary(artifacts: LanguageArtifacts) -> dict[str, object]:
    return json.loads(artifacts.report_path.read_text(encoding="utf-8"))


def run_translation(
    srt_upload,
    script_upload,
    glossary_upload,
    languages: list[str],
    style_profile: str,
    review_mode: bool,
) -> RunRecord:
    config = load_config(APP_DIR / "config.yaml")
    config.raw["style_profile"] = style_profile

    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    srt_path = save_uploaded_file(srt_upload, run_dir / srt_upload.name)
    script_path = save_uploaded_file(script_upload, run_dir / script_upload.name)
    glossary_path = None
    if glossary_upload is not None:
        glossary_path = str(save_uploaded_file(glossary_upload, run_dir / glossary_upload.name))

    config.raw.setdefault("output", {})
    config.raw["output"]["output_dir"] = str(run_dir)

    artifacts = translate_project_with_artifacts(
        srt_path=str(srt_path),
        script_path=str(script_path),
        langs=languages,
        config=config,
        glossary_path=glossary_path,
        profile=style_profile,
        review_mode=review_mode,
    )
    return RunRecord(run_id=run_id, languages=languages, artifacts=artifacts)


def init_state() -> None:
    if "run_history" not in st.session_state:
        st.session_state.run_history = []


def main() -> None:
    st.set_page_config(
        page_title="Subtitle Translation Tool",
        page_icon=":globe_with_meridians:",
        layout="wide",
    )
    init_state()

    st.title("Subtitle Translation Tool")
    st.caption("Translate SRT subtitles with script-aware context, verification, and review artifacts.")

    with st.sidebar:
        st.header("Inputs")
        srt_upload = st.file_uploader("Subtitle file (.srt)", type=["srt"])
        script_upload = st.file_uploader("Script file (.pdf, .txt, .md)", type=["pdf", "txt", "md"])
        glossary_upload = st.file_uploader("Glossary file (.yaml)", type=["yaml", "yml"])
        st.header("Settings")
        selected_languages = st.multiselect(
            "Target languages",
            options=[code for code, _ in LANGUAGE_OPTIONS],
            format_func=language_label,
        )
        style_profile = st.selectbox("Translation style", STYLE_OPTIONS, index=1)
        review_mode = st.toggle("Review mode", value=True)
        run_clicked = st.button("Start translation", type="primary", use_container_width=True)

    col1, col2 = st.columns([1.1, 0.9])
    with col1:
        st.subheader("Instructions")
        st.markdown(
            "- Upload an `.srt` subtitle file and a matching script.\n"
            "- Select one or more target languages.\n"
            "- Optionally upload a glossary and enable review mode.\n"
            "- Use the generated reports to inspect uncertain or flagged segments."
        )

    with col2:
        st.subheader("Previous Runs")
        if st.session_state.run_history:
            for record in reversed(st.session_state.run_history[-5:]):
                st.caption(f"Run {record.run_id}: {', '.join(record.languages)}")
        else:
            st.caption("No previous runs yet.")

    if run_clicked:
        if srt_upload is None:
            st.error("Please upload an `.srt` subtitle file.")
            return
        if script_upload is None:
            st.error("Please upload a script file in `.pdf`, `.txt`, or `.md` format.")
            return
        if not selected_languages:
            st.error("Please select at least one target language.")
            return

        log_handler = StreamlitLogHandler()
        log_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s - %(message)s"))
        pipeline_logger = logging.getLogger("translator.pipeline")
        pipeline_logger.setLevel(logging.INFO)
        pipeline_logger.addHandler(log_handler)

        progress = st.progress(0, text="Preparing translation run...")
        status_box = st.empty()
        try:
            progress.progress(15, text="Running translation pipeline...")
            result = run_translation(
                srt_upload=srt_upload,
                script_upload=script_upload,
                glossary_upload=glossary_upload,
                languages=selected_languages,
                style_profile=style_profile,
                review_mode=review_mode,
            )
            st.session_state.run_history.append(result)
            progress.progress(100, text="Translation complete.")
            status_box.success(f"Run {result.run_id} completed.")
        except Exception as exc:
            progress.progress(100, text="Run failed.")
            status_box.error(f"Translation failed: {exc}")
            pipeline_logger.removeHandler(log_handler)
            return
        pipeline_logger.removeHandler(log_handler)

        if log_handler.messages:
            with st.expander("Status log", expanded=True):
                st.code("\n".join(log_handler.messages), language="text")

        st.header("Outputs")
        for language in result.languages:
            artifacts = result.artifacts[language]
            report = load_report_summary(artifacts)
            with st.container(border=True):
                st.subheader(language_label(language))
                c1, c2, c3 = st.columns(3)
                c1.metric("Passed", "Yes" if report["passed"] else "Needs review")
                c2.metric("Issues", int(report["summary"]["issue_count"]))
                c3.metric("Avg confidence", report["summary"]["average_confidence"])
                render_downloads(language, artifacts)
                render_preview(language, artifacts)
                render_flags(language, artifacts)


if __name__ == "__main__":
    main()
