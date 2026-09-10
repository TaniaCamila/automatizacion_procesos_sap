from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import RESOURCES_DIR


class Settings:
    """
    Carga los archivos de configuración ubicados en data/resources.
    """

    def __init__(self) -> None:
        self.columnas = self._load_yaml("columnas.yml")
        self.sociedades = self._load_yaml("sociedades.yml")
        self.monedas = self._load_yaml("monedas.yml")
        self.conceptos = self._load_yaml("conceptos.yml")

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        path: Path = RESOURCES_DIR / filename

        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        return data if isinstance(data, dict) else {}
