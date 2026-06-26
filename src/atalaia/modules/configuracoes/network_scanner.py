from __future__ import annotations

import socket
import threading

from PySide6.QtCore import QThread, Signal


def _get_subnet() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ".".join(ip.split(".")[:3])
    except Exception:
        return "192.168.1"


def _testa_porta(ip: str, porta: int, timeout: float) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        conectou = sock.connect_ex((ip, porta)) == 0
        sock.close()
        return conectou
    except Exception:
        return False


def scan_mysql_servers(timeout: float = 0.5) -> list[str]:
    subnet = _get_subnet()
    encontrados: list[str] = []
    lock = threading.Lock()
    threads: list[threading.Thread] = []

    def check(ip: str) -> None:
        if _testa_porta(ip, 3306, timeout):
            with lock:
                encontrados.append(ip)

    for i in range(1, 255):
        t = threading.Thread(target=check, args=(f"{subnet}.{i}",), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=timeout + 1.0)

    return sorted(encontrados)


class NetworkScanner(QThread):
    resultado = Signal(list)

    def __init__(self, timeout: float = 0.5, parent=None):
        super().__init__(parent)
        self._timeout = timeout

    def run(self) -> None:
        ips = scan_mysql_servers(self._timeout)
        self.resultado.emit(ips)
