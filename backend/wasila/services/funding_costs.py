"""Funding costs (Wasila v1.0.0.0): use of funds, the funding tranches (SEIS/EIS, equity,
grants) and 48-month income and cost lines, with the KPIs investor updates quote.

The only writer of ``funding_cost_lines``. Money is whole currency units (``bigint``).
``kind``:

- ``funding``: money raised or planned (``amount``; ``tranche`` seis / eis / equity / grant).
- ``use_of_funds``: how the round is spent (``amount``, ``objective``).
- ``income`` / ``cost``: yearly lines ``y1``..``y4``, grouped (People, Direct, Operating …).

``import_workbook`` reads the two layouts Applied Biosciences uses (a "Use of funds" sheet
and a "Summary" P&L with Year 1..4 columns) or a plain sheet with the columns Kind, Group,
Name, Amount, Y1, Y2, Y3, Y4, Tranche, Objective.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.auth.principal import WorkspaceContext
from wasila.core.errors import NotFound, ValidationFailed
from wasila.models.room import FundingCostLine

KINDS: Final[tuple[str, ...]] = ("funding", "use_of_funds", "income", "cost")
TRANCHES: Final[tuple[str, ...]] = ("seis", "eis", "equity", "grant", "other")
YEARS: Final[tuple[str, ...]] = ("y1", "y2", "y3", "y4")
MAX_LINES: Final[int] = 500


def invalid(message: str, field: str = "body") -> ValidationFailed:
    return ValidationFailed(field, message)


def _money(v: Any, field: str) -> int:
    if v is None or v == "":
        return 0
    try:
        n = round(float(str(v).replace(",", "").replace("£", "").replace("$", "").strip()))
    except ValueError as exc:
        raise invalid(f"{field} must be a number.", field) from exc
    if abs(n) > 10**13:
        raise invalid(f"{field} is too large.", field)
    return int(n)


def _clean(fields: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "kind" in fields and fields["kind"] is not None:
        if fields["kind"] not in KINDS:
            raise invalid(f"kind must be one of: {', '.join(KINDS)}.", "kind")
        out["kind"] = fields["kind"]
    for k, n in (("grp", 80), ("name", 200)):
        if k in fields and fields[k] is not None:
            v = str(fields[k]).strip()
            if not 1 <= len(v) <= n:
                raise invalid(f"{k} must be 1 to {n} characters.", k)
            out[k] = v
    if fields.get("currency"):
        c = str(fields["currency"]).upper()
        if len(c) != 3 or not c.isalpha():
            raise invalid("currency must be a 3-letter code such as GBP, USD or SAR.", "currency")
        out["currency"] = c
    for k in ("amount", *YEARS):
        if k in fields:
            out[k] = _money(fields[k], k)
    if "tranche" in fields:
        t = fields["tranche"]
        if t not in (None, "", *TRANCHES):
            raise invalid(f"tranche must be one of: {', '.join(TRANCHES)}.", "tranche")
        out["tranche"] = t or None
    if "objective" in fields:
        out["objective"] = (str(fields["objective"] or "").strip()[:500]) or None
    if "position" in fields and fields["position"] is not None:
        out["position"] = int(fields["position"])
    if creating:
        for req in ("kind", "grp", "name"):
            if req not in out:
                raise invalid(f"{req} is required.", req)
    return out


async def list_lines(
    db: AsyncSession, ws: WorkspaceContext, *, kind: str | None = None
) -> list[FundingCostLine]:
    stmt = select(FundingCostLine).where(FundingCostLine.workspace_id == ws.workspace_id)
    if kind:
        stmt = stmt.where(FundingCostLine.kind == kind)
    stmt = stmt.order_by(FundingCostLine.kind, FundingCostLine.position, FundingCostLine.name)
    return list((await db.scalars(stmt)).all())


async def get_line(db: AsyncSession, ws: WorkspaceContext, line_id: UUID) -> FundingCostLine:
    row = await db.scalar(
        select(FundingCostLine).where(
            FundingCostLine.workspace_id == ws.workspace_id, FundingCostLine.id == line_id
        )
    )
    if row is None:
        raise NotFound("Cost line not found.")
    return row


async def create_line(
    db: AsyncSession, ws: WorkspaceContext, *, fields: dict[str, Any], now: datetime
) -> FundingCostLine:
    n = await db.scalar(
        select(func.count())
        .select_from(FundingCostLine)
        .where(FundingCostLine.workspace_id == ws.workspace_id)
    )
    if (n or 0) >= MAX_LINES:
        raise invalid(f"A workspace can have at most {MAX_LINES} cost lines.")
    clean = _clean(fields, creating=True)
    clean.setdefault("currency", ws.currency if len(ws.currency) == 3 else "GBP")
    if "position" not in clean:
        clean["position"] = int(n or 0)
    row = FundingCostLine(workspace_id=ws.workspace_id, created_at=now, updated_at=now, **clean)
    db.add(row)
    await db.flush()
    return row


async def update_line(
    db: AsyncSession, ws: WorkspaceContext, line_id: UUID, *, fields: dict[str, Any], now: datetime
) -> FundingCostLine:
    row = await get_line(db, ws, line_id)
    clean = _clean(fields, creating=False)
    for k, v in clean.items():
        setattr(row, k, v)
    if clean:
        row.updated_at = now
    await db.flush()
    return row


async def delete_line(db: AsyncSession, ws: WorkspaceContext, line_id: UUID) -> None:
    row = await get_line(db, ws, line_id)
    await db.execute(
        delete(FundingCostLine).where(
            FundingCostLine.workspace_id == ws.workspace_id, FundingCostLine.id == row.id
        )
    )
    await db.flush()


def summarize(lines: list[FundingCostLine]) -> dict[str, Any]:
    """Totals, the use-of-funds split, the SEIS/EIS split and simple KPIs."""
    by = {k: [x for x in lines if x.kind == k] for k in KINDS}
    funding = sum(x.amount for x in by["funding"])
    use = sum(x.amount for x in by["use_of_funds"])
    income = {y: sum(getattr(x, y) for x in by["income"]) for y in YEARS}
    costs = {y: sum(getattr(x, y) for x in by["cost"]) for y in YEARS}
    groups: dict[str, dict[str, int]] = {}
    for x in by["cost"]:
        g = groups.setdefault(x.grp, dict.fromkeys(YEARS, 0))
        for y in YEARS:
            g[y] += getattr(x, y)
    net = {y: income[y] - costs[y] for y in YEARS}
    # Cash runway from the funding: months until the cumulative net burn uses it up.
    cash, months = funding, 0
    for y in YEARS:
        monthly = net[y] / 12
        for _ in range(12):
            if cash + monthly < 0:
                break
            cash += monthly
            months += 1
        else:
            continue
        break
    tranches: dict[str, int] = {}
    for x in by["funding"]:
        key = x.tranche or "other"
        tranches[key] = tranches.get(key, 0) + x.amount
    first_year_burn = max(costs["y1"] - income["y1"], 0)
    return {
        "currency": lines[0].currency if lines else None,
        "funding_total": funding,
        "use_of_funds_total": use,
        "unallocated": funding - use,
        "tranches": tranches,
        "use_of_funds": [
            {
                "id": str(x.id),
                "name": x.name,
                "amount": x.amount,
                "pct": round(100 * x.amount / use, 1) if use else 0.0,
                "objective": x.objective,
            }
            for x in by["use_of_funds"]
        ],
        "income": income,
        "costs": costs,
        "cost_groups": groups,
        "net": net,
        "total_costs_48m": sum(costs.values()),
        "total_income_48m": sum(income.values()),
        "kpis": {
            "monthly_burn_y1": round(first_year_burn / 12),
            "runway_months": months if months < 48 else None,
            "runway_beyond_48m": months >= 48,
            "funding_gap_48m": max(-(funding + sum(net.values())), 0),
        },
    }


# --- merge fields for investor updates --------------------------------------------------------

MERGE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("raise_total", "Total raise"),
    ("seis", "SEIS tranche"),
    ("eis", "EIS tranche"),
    ("use_of_funds", "Use of funds (top three)"),
    ("monthly_burn", "Monthly burn, year 1"),
    ("runway", "Runway"),
    ("funding_gap", "Funding gap over 48 months"),
)

_SYMBOL: Final[dict[str, str]] = {"GBP": "\u00a3", "USD": "$", "EUR": "\u20ac"}


def money_text(amount: int, currency: str | None) -> str:
    """Whole units with thousands separators: \u00a32,000,000, $1,500, SAR 750,000."""
    cur = (currency or "").upper()
    sym = _SYMBOL.get(cur)
    sign = "-" if amount < 0 else ""
    if sym:
        return f"{sign}{sym}{abs(amount):,}"
    return f"{sign}{cur} {abs(amount):,}".strip() if cur else f"{amount:,}"


def merge_values(lines: list[FundingCostLine]) -> dict[str, str]:
    """The funding figures an investor update can quote, as text ({raise_total}, {runway} ...).

    Every field is present; a figure the workspace has not entered is an empty string, so a
    template never shows a raw ``{placeholder}``.
    """
    out = dict.fromkeys((k for k, _ in MERGE_FIELDS), "")
    if not lines:
        return out
    sm = summarize(lines)
    cur = sm["currency"]
    if sm["funding_total"]:
        out["raise_total"] = money_text(sm["funding_total"], cur)
    for key in ("seis", "eis"):
        if sm["tranches"].get(key):
            out[key] = money_text(sm["tranches"][key], cur)
    top = sorted(sm["use_of_funds"], key=lambda x: -x["amount"])[:3]
    out["use_of_funds"] = ", ".join(f"{x['name']} {x['pct']:g}%" for x in top)
    if sm["costs"]["y1"] or sm["income"]["y1"]:
        out["monthly_burn"] = money_text(sm["kpis"]["monthly_burn_y1"], cur)
        if sm["kpis"]["runway_beyond_48m"]:
            out["runway"] = "more than 48 months"
        elif sm["kpis"]["runway_months"] is not None:
            m = sm["kpis"]["runway_months"]
            out["runway"] = f"{m} month" + ("" if m == 1 else "s")
        out["funding_gap"] = money_text(sm["kpis"]["funding_gap_48m"], cur)
    return out


# --- workbook import ----------------------------------------------------------------------------

_SKIP_PREFIXES: Final[tuple[str, ...]] = (
    "total",
    "gross",
    "ebitda",
    "net profit",
    "customer revenue",
    "corporation tax",
    "check",
)


def _num(v: Any) -> int:
    if isinstance(v, (int, float)):
        return round(v)
    return 0


def parse_workbook(data: bytes) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise invalid("This is not a readable Excel (.xlsx) file.", "file") from exc
    out: list[dict[str, Any]] = []
    try:
        names = {ws.title.lower(): ws for ws in wb.worksheets}
        plain = names.get("wasila costs")
        if plain is not None:
            return _plain_sheet(plain)
        if "use of funds" in names:
            out += _use_of_funds(names["use of funds"])
        if "summary" in names:
            out += _summary(names["summary"])
    finally:
        wb.close()
    if not out:
        raise invalid(
            'No cost data found. Use a "Use of funds" or "Summary" sheet, or a sheet named '
            '"Wasila costs" with Kind, Group, Name, Amount, Y1..Y4, Tranche, Objective.',
            "file",
        )
    return out[:MAX_LINES]


def _rows(ws: Any) -> list[list[Any]]:
    return [list(r) for r in ws.iter_rows(max_row=400, values_only=True)]


def _use_of_funds(ws: Any) -> list[dict[str, Any]]:
    out = []
    started = False
    for r in _rows(ws):
        cells = [c for c in r]
        label = str(cells[0]).strip() if cells and cells[0] is not None else ""
        if label.lower() == "category":
            started = True
            continue
        if not started or not label:
            continue
        amount = _num(cells[1]) if len(cells) > 1 else 0
        low = label.lower()
        if low == "total":
            continue
        if low.startswith("seis"):
            out.append(
                {
                    "kind": "funding",
                    "grp": "Round",
                    "name": label,
                    "amount": amount,
                    "tranche": "seis",
                }
            )
        elif low.startswith("eis"):
            out.append(
                {
                    "kind": "funding",
                    "grp": "Round",
                    "name": label,
                    "amount": amount,
                    "tranche": "eis",
                }
            )
        elif amount:
            obj = cells[3] if len(cells) > 3 else None
            out.append(
                {
                    "kind": "use_of_funds",
                    "grp": "Use of funds",
                    "name": label,
                    "amount": amount,
                    "objective": str(obj).strip()[:500] if obj else None,
                }
            )
    return out


def _summary(ws: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cols: list[int] = []
    section = "income"
    group = "Income"
    for r in _rows(ws):
        texts = [str(c).strip() if c is not None else "" for c in r]
        if not cols:
            cols = [i for i, t in enumerate(texts) if t.lower().startswith("year ")][:4]
            continue
        label = texts[0]
        if not label:
            continue
        low = label.lower()
        if low.startswith("cash and balance") or low.startswith("people and volume"):
            break
        if low == "total income":
            section, group = "cost", "Direct costs"
            continue
        if low == "total direct costs":
            group = "People"
            continue
        if low == "total people costs":
            group = "Operating"
            continue
        if low.startswith(_SKIP_PREFIXES) or low in ("profit and loss",):
            continue
        values = [_num(r[i]) if i < len(r) else 0 for i in cols]
        if not any(values):
            continue
        line: dict[str, Any] = {"kind": section, "grp": group, "name": label[:200]}
        for y, v in zip(YEARS, values + [0] * (4 - len(values)), strict=False):
            line[y] = v
        if section == "cost" and low.startswith("people:"):
            line["grp"] = "People"
            line["name"] = label.split(":", 1)[1].strip().capitalize() or label
        out.append(line)
    return out


def _plain_sheet(ws: Any) -> list[dict[str, Any]]:
    rows = _rows(ws)
    if not rows:
        return []
    header = [str(h or "").strip().lower() for h in rows[0]]
    idx = {h: i for i, h in enumerate(header)}
    out = []
    for r in rows[1:]:

        def get(name: str, r: list[Any] = r) -> Any:
            i = idx.get(name)
            return r[i] if i is not None and i < len(r) else None

        if not get("name"):
            continue
        out.append(
            {
                "kind": str(get("kind") or "cost").strip().lower(),
                "grp": str(get("group") or "General").strip(),
                "name": str(get("name")).strip(),
                "amount": get("amount"),
                "y1": get("y1"),
                "y2": get("y2"),
                "y3": get("y3"),
                "y4": get("y4"),
                "tranche": (str(get("tranche")).strip().lower() if get("tranche") else None),
                "objective": get("objective"),
            }
        )
    return out


async def import_workbook(
    db: AsyncSession,
    ws: WorkspaceContext,
    data: bytes,
    *,
    currency: str,
    replace: bool,
    now: datetime,
) -> list[FundingCostLine]:
    parsed = parse_workbook(data)
    cleaned = [_clean({**p, "currency": currency}, creating=True) for p in parsed]
    if replace:
        await db.execute(
            delete(FundingCostLine).where(FundingCostLine.workspace_id == ws.workspace_id)
        )
    rows = []
    for pos, c in enumerate(cleaned):
        c.setdefault("position", pos)
        row = FundingCostLine(workspace_id=ws.workspace_id, created_at=now, updated_at=now, **c)
        db.add(row)
        rows.append(row)
    await db.flush()
    return rows
