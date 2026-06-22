#!/usr/bin/env python3
"""
PreToolUse hook — bloqueia comandos Alembic destrutivos.

Recebe JSON via stdin no formato padrão de hooks do Claude Code:
  {"tool_name": "Bash", "tool_input": {"command": "..."}, ...}

Cobre:
  - CLI: alembic upgrade (sem --sql), alembic downgrade, alembic stamp
  - API inline: python -c "from alembic import command; command.upgrade(...)"
               python -c "alembic.command.upgrade(...)"

NÃO cobre: arquivo .py separado criado e depois executado via
  python script_temp.py chamando alembic.command.*
  Esse caso depende da restrição explícita no system prompt e da revisão
  humana do diff antes de confiar em qualquer correção proposta por este agente.

Exit 0 = permitido (sem saída em stdout)
Exit 2 = bloqueado (mensagem explicativa no stderr)
"""
import json
import re
import sys

sys.stderr.reconfigure(encoding="utf-8")


def main() -> None:
    data = sys.stdin.read()
    try:
        hook_input = json.loads(data)
    except json.JSONDecodeError:
        return

    command = hook_input.get("tool_input", {}).get("command", "")

    BLOCKED = [
        (r"alembic\s+upgrade(?!.*--sql)", "alembic upgrade (sem --sql)"),
        (r"alembic\s+downgrade\b", "alembic downgrade"),
        (r"alembic\s+stamp\b", "alembic stamp"),
        # API do Alembic chamada diretamente (cobre alembic.command.upgrade( e command.upgrade( após import).
        # NÃO cobre arquivo .py separado criado e depois executado — esse caso depende do system prompt e revisão humana.
        (r"\bcommand\s*\.\s*(upgrade|stamp)\s*\(", "chamada direta à API do Alembic (command.upgrade/stamp)"),
    ]

    for pattern, label in BLOCKED:
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            sys.stderr.write(
                f"[ALEMBIC GUARD] BLOQUEADO: '{label}' detectado.\n"
                f"Este agente não pode aplicar migrations ao banco.\n"
                f"Diagnóstico permitido: alembic check | history | current | upgrade head --sql\n"
                f"Comando bloqueado: {command!r}\n"
            )
            sys.exit(2)


if __name__ == "__main__":
    main()
