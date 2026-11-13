"""Měsíční aktualizace: stáhne data, spočítá indexy, zapíše docs/data.json a grafy.

Spuštění:  python src/update.py
Proměnná prostředí ARAD_API_KEY (klíč ČNB ARAD) se nikdy nezapisuje do souborů.
"""
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import fetch  # noqa: E402
import model  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")


def r5(s):
    return [None if pd.isna(v) else round(float(v), 5) for v in s]


def main():
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    codes = ["0"] + list(cfg["weights_2024_promile"])
    cpi = fetch.fetch_cpi(codes, DATA)
    hpi_q = fetch.fetch_hpi(DATA)
    rates = fetch.fetch_rates(cfg, DATA)

    res = model.build(cpi, hpi_q, rates, cfg)
    H = cfg["default_housing_share"]
    idx = res["idx"]

    # kontrola věrnosti přepočtu oficiálního CPI (meziroční změny, od roku 2024)
    off = res["cpi_official"]
    rep = res["cpi_replica"]
    yo = (off / off.shift(12) - 1) * 100
    yr = (rep / rep.shift(12) - 1) * 100
    err = (yr - yo).loc["2024-01":].dropna()

    data = {
        "meta": {
            "aktualizovano": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "posledni_mesic": str(idx[-1]),
            "posledni_cpi": str(cpi.index.max()),
            "posledni_sazby": str(rates["r_new_net"].dropna().index.max()),
            "posledni_hpi_ctvrtleti": str(hpi_q.index.max()),
            "hpi_odhad_od": None if res["hpi_est_from"] is None else str(res["hpi_est_from"]),
            "referencni_obdobi": list(res["ref_period"]),
            "vychozi_podil_bydleni": H,
            "splatnost_let": cfg["mortgage_term_years"],
            "chyba_prepoctu_cpi_pb": {"mae_2024_plus": round(float(err.abs().mean()), 3),
                                      "max_2024_plus": round(float(err.abs().max()), 3)},
        },
        "mesice": [str(p) for p in idx],
        "n": r5(res["n"]),
        "cpi_replika": r5(res["cpi_replica"]),
        "cpi_oficialni": r5(res["cpi_official"]),
        "hc": {k: r5(v) for k, v in res["hc"].items()},
        "rozklad_kupujici": {k: r5(v) for k, v in res["parts"].items()},
        "sazby": {"nove_uvery_pct": r5(res["r_new"]), "zustatky_pct": r5(res["r_stock"])},
        "souhrn_vychozi": model.summarize(res, H),
    }
    os.makedirs(DOCS, exist_ok=True)
    out = os.path.join(DOCS, "data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Zapsáno {out}; poslední měsíc {idx[-1]}; souhrn: {data['souhrn_vychozi']}")

    try:
        import chart  # noqa: WPS433
        chart.render(res, H, DOCS)
    except ImportError:
        print("Modul chart zatím neexistuje, graf přeskočen")


if __name__ == "__main__":
    main()
