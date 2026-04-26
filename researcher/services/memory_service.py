import os

from researcher.memory.io import append_entry, last_n_entries, read_file


class MemoryService:
    def __init__(self, base_path: str) -> None:
        self._base = base_path

    def resolve(self, filename: str) -> str:
        return os.path.join(self._base, filename)

    def read_file(self, path: str) -> str:
        return read_file(path)

    def last_n_entries(self, path: str, n: int) -> str:
        return last_n_entries(path, n)

    def append_entry(self, path: str, content: str) -> None:
        append_entry(path, content)
