from pathlib import Path

from parsers.alignment import align_subtitles_to_script
from parsers.script_parser import parse_script
from parsers.srt_parser import parse_srt


def test_alignment_prefers_related_script_segment(tmp_path: Path) -> None:
    srt = tmp_path / "input.srt"
    script = tmp_path / "script.txt"
    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nMercy is not weakness.\n",
        encoding="utf-8",
    )
    script.write_text(
        "Compassion and mercy are not signs of weakness. Justice requires wisdom.",
        encoding="utf-8",
    )

    blocks = parse_srt(srt)
    script_doc = parse_script(script)
    alignments = align_subtitles_to_script(blocks, script_doc)

    assert len(alignments) == 1
    assert "weakness" in alignments[0].script_excerpt.lower()
