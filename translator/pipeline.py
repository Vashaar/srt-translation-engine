from __future__ import annotations

import logging
from pathlib import Path

from parsers.alignment import align_subtitles_to_script
from parsers.script_parser import parse_script
from parsers.srt_parser import build_srt_blocks, parse_srt
from translator.config import AppConfig
from translator.factory import build_provider
from translator.glossary import load_glossary
from translator.models import (
    AlignmentResult,
    LanguageArtifacts,
    SubtitleBlock,
    TranslationRequest,
    TranslationResult,
)
from translator.reporting import ensure_output_dir, write_flags, write_report, write_review_csv, write_srt
from translator.text import is_rtl_language, rebalance_subtitle_lines
from verifier.checks import verify_translation

logger = logging.getLogger(__name__)


def translate_project(
    srt_path: str,
    script_path: str,
    langs: list[str],
    config: AppConfig,
    glossary_path: str | None = None,
    profile: str | None = None,
    review_mode: bool = False,
) -> dict[str, Path]:
    artifacts = translate_project_with_artifacts(
        srt_path=srt_path,
        script_path=script_path,
        langs=langs,
        config=config,
        glossary_path=glossary_path,
        profile=profile,
        review_mode=review_mode,
    )
    return {lang: result.srt_path for lang, result in artifacts.items()}


def translate_project_with_artifacts(
    srt_path: str,
    script_path: str,
    langs: list[str],
    config: AppConfig,
    glossary_path: str | None = None,
    profile: str | None = None,
    review_mode: bool = False,
) -> dict[str, LanguageArtifacts]:
    source_blocks = parse_srt(srt_path)
    script = parse_script(script_path)
    alignments = align_subtitles_to_script(source_blocks, script)
    glossary = load_glossary(glossary_path or config.raw.get("glossary", {}).get("default_path"))
    provider = build_provider(config.provider, config.model)

    output_dir = config.output_dir
    ensure_output_dir(output_dir)
    srt_stem = Path(srt_path).stem

    results: dict[str, LanguageArtifacts] = {}
    for lang in langs:
        logger.info("Translating language %s", lang)
        translated_blocks, translations = _translate_language(
            source_blocks=source_blocks,
            alignments=alignments,
            lang=lang,
            provider=provider,
            config=config,
            glossary=glossary,
            profile=profile or config.style_profile,
        )
        report = verify_translation(
            language=lang,
            source_blocks=source_blocks,
            translated_blocks=translated_blocks,
            alignments=alignments,
            translations=translations,
            allowed_source_leftovers=list(
                config.raw.get("translation", {}).get("allow_source_language_leftovers", [])
            )
            + list(glossary.get("do_not_translate", [])),
            glossary_terms=dict(glossary.get("terms", {})),
            protected_terms=list(glossary.get("protected_terms", []))
            + list(glossary.get("do_not_translate", []))
            + list(config.raw.get("glossary", {}).get("protected_terms", [])),
            rtl=is_rtl_language(lang) or bool(config.language_settings(lang).get("rtl", False)),
        )

        output_srt = output_dir / f"{srt_stem}.{lang}.srt"
        output_report = output_dir / f"{srt_stem}.{lang}.report.json"
        output_review = output_dir / f"{srt_stem}.{lang}.review.csv"
        output_flags = output_dir / f"{srt_stem}.{lang}.flags.txt"

        write_srt(output_srt, translated_blocks)
        write_report(output_report, report)
        write_flags(output_flags, report)
        if review_mode or config.raw.get("output", {}).get("write_review_csv", True):
            write_review_csv(output_review, source_blocks, translated_blocks, alignments, translations)
            review_path: Path | None = output_review
        else:
            review_path = None

        results[lang] = LanguageArtifacts(
            language=lang,
            srt_path=output_srt,
            report_path=output_report,
            review_path=review_path,
            flags_path=output_flags,
        )
    return results


def _translate_language(
    source_blocks: list[SubtitleBlock],
    alignments: list[AlignmentResult],
    lang: str,
    provider,
    config: AppConfig,
    glossary: dict[str, object],
    profile: str,
) -> tuple[list[SubtitleBlock], list[TranslationResult]]:
    translated_line_sets: list[list[str]] = []
    translation_results: list[TranslationResult] = []
    glossary_terms = dict(glossary.get("terms", {}))
    do_not_translate = list(glossary.get("do_not_translate", []))
    protected_terms = list(glossary.get("protected_terms", [])) + do_not_translate
    rtl = is_rtl_language(lang) or bool(config.language_settings(lang).get("rtl", False))
    for block, alignment in zip(source_blocks, alignments, strict=True):
        request = TranslationRequest(
            source_subtitle_text=block.text,
            script_context=alignment.script_excerpt,
            source_language=config.source_language,
            target_language=lang,
            style_profile=profile,
            glossary_terms=glossary_terms,
            do_not_translate=do_not_translate,
            protected_terms=protected_terms,
            rtl=rtl,
            metadata={
                "subtitle_index": block.index,
                "subtitle_start": block.start,
                "subtitle_end": block.end,
                "script_similarity": alignment.similarity,
                "used_script_as_truth": alignment.used_script_as_truth,
            },
        )
        result = provider.translate(request)
        if config.retry_low_confidence and result.confidence < config.low_confidence_threshold:
            result.notes.append("Low-confidence translation; review recommended.")
        translated_lines = (
            rebalance_subtitle_lines(result.translated_text, config.max_chars_per_line)
            if config.line_rebalancing_enabled
            else [line for line in result.translated_text.splitlines() if line.strip()] or [result.translated_text]
        )
        translated_line_sets.append(translated_lines)
        translation_results.append(result)
    translated_blocks = build_srt_blocks(source_blocks, translated_line_sets)
    return translated_blocks, translation_results
