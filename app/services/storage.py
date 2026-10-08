import os
from abc import ABC, abstractmethod
from pathlib import Path


class StorageInterface(ABC):
    """Abstract storage interface allowing local disk or cloud S3 replacement."""

    @abstractmethod
    def save(self, path: str, data: bytes) -> str:
        """Save bytes to storage path and return key/path."""
        pass

    @abstractmethod
    def read(self, path: str) -> bytes:
        """Read bytes from storage path."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if file exists at storage path."""
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete file at storage path."""
        pass


class LocalStorage(StorageInterface):
    """Local disk implementation of StorageInterface."""

    def __init__(self, base_dir: str = "storage"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _full_path(self, path: str) -> Path:
        # If absolute path and within base_dir, return it directly
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_dir / path

    def save(self, path: str, data: bytes) -> str:
        target = self._full_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)
        return str(path)

    def read(self, path: str) -> bytes:
        target = self._full_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Storage path not found: {path}")
        with open(target, "rb") as f:
            return f.read()

    def exists(self, path: str) -> bool:
        target = self._full_path(path)
        return target.exists()

    def delete(self, path: str) -> bool:
        target = self._full_path(path)
        if target.exists():
            target.unlink()
            return True
        return False
