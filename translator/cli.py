from __future__ import annotations

import argparse
import logging

from translator.config import load_config
from translator.pipeline import translate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate SRT subtitle files using a reference script for context and verification."
    )
    parser.add_argument("--srt", required=True, help="Path to the input .srt file")
    parser.add_argument(
        "--script",
        required=True,
        help="Path to the source script (.pdf, .txt, or .md)",
    )
    parser.add_argument(
        "--langs",
        nargs="+",
        required=True,
        help="Target language codes, for example: ur ar es",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config")
    parser.add_argument("--glossary", help="Optional glossary YAML path")
    parser.add_argument("--profile", help="Style profile override")
    parser.add_argument("--provider", help="Provider override, for example: ollama or openai")
    parser.add_argument("--model", help="Model override for the selected provider")
    parser.add_argument(
        "--review-mode",
        action="store_true",
        help="Write review CSV even if disabled in config",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    config = load_config(args.config)
    if args.provider:
        config.raw["provider"] = args.provider
    if args.model:
        config.raw["model"] = args.model
    outputs = translate_project(
        srt_path=args.srt,
        script_path=args.script,
        langs=args.langs,
        config=config,
        glossary_path=args.glossary,
        profile=args.profile,
        review_mode=args.review_mode,
    )
    for lang, path in outputs.items():
        print(f"{lang}: {path}")
    return 0
