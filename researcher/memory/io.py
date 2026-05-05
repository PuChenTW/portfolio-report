from datetime import date
from pathlib import Path


def read_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def append_entry(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(content + "\n")


def last_n_entries(path: str, n: int) -> str:
    if n <= 0:
        return ""
    content = read_file(path)
    if not content:
        return ""
    # Sections delimited by "\n## " — section bodies must not contain lines starting with "## "
    parts = content.split("\n## ")
    sections = [parts[0]] + ["## " + p for p in parts[1:]]
    return "\n".join(sections[-n:])


def entries_since(path: str, since: date) -> str:
    """Return all ## sections whose header date token (YYYY-MM-DD) is >= since."""
    content = read_file(path)
    if not content:
        return ""
    parts = content.split("\n## ")
    sections = [parts[0]] + ["## " + p for p in parts[1:]]
    result = []
    for section in sections:
        header_token = section.lstrip("# ").split()[0] if section.strip() else ""
        try:
            if date.fromisoformat(header_token) >= since:
                result.append(section)
        except ValueError:
            pass
    return "\n".join(result)
