from pathlib import Path

import yaml

from translator.config import load_config
from translator.pipeline import translate_project


def test_pipeline_creates_expected_outputs(tmp_path: Path) -> None:
    srt = tmp_path / "input.srt"
    script = tmp_path / "script.txt"
    config = tmp_path / "config.yaml"
    out_dir = tmp_path / "outputs"

    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nPeace be upon you.\n",
        encoding="utf-8",
    )
    script.write_text(
        "Peace be upon you. May mercy and guidance follow.",
        encoding="utf-8",
    )
    config.write_text(
        yaml.safe_dump(
            {
                "provider": "mock",
                "model": "mock",
                "output": {"output_dir": str(out_dir), "write_review_csv": True},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_config(config)
    outputs = translate_project(str(srt), str(script), ["ur"], loaded, review_mode=True)

    assert "ur" in outputs
    assert (out_dir / "input.ur.srt").exists()
    assert (out_dir / "input.ur.report.json").exists()
    assert (out_dir / "input.ur.review.csv").exists()
    assert (out_dir / "input.ur.flags.txt").exists()


def test_pipeline_supports_manual_provider(tmp_path: Path) -> None:
    srt = tmp_path / "input.srt"
    script = tmp_path / "script.txt"
    config = tmp_path / "config.yaml"
    out_dir = tmp_path / "outputs"

    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nAllah is merciful.\n",
        encoding="utf-8",
    )
    script.write_text("Allah is merciful and just.", encoding="utf-8")
    config.write_text(
        yaml.safe_dump(
            {
                "provider": "manual",
                "model": "manual",
                "output": {"output_dir": str(out_dir), "write_review_csv": True},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_config(config)
    outputs = translate_project(str(srt), str(script), ["ur"], loaded, review_mode=True)

    assert "ur" in outputs
    content = (out_dir / "input.ur.srt").read_text(encoding="utf-8")
    assert "Allah is merciful." in content
