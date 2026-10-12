from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_files(folder: Path, root: Path) -> list[dict[str, Any]]:
    if not folder.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in folder.rglob("*") if item.is_file()):
        if path.name.startswith("."):
            continue
        stat = path.stat()
        records.append(
            {
                "archivo": str(path.relative_to(root)),
                "huella": fingerprint(path),
                "tamano_bytes": stat.st_size,
                "modificado": datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc
                ).isoformat(timespec="seconds"),
            }
        )
    return records
