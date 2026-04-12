from pathlib import Path

from parsers.srt_parser import parse_srt


def test_parse_srt_reads_blocks(tmp_path: Path) -> None:
    path = tmp_path / "sample.srt"
    path.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nHello world.\n\n"
        "2\n00:00:03,500 --> 00:00:05,000\nSecond line.\n",
        encoding="utf-8",
    )

    blocks = parse_srt(path)

    assert len(blocks) == 2
    assert blocks[0].index == 1
    assert blocks[0].text == "Hello world."
    assert blocks[1].start == "00:00:03,500"
