from pathlib import Path

from app.core.config import settings


class LocalStorage:
    def __init__(self, root_path: str = settings.storage_path) -> None:
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)

    def save(self, object_key: str, content: bytes) -> None:
        target = self.root_path / object_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def delete(self, object_key: str) -> None:
        if not object_key:
            return
        target = self.root_path / object_key
        if target.exists() and target.is_file():
            target.unlink()

    def get_path(self, object_key: str) -> Path | None:
        if not object_key:
            return None
        target = (self.root_path / object_key).resolve()
        root = self.root_path.resolve()
        if root not in target.parents:
            return None
        return target if target.exists() and target.is_file() else None


local_storage = LocalStorage()
