from __future__ import annotations

import subprocess
import zipfile
from datetime import datetime, date, time as dtime
from pathlib import Path

import bcrypt as _bcrypt
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from atalaia.config_local import ConfigLocal
from atalaia import config as db_config

_SENHA_HASH = b"$2b$12$kYJBo0/3RPse8HUeaJNRAeaTUoVq.4VoTGaPJeWkiFic9VVnHquE6"


def verificar_senha_programador(senha: str) -> bool:
    try:
        return _bcrypt.checkpw(senha.encode("utf-8"), _SENHA_HASH)
    except Exception:
        return False


def gerar_backup() -> str:
    cfg = ConfigLocal.instancia()
    pasta = cfg.get("backup", "pasta_destino", "").strip()
    if not pasta:
        raise ValueError("Pasta de destino do backup não configurada em config.ini.")

    pasta_path = Path(pasta)
    pasta_path.mkdir(parents=True, exist_ok=True)

    mysqldump_path = cfg.get("sistema", "mysqldump_path", "tools/mysqldump.exe")
    if not Path(mysqldump_path).exists():
        raise FileNotFoundError(
            f"mysqldump não encontrado em '{mysqldump_path}'. "
            "Configure o caminho correto em config.ini [sistema] mysqldump_path."
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_sql = f"atalaia_backup_{ts}.sql"
    nome_zip = f"atalaia_backup_{ts}.sql.zip"
    caminho_sql = pasta_path / nome_sql
    caminho_zip = pasta_path / nome_zip

    host = db_config.DB_HOST or "localhost"
    porta = db_config.DB_PORT or "3306"
    usuario = db_config.DB_USER or ""
    senha = db_config.DB_PASSWORD or ""
    db_name = db_config.DB_NAME or ""

    cmd = [
        mysqldump_path,
        f"-h{host}",
        f"-P{porta}",
        f"-u{usuario}",
        f"-p{senha}",
        db_name,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Falha no mysqldump: {result.stderr[:500]}")

    caminho_sql.write_text(result.stdout, encoding="utf-8")

    with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(caminho_sql, nome_sql)

    caminho_sql.unlink()
    return str(caminho_zip)


def restaurar_backup(caminho_zip: str, senha_programador: str) -> None:
    if not verificar_senha_programador(senha_programador):
        raise PermissionError("Senha do programador incorreta.")

    caminho = Path(caminho_zip)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_zip}")

    cfg = ConfigLocal.instancia()
    mysqldump_path = cfg.get("sistema", "mysqldump_path", "tools/mysqldump.exe")
    mysql_path = Path(mysqldump_path).parent / "mysql.exe"
    if not mysql_path.exists():
        mysql_path = Path("mysql")

    host = db_config.DB_HOST or "localhost"
    porta = db_config.DB_PORT or "3306"
    usuario = db_config.DB_USER or ""
    senha = db_config.DB_PASSWORD or ""
    db_name = db_config.DB_NAME or ""

    with zipfile.ZipFile(caminho, "r") as zf:
        nome_sql = zf.namelist()[0]
        sql_bytes = zf.read(nome_sql)

    cmd = [
        str(mysql_path),
        f"-h{host}",
        f"-P{porta}",
        f"-u{usuario}",
        f"-p{senha}",
        db_name,
    ]
    result = subprocess.run(cmd, input=sql_bytes, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Falha na restauração: {result.stderr.decode()[:500]}")


def agendar_backup_automatico(app: QApplication) -> QTimer:
    cfg = ConfigLocal.instancia()

    def _calcular_ms_ate_18h() -> int:
        horario_str = cfg.get("backup", "horario_automatico", "18:00")
        try:
            h, m = (int(x) for x in horario_str.split(":"))
        except Exception:
            h, m = 18, 0
        agora = datetime.now()
        alvo = agora.replace(hour=h, minute=m, second=0, microsecond=0)
        if alvo <= agora:
            alvo = alvo.replace(day=alvo.day + 1)
        delta = alvo - agora
        return max(int(delta.total_seconds() * 1000), 1000)

    timer = QTimer(app)
    timer.setSingleShot(True)

    def _disparar():
        ativo = cfg.get("backup", "backup_automatico", "true").lower() == "true"
        if ativo:
            try:
                gerar_backup()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error("Backup automático falhou: %s", e)
        timer.setInterval(_calcular_ms_ate_18h())
        timer.start()

    timer.timeout.connect(_disparar)
    timer.setInterval(_calcular_ms_ate_18h())
    timer.start()
    return timer
