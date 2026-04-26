import pytest
from pathlib import Path
from researcher.memory.io import read_file, append_entry, last_n_entries


@pytest.fixture
def log_path(tmp_path):
    p = tmp_path / "RESEARCH-LOG.md"
    p.write_text("## 2026-04-23\nentry one\n\n## 2026-04-24\nentry two\n\n## 2026-04-25\nentry three\n")
    return str(p)


def test_read_file(log_path):
    content = read_file(log_path)
    assert "entry one" in content


def test_read_file_missing(tmp_path):
    content = read_file(str(tmp_path / "nope.md"))
    assert content == ""


def test_append_entry(tmp_path):
    p = tmp_path / "LOG.md"
    p.write_text("")
    append_entry(str(p), "## 2026-04-25\nnew entry\n")
    assert "new entry" in p.read_text()


def test_append_entry_creates_file(tmp_path):
    path = str(tmp_path / "NEW.md")
    append_entry(path, "## 2026-04-25\ncreated\n")
    assert Path(path).exists()


def test_last_n_entries_returns_last_n(log_path):
    result = last_n_entries(log_path, 2)
    assert "entry two" in result
    assert "entry three" in result
    assert "entry one" not in result


def test_last_n_entries_missing_file(tmp_path):
    result = last_n_entries(str(tmp_path / "nope.md"), 3)
    assert result == ""
