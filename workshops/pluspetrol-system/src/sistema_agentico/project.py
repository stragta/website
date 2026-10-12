from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import read_json


@dataclass(frozen=True)
class Project:
    root: Path

    @property
    def profile_path(self) -> Path:
        return self.root / "config" / "perfil.json"

    @property
    def system_path(self) -> Path:
        return self.root / "config" / "sistema.json"

    @property
    def state_path(self) -> Path:
        return self.root / "estado" / "estado.json"

    @property
    def current_run_path(self) -> Path:
        return self.root / "estado" / "ejecucion_actual.json"

    def profile(self) -> dict[str, Any]:
        return read_json(self.profile_path, {})

    def system(self) -> dict[str, Any]:
        return read_json(self.system_path, {})


def locate_project(start: Path | None = None) -> Project:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "config" / "sistema.json").exists():
            return Project(candidate)
    package_root = Path(__file__).resolve().parents[2]
    if (package_root / "config" / "sistema.json").exists():
        return Project(package_root)
    raise FileNotFoundError(
        "No se encontró config/sistema.json. Ejecute el comando desde la raíz del proyecto."
    )
