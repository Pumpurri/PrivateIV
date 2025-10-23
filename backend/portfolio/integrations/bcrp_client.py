import io
import re
import csv
import json
from decimal import Decimal
from datetime import datetime, time
from typing import Tuple

import requests

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


BCRP_BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"


def _fetch(url: str) -> str:
    r = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": "privateiv/1.0 (+bcrp)",
            "Accept": "application/json,text/csv,text/plain,*/*",
        },
    )
    r.raise_for_status()
    return r.text.lstrip("\ufeff")


def _ensure_json(raw: str):
    s = raw.strip()
    if not (s.startswith("{") or s.startswith("[")):
        raise ValueError("Endpoint did not return JSON (maybe HTML/redirect).")
    return json.loads(s)


def _has_number(v) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    return s not in ("", "-", "NaN", "null", "None")


def _to_float(v) -> float:
    return float(str(v).replace(",", ".").strip())


def _norm_period_iso(s: str) -> str:
    """Normalize many BCRP date shapes to ISO YYYY-MM-DD (or YYYY-MM)."""
    s = (s or "").strip()
    m = re.match(r"^(\d{1,2})\.(\w{3})\.(\d{2,4})$", s, flags=re.IGNORECASE)
    if m:
        d, mon, y = m.groups()
        mon_map = {
            'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,
            'jul':7,'ago':8,'set':9,'sep':9,'oct':10,'nov':11,'dic':12
        }
        mm = mon_map.get(mon.lower())
        yy = int(y); yy = 2000 + yy if yy < 100 else yy
        if mm:
            return f"{yy:04d}-{mm:02d}-{int(d):02d}"
    s = s.replace("/", "-")
    parts = [p for p in s.split("-") if p]
    if len(parts) == 3:
        a, b, c = parts
        if len(a) == 4 and a.isdigit():  # YYYY-MM-DD
            y, m, d = int(a), int(b), int(c)
        elif len(c) == 4 and c.isdigit():  # DD-MM-YYYY
            d, m, y = int(a), int(b), int(c)
        else:
            ai, bi, ci = int(a), int(b), int(c)
            if ci >= 1900:
                d, m, y = ai, bi, ci
            else:
                y, m, d = ai, bi, ci
        return f"{y:04d}-{m:02d}-{d:02d}"
    if len(parts) == 2:
        a, b = parts
        if len(a) == 4 and a.isdigit():
            y, m = int(a), int(b)
        elif len(b) == 4 and b.isdigit():
            y, m = int(b), int(a)
        else:
            return s
        return f"{y:04d}-{m:02d}"
    return s


def _parse_bcrp_json_latest(payload) -> Tuple[str, float]:
    # 1) dataset.data -> [[period, value], ...]
    try:
        rows = payload["data"]["dataset"]["data"]
        for period, val, *rest in reversed(rows):
            if _has_number(val):
                return _norm_period_iso(period), _to_float(val)
    except Exception:
        pass
    # 2) series[0].data -> [{fecha/periodo/name, valor/value}, ...]
    try:
        rows = payload["series"][0]["data"]
        for obs in reversed(rows):
            period = obs.get("fecha") or obs.get("periodo") or obs.get("name")
            val = obs.get("valor") or obs.get("value")
            if _has_number(val):
                return _norm_period_iso(period), _to_float(val)
    except Exception:
        pass
    # 3) periods: [{name, values:[...]}]
    try:
        rows = payload["periods"]
        for p in reversed(rows):
            vals = p.get("values") or []
            if vals and _has_number(vals[0]):
                return _norm_period_iso(p.get("name")), _to_float(vals[0])
    except Exception:
        pass
    # Fallback: regex
    flat = json.dumps(payload, ensure_ascii=False)
    m = re.findall(r'(\b20\d{2}[-/]\d{1,2}(?:[-/]\d{1,2})?)\D+([0-9]+(?:[.,][0-9]+)?)', flat)
    if m:
        period, val = m[-1]
        return _norm_period_iso(period), _to_float(val)
    raise ValueError("Unrecognized BCRP JSON schema")


def _parse_bcrp_csv_latest(raw: str) -> Tuple[str, float]:
    buf = io.StringIO(raw.lstrip("\ufeff"))
    reader = csv.reader(buf)
    rows = [r for r in reader if r and any(c.strip() for c in r)]
    if rows and not re.match(r"^\d{4}[-/]\d{1,2}([-/]\d{1,2})?$", (rows[0][0] or "").strip()):
        rows = rows[1:]
    for row in reversed(rows):
        if len(row) < 2:
            continue
        period, val = row[0].strip(), row[1].strip()
        val = val.replace(",", ".")
        if _has_number(val):
            try:
                return _norm_period_iso(period), float(val)
            except Exception:
                continue
    raise ValueError("Could not parse CSV latest observation")


def get_latest(series_code: str) -> Tuple[str, Decimal]:
    url_json = f"{BCRP_BASE}/{series_code}/json"
    url_csv = f"{BCRP_BASE}/{series_code}/csv"
    try:
        raw = _fetch(url_json)
        payload = _ensure_json(raw)
        d, v = _parse_bcrp_json_latest(payload)
    except Exception:
        raw_csv = _fetch(url_csv)
        d, v = _parse_bcrp_csv_latest(raw_csv)
    return d, Decimal(str(v))


def _series_chain(intraday: bool, direction: str):
    # direction: 'compra' for USD->PEN, 'venta' for PEN->USD
    if direction not in ("compra", "venta"):
        raise ValueError("direction must be 'compra' or 'venta'")
    if intraday:
        compra = ["PD04643PD", "PD04645PD", "PD04639PD"]
        venta  = ["PD04644PD", "PD04646PD", "PD04640PD"]
    else:
        compra = ["PD04645PD", "PD04643PD", "PD04639PD"]
        venta  = ["PD04646PD", "PD04644PD", "PD04640PD"]
    return compra if direction == "compra" else venta


def _today_prefix() -> str:
    try:
        today = datetime.now(ZoneInfo("America/Lima")).date() if ZoneInfo else datetime.now().date()
    except Exception:
        today = datetime.now().date()
    return today.strftime("%Y-%m-%d")


def resolve_latest_auto(mode: str = 'auto', direction: str = 'compra') -> Tuple[str, str, Decimal]:
    # Decide intraday vs cierre: default cierre; intraday only 11:05–13:29
    if mode == 'intraday':
        intraday = True
        expect_today = True
    elif mode == 'cierre':
        intraday = False
        try:
            now = datetime.now(ZoneInfo("America/Lima")).time() if ZoneInfo else datetime.now().time()
        except Exception:
            now = datetime.now().time()
        expect_today = now >= time(13, 30)
    else:
        try:
            now = datetime.now(ZoneInfo("America/Lima")).time() if ZoneInfo else datetime.now().time()
        except Exception:
            now = datetime.now().time()
        intraday = (now >= time(11, 5)) and (now < time(13, 30))
        expect_today = intraday or (now >= time(13, 30))

    chain = _series_chain(intraday, direction)
    last_err = None
    prefix = _today_prefix()
    for code in chain:
        try:
            d, v = get_latest(code)
            if expect_today and isinstance(d, str) and d and not d.startswith(prefix):
                continue
            return code, d, v
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise RuntimeError("No series produced a value")

