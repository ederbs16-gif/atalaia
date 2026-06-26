from __future__ import annotations

from datetime import date, timedelta


def calcular_periodo(tipo: str) -> tuple[date | None, date | None]:
    hoje = date.today()
    if tipo == "diario":
        return hoje, hoje
    if tipo == "semanal":
        return hoje - timedelta(days=6), hoje
    if tipo == "mensal":
        return hoje.replace(day=1), hoje
    return None, None
