from __future__ import annotations

import configparser
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.ini"

_DEFAULTS: dict[str, dict[str, str]] = {
    "interface": {
        "fonte_tamanho_geral": "11",
        "fonte_tamanho_pdv": "14",
        "fonte_tamanho_titulo": "16",
        "campo_altura_minima": "30",
    },
    "impressora": {
        "escpos_ativada": "false",
        "escpos_porta": "",
        "escpos_modelo": "",
    },
    "banco": {
        "host": "localhost",
        "porta": "3306",
        "usuario": "atalaia_app",
        "senha": "",
    },
    "backup": {
        "pasta_destino": "",
        "horario_automatico": "18:00",
        "backup_automatico": "true",
    },
    "sistema": {
        "mysqldump_path": "tools/mysqldump.exe",
    },
}


class ConfigLocal:
    _instance: "ConfigLocal | None" = None

    def __init__(self, path: Path | None = None):
        self._path = path or _CONFIG_PATH
        self._parser = configparser.ConfigParser()
        self._load()

    @classmethod
    def instancia(cls) -> "ConfigLocal":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self) -> None:
        if self._path.exists():
            self._parser.read(self._path, encoding="utf-8")
        for section, keys in _DEFAULTS.items():
            if not self._parser.has_section(section):
                self._parser.add_section(section)
            for key, val in keys.items():
                if not self._parser.has_option(section, key):
                    self._parser.set(section, key, val)
        self.save()

    def get(self, secao: str, chave: str, fallback: str = "") -> str:
        return self._parser.get(secao, chave, fallback=fallback)

    def set(self, secao: str, chave: str, valor: str) -> None:
        if not self._parser.has_section(secao):
            self._parser.add_section(secao)
        self._parser.set(secao, chave, valor)

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            self._parser.write(f)
