"""Model alternativní inflace bydlení pro čtyři situace.

Index každé situace je Laspeyresův index vůči cenám průměru roku 2024:

    L_s(t) = H * hc_s(t) + (1 - H) * n(t)

kde n(t) je koš bez nájemného a imputovaného nájemného (váhy ČSÚ 2024),
hc_s(t) je složka bydlení dané situace a H je podíl bydlení v rozpočtu.
Obě složky jsou normalizované tak, aby průměr referenčního období = 1.
Tentýž vzorec počítá HTML stránka, takže posuvník H nepotřebuje přepočet v Pythonu.
"""
import numpy as np
import pandas as pd


def annuity(rate_pct, years=30):
    """Měsíční splátka na 1 Kč jistiny při roční sazbě v % a splatnosti v letech."""
    i = np.asarray(rate_pct, dtype=float) / 1200.0
    n = years * 12
    with np.errstate(divide="ignore", invalid="ignore"):
        a = i / (1.0 - (1.0 + i) ** (-n))
    return np.where(i == 0, 1.0 / n, a)


def monthly_hpi(hpi_q, end):
    """Čtvrtletní HPI -> měsíční (lineární interpolace mezi prostředními měsíci čtvrtletí).

    Po posledním čtvrtletí extrapoluje trend posledních 12 měsíců až do `end`.
    Vrací (série, první odhadnutý měsíc nebo None).
    """
    pts = {(q.asfreq("M", how="start") + 1): v for q, v in hpi_q.items()}
    s = pd.Series(pts)
    s.index = pd.PeriodIndex(s.index, freq="M")
    m = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M")).interpolate()
    est_from = None
    if end > m.index.max():
        g = np.log(m).diff().iloc[-12:].mean()
        ext = pd.period_range(m.index.max() + 1, end, freq="M")
        vals = [m.iloc[-1] * np.exp(g * (k + 1)) for k in range(len(ext))]
        m = pd.concat([m, pd.Series(vals, index=ext)])
        est_from = ext[0]
    return m, est_from


def build(cpi, hpi_q, rates, cfg):
    w = cfg["weights_2024_promile"]
    nonh = {k: v for k, v in w.items() if k not in ("041", "042")}
    r0, r1 = cfg["ref_period"]
    term = cfg["mortgage_term_years"]

    end = min(cpi.index.max(),
              rates["r_new_net"].dropna().index.max(),
              rates["r_stock"].dropna().index.max())
    start = pd.Period(cfg["start"], freq="M")
    idx = pd.period_range(start, end, freq="M")

    hpi_m, est_from = monthly_hpi(hpi_q, end)
    L = cpi.reindex(idx)
    ref = cpi.loc[r0:r1].mean()

    def laspeyres(weights):
        tot = sum(weights.values())
        return sum(weights[c] * L[c] / ref[c] for c in weights) / tot

    n = laspeyres(nonh)
    cpi_replica = laspeyres(w)
    cpi_official = L["0"] / ref["0"]

    r_new = rates["r_new_net"].reindex(idx)
    r_stk = rates["r_stock"].reindex(idx)
    pay_new = pd.Series(annuity(r_new.values, term), index=idx)
    pay_stk = pd.Series(annuity(r_stk.values, term), index=idx)
    full = pd.period_range(r0, r1, freq="M")
    pay_new_all = pd.Series(annuity(rates["r_new_net"].reindex(idx.union(full)).values, term),
                            index=idx.union(full))
    pay_stk_all = pd.Series(annuity(rates["r_stock"].reindex(idx.union(full)).values, term),
                            index=idx.union(full))
    hpi_all = hpi_m.reindex(idx.union(full))
    buy_all = hpi_all * pay_new_all                      # splátka na standardní byt
    pay_new_ref = pay_new_all.loc[full].mean()
    pay_stk_ref = pay_stk_all.loc[full].mean()
    hpi_ref = hpi_all.loc[full].mean()
    buy_ref = buy_all.loc[full].mean()

    hc = {
        "najemnik": L["041"] / ref["041"],
        "drzitel": pay_stk / pay_stk_ref,
        "kupujici": buy_all.reindex(idx) / buy_ref,
    }
    parts = {"hpi": hpi_m.reindex(idx) / hpi_ref, "splatka_nove": pay_new / pay_new_ref}
    return {
        "idx": idx, "n": n, "cpi_replica": cpi_replica, "cpi_official": cpi_official,
        "hc": hc, "parts": parts, "r_new": r_new, "r_stock": r_stk,
        "hpi_est_from": est_from, "ref_period": (r0, r1),
        "last_hpi_q": f"{hpi_q.index.max().quarter}. čtvrtletí {hpi_q.index.max().year}",
    }


def situation_index(res, key, H):
    """Úroveň indexu situace (průměr referenčního období = 1)."""
    if key == "vlastnik":
        return res["n"]
    if key == "cpi":
        return res["cpi_replica"]
    return H * res["hc"][key] + (1.0 - H) * res["n"]


def per_annum(total_pct, months):
    """Přepočet celkové změny (v %) za dané období na průměrnou roční změnu (složené, geometricky)."""
    return ((1 + total_pct / 100) ** (12 / months) - 1) * 100


def summarize(res, H):
    """Souhrnná čísla pro výchozí podíl bydlení H."""
    out = {}
    idx = res["idx"]
    last = idx[-1]
    for key in ("cpi", "vlastnik", "najemnik", "drzitel", "kupujici"):
        s = situation_index(res, key, H)
        out[key] = {
            "od_zacatku_pct": round(float((s.iloc[-1] / s.iloc[0] - 1) * 100), 1),
            "rocne_od_zacatku_pct": round(float(per_annum((s.iloc[-1] / s.iloc[0] - 1) * 100, len(s) - 1)), 1),
            "mezirocne_pct": round(float((s.iloc[-1] / s.loc[last - 12] - 1) * 100), 1),
        }
    return out
