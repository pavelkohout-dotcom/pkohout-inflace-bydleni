"""Stahování vstupních dat: ČSÚ (CPI), Eurostat/ČSÚ (HPI), ČNB ARAD (sazby).

Každá funkce vrací pandas objekt s měsíčním/čtvrtletním PeriodIndex.
Odpovědi se ukládají do složky data/ jako cache; chybí-li ARAD klíč nebo je ARAD
nedostupný, použije se poslední uložená cache a skript na to upozorní.
"""
import io
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import requests

CSU_URL = "https://data.csu.gov.cz/opendata/sady/CEN0101E/distribuce/csv"
EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hpi_q"
    "?format=JSON&lang=EN&geo=CZ&unit=I15_Q&purchase=DW_EXST"
)
ARAD_BASE = "https://www.cnb.cz/aradb/api/v1"
HEADERS = {"User-Agent": "Mozilla/5.0 (pkohout-inflace-bydleni; +https://www.pkohout.com)"}

CSU_COLS = ["ukaz", "ukaz_k", "typ", "typ_k", "odd", "odd_k", "skup", "skup_k",
            "dom", "dom_k", "uz", "uz_k", "mes", "mes_k", "hod", "mj", "mjs"]


def _warn(msg):
    print(f"VAROVÁNÍ: {msg}", file=sys.stderr)


def fetch_cpi(codes, data_dir):
    """Měsíční bazické indexy spotřebitelských cen podle tříd/oddílů (domácnosti celkem)."""
    cache = os.path.join(data_dir, "cpi_levels.csv")
    try:
        r = requests.get(CSU_URL, headers=HEADERS, timeout=300)
        r.raise_for_status()
        df = pd.read_csv(io.BytesIO(r.content), dtype=str)
        if df.shape[1] != len(CSU_COLS):
            raise RuntimeError(f"ČSÚ změnil strukturu CSV ({df.shape[1]} sloupců místo {len(CSU_COLS)})")
        df.columns = CSU_COLS
        df = df[(df.dom_k == "0") & df.mes_k.str.match(r"^\d{4}-\d{2}$", na=False)]
        # nejdelší dostupná bazická řada (např. "Bazický index (2015 = 100)")
        bases = sorted(t for t in df.typ.unique() if re.match(r"^Bazický index \(\d{4} = 100\)$", t))
        if not bases:
            raise RuntimeError("V datech ČSÚ chybí bazický index")
        best = max(bases, key=lambda t: (df[(df.typ == t) & (df.odd_k == "0")].shape[0], -int(re.findall(r"\d{4}", t)[0])))
        d = df[df.typ == best].copy()
        d["hod"] = d.hod.astype(float)
        d["code"] = np.where(d.skup_k.notna(), d.skup_k, d.odd_k)
        p = d[d.code.isin(codes)].pivot_table(index="mes_k", columns="code", values="hod", aggfunc="first")
        p.index = pd.PeriodIndex(p.index, freq="M")
        p = p.sort_index()
        missing = [c for c in codes if c not in p.columns]
        if missing:
            raise RuntimeError(f"V datech ČSÚ chybí kódy {missing}")
        p.to_csv(cache)
        print(f"CPI: {p.index.min()} až {p.index.max()} (řada: {best})")
        return p
    except Exception as e:  # noqa: BLE001
        _warn(f"CPI se nepodařilo stáhnout ({e}); používám cache")
        p = pd.read_csv(cache, index_col=0)
        p.index = pd.PeriodIndex(p.index, freq="M")
        return p


def fetch_hpi(data_dir):
    """Čtvrtletní index cen starších bytů (HPI, 2015 = 100), zdroj ČSÚ přes Eurostat."""
    cache = os.path.join(data_dir, "hpi_existing_q.csv")
    try:
        r = requests.get(EUROSTAT_URL, headers=HEADERS, timeout=60)
        r.raise_for_status()
        j = r.json()
        t = j["dimension"]["time"]["category"]["index"]
        inv = {v: k for k, v in t.items()}
        s = pd.Series({inv[int(k)]: float(v) for k, v in j["value"].items()}).sort_index()
        s.index = pd.PeriodIndex(s.index.str.replace("-", ""), freq="Q")
        s.to_csv(cache, header=["hpi"])
        print(f"HPI: {s.index.min()} až {s.index.max()}")
        return s
    except Exception as e:  # noqa: BLE001
        _warn(f"HPI se nepodařilo stáhnout ({e}); používám cache")
        s = pd.read_csv(cache, index_col=0).iloc[:, 0]
        s.index = pd.PeriodIndex(s.index, freq="Q")
        return s


def fetch_rates(cfg, data_dir, api_key=None):
    """Sazby z úvěrů na bydlení (ČNB ARAD): nové čisté úvěry, všechny nové obchody, zůstatky."""
    cache = os.path.join(data_dir, "arad_rates.csv")
    ids = cfg["arad"]
    names = {ids["new_net_rate"]: "r_new_net", ids["new_all_rate"]: "r_new_all", ids["stock_rate"]: "r_stock"}
    api_key = api_key or os.environ.get("ARAD_API_KEY")
    if not api_key:
        _warn("ARAD_API_KEY není nastaven; používám cache sazeb")
    else:
        try:
            today = pd.Timestamp.today().strftime("%Y%m%d")
            r = requests.get(
                f"{ARAD_BASE}/data-trans",
                params={"api_key": api_key, "lang": "CS", "indicator_id_list": ",".join(names),
                        "period_from": "20040101", "period_to": today},
                headers=HEADERS, timeout=120)
            if "json" in r.headers.get("content-type", ""):
                raise RuntimeError(r.json().get("message", {}).get("cs", r.text[:200]))
            r.raise_for_status()
            d = pd.read_csv(io.StringIO(r.content.decode("cp1250")), sep=";", decimal=",")
            d["m"] = pd.PeriodIndex(pd.to_datetime(d["period"].astype(str), format="%Y%m%d"), freq="M")
            d = d.set_index("m").drop(columns="period").sort_index().rename(columns=names)
            d = d[list(names.values())]
            d.to_csv(cache)
            print(f"ARAD: {d.dropna(how='all').index.min()} až {d.dropna(how='all').index.max()}")
            return d
        except Exception as e:  # noqa: BLE001
            _warn(f"ARAD se nepodařilo stáhnout ({e}); používám cache sazeb")
    d = pd.read_csv(cache, index_col=0)
    d.index = pd.PeriodIndex(d.index, freq="M")
    return d
