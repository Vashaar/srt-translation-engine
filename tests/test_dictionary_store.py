from __future__ import annotations

from pathlib import Path

import yaml

from translator.dictionary_store import (
    dictionary_path,
    download_dictionary,
    import_dictionary,
    list_dictionaries,
)


class FakeHeaders:
    def __init__(self, content_type: str) -> None:
        self._content_type = content_type

    def get_content_type(self) -> str:
        return self._content_type


class FakeResponse:
    def __init__(self, payload: bytes, content_type: str = "application/json") -> None:
        self._payload = payload
        self.headers = FakeHeaders(content_type)

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_download_dictionary_normalizes_json_mapping(tmp_path: Path, monkeypatch) -> None:
    payload = b'{"Allah": "Allah", "Moses": "Musa"}'

    monkeypatch.setattr(
        "translator.dictionary_store.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(payload, "application/json"),
    )

    record = download_dictionary(
        "https://example.com/islamic_terms.json",
        "Islamic Terms",
        base_dir=tmp_path,
    )

    dictionaries = list_dictionaries(tmp_path)
    assert [item.name for item in dictionaries] == ["Islamic Terms"]

    saved = yaml.safe_load(dictionary_path(record, tmp_path).read_text(encoding="utf-8"))
    assert saved["terms"]["Moses"] == "Musa"
    assert saved["do_not_translate"] == []


def test_import_dictionary_supports_csv_pairs(tmp_path: Path) -> None:
    source = tmp_path / "pairs.csv"
    source.write_text("source,target\nPeace,Salaam\nMercy,Rahma\n", encoding="utf-8")

    record = import_dictionary(source, "CSV Terms", base_dir=tmp_path)

    saved = yaml.safe_load(dictionary_path(record, tmp_path).read_text(encoding="utf-8"))
    assert saved["terms"] == {"Peace": "Salaam", "Mercy": "Rahma"}


def test_import_dictionary_supports_text_rules(tmp_path: Path) -> None:
    source = tmp_path / "rules.txt"
    source.write_text(
        "Allah=Allah\nprotect:Muhammad\ndnt:Quran\n",
        encoding="utf-8",
    )

    record = import_dictionary(source, "Rule Terms", base_dir=tmp_path)

    saved = yaml.safe_load(dictionary_path(record, tmp_path).read_text(encoding="utf-8"))
    assert saved["terms"]["Allah"] == "Allah"
    assert saved["protected_terms"] == ["Muhammad"]
    assert saved["do_not_translate"] == ["Quran"]


def test_download_dictionary_supports_text_plain_yaml(tmp_path: Path, monkeypatch) -> None:
    payload = b"terms:\n  Allah: Allah\n  Mercy: Rahma\nprotected_terms:\n  - Ibrahim\n"

    monkeypatch.setattr(
        "translator.dictionary_store.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(payload, "text/plain"),
    )

    record = download_dictionary(
        "https://example.com/raw/glossary",
        "Plain Text YAML",
        base_dir=tmp_path,
    )

    saved = yaml.safe_load(dictionary_path(record, tmp_path).read_text(encoding="utf-8"))
    assert saved["terms"]["Mercy"] == "Rahma"
    assert saved["protected_terms"] == ["Ibrahim"]
