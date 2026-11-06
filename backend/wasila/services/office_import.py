"""Excel and Word tables to CSV (Wasila v1.0.0.0), so lead lists in any of the three formats
go through the one CSV import pipeline (mapping, preview, dedupe) in ``services/imports``.

- ``.xlsx``: every sheet with data becomes one table (formulas read as their saved values).
- ``.docx``: every table becomes one table; the first row is the header.
- ``.csv``: returned as is (UTF-8, with or without a BOM).

Nothing here writes to the database. Workbooks are read with ``read_only`` and macros are
never run (``.xlsm`` is refused).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final

from wasila.core.errors import ValidationFailed

MAX_ROWS: Final[int] = 5000
MAX_COLS: Final[int] = 60


@dataclass
class Table:
    name: str
    header: list[str]
    rows: int
    csv: str


def invalid(message: str) -> ValidationFailed:
    return ValidationFailed("file", message)


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == datetime.min.time() else v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _to_csv(name: str, grid: list[list[str]]) -> Table | None:
    # Drop empty rows and trailing empty columns; the first non-empty row is the header.
    grid = [r for r in grid if any(c.strip() for c in r)]
    if len(grid) < 2:
        return None
    width = max(
        (max((i for i, c in enumerate(r) if c.strip()), default=-1) + 1 for r in grid), default=0
    )
    width = min(width, MAX_COLS)
    if width == 0:
        return None
    grid = [(r + [""] * width)[:width] for r in grid[: MAX_ROWS + 1]]
    header = [h.strip() or f"Column {i + 1}" for i, h in enumerate(grid[0])]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(grid[1:])
    return Table(name=name, header=header, rows=len(grid) - 1, csv=buf.getvalue())


def from_xlsx(data: bytes) -> list[Table]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # zipfile, xml and openpyxl errors alike
        raise invalid("This is not a readable Excel (.xlsx) file.") from exc
    out = []
    try:
        for ws in wb.worksheets:
            grid = [
                [_cell(v) for v in row[:MAX_COLS]]
                for row in ws.iter_rows(max_row=MAX_ROWS + 50, values_only=True)
            ]
            t = _to_csv(ws.title, grid)
            if t is not None:
                out.append(t)
    finally:
        wb.close()
    return out


def from_docx(data: bytes) -> list[Table]:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:
        raise invalid("This is not a readable Word (.docx) file.") from exc
    out = []
    for i, table in enumerate(doc.tables, start=1):
        grid = [
            [c.text.strip() for c in row.cells[:MAX_COLS]] for row in table.rows[: MAX_ROWS + 1]
        ]
        t = _to_csv(f"Table {i}", grid)
        if t is not None:
            out.append(t)
    return out


def from_csv(data: bytes) -> list[Table]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    grid = list(csv.reader(io.StringIO(text)))
    t = _to_csv("CSV", grid)
    return [t] if t else []


def convert(filename: str, data: bytes) -> list[Table]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not data:
        raise invalid("The file is empty.")
    if ext == "xlsx":
        tables = from_xlsx(data)
    elif ext == "docx":
        tables = from_docx(data)
    elif ext in ("csv", "txt"):
        tables = from_csv(data)
    else:
        raise invalid(
            "Upload a .csv, .xlsx or .docx file (older .xls and .doc: save as the new format)."
        )
    if not tables:
        raise invalid("No table with a header row and data was found in this file.")
    return tables
