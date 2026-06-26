from __future__ import annotations

import math
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import QFileDialog, QWidget


def imprimir_relatorio(widget: QWidget, titulo: str) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setDocName(titulo)
    dlg = QPrintDialog(printer, widget)
    dlg.setWindowTitle(f"Imprimir — {titulo}")
    if dlg.exec() != QPrintDialog.Accepted:
        return
    painter = QPainter(printer)
    widget.render(painter)
    painter.end()


def exportar_pdf(widget: QWidget, titulo: str, caminho: str | None = None) -> None:
    if caminho is None:
        sugestao = f"{titulo.replace(' ', '_')}_{date.today()}.pdf"
        caminho, _ = QFileDialog.getSaveFileName(
            widget,
            f"Exportar PDF — {titulo}",
            sugestao,
            "PDF (*.pdf)",
        )
    if not caminho:
        return
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(caminho)
    printer.setDocName(titulo)
    painter = QPainter(printer)
    widget.render(painter)
    painter.end()


def exportar_sugestao_compra(itens: list[dict], parent: QWidget | None = None) -> None:
    sugestao = f"sugestao_compra_{date.today()}.pdf"
    caminho, _ = QFileDialog.getSaveFileName(
        parent,
        "Exportar Sugestão de Compra",
        sugestao,
        "PDF (*.pdf)",
    )
    if not caminho:
        return

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(caminho)
    printer.setDocName("Sugestão de Compra")

    painter = QPainter(printer)
    painter.setFont(painter.font())
    page_rect = printer.pageRect(QPrinter.DevicePixel)
    x, y = int(page_rect.x()) + 40, int(page_rect.y()) + 60
    line_h = 60

    painter.drawText(x, y, f"Sugestão de Compra — {date.today().strftime('%d/%m/%Y')}")
    y += line_h * 2

    cabecalho = f"{'Produto':<40} {'Cat':<20} {'Atual':>8} {'Mínimo':>8} {'Sugerido':>10}"
    painter.drawText(x, y, cabecalho)
    y += line_h

    for item in itens:
        margem = math.ceil((item["estoque_minimo"] - item["estoque_atual"]) * 1.2)
        sugerido = max(margem, 1)
        linha = (
            f"{item['nome'][:38]:<40}"
            f" {item['categoria'][:18]:<20}"
            f" {item['estoque_atual']:>8}"
            f" {item['estoque_minimo']:>8}"
            f" {sugerido:>10}"
        )
        painter.drawText(x, y, linha)
        y += line_h

        if y > page_rect.height() - 80:
            printer.newPage()
            y = int(page_rect.y()) + 60

    painter.end()
