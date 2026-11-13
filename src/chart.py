"""Statický graf (PNG, 4:3 na šířku) v designu pkohout.com.

Forma "zvýrazni jednu, ostatní zašedni": v každém panelu malých násobků je červenou
čarou situace čtenáře a šedou oficiální CPI. Identita je dána názvem panelu, ne barvou.
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
import pandas as pd  # noqa: E402

import model  # noqa: E402

# --- design pkohout.com -----------------------------------------------------
SURFACE = "#FBF6EB"   # krémové pozadí webu
INK = "#141211"        # primární text
INK2 = "#4A4642"       # sekundární text
MUTED = "#6F6A62"      # popisky os
GRID = "#E6DFD0"       # hairline mřížka
BASE = "#A9A397"       # osa
ACCENT = "#BA3A36"     # červená pkohout.com: situace čtenáře
BENCH = "#6F6A62"      # neutrální šedá: oficiální CPI (zdůrazni jednu, ostatní zašedni)
FONT = ["EB Garamond", "Garamond", "Times New Roman", "DejaVu Serif"]
_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
for _f in ("EBGaramond-Regular.ttf", "EBGaramond-SemiBold.ttf"):  # písmo je v repozitáři (licence SIL OFL)
    _p = os.path.join(_FONT_DIR, _f)
    if os.path.exists(_p):
        font_manager.fontManager.addfont(_p)

PANELS = [
    ("kupujici", "Kupující", "Chce si koupit byt: cena starších bytů × splátka"),
    ("drzitel", "Držitel hypotéky", "Splácí hypotéku: průměrná sazba ze zůstatků"),
    ("najemnik", "Nájemník", "Platí nájem: nájemné z CPI"),
    ("vlastnik", "Vlastník bez hypotéky", "Bydlení nic nestojí: koš bez nájmu"),
]


def _pct(v):
    return f"{v:+.1f} %".replace(".", ",").replace("-", "−")


def render(res, H, out_dir):
    plt.rcParams.update({"font.family": FONT, "font.size": 11.5, "axes.unicode_minus": True})
    idx = res["idx"]
    x = idx.to_timestamp() + pd.offsets.MonthEnd(0)
    est = res["hpi_est_from"]

    series = {k: model.situation_index(res, k, H) for k, _, _ in PANELS}
    bench = model.situation_index(res, "cpi", H)
    base = lambda s: s / s.iloc[0] * 100  # noqa: E731
    series = {k: base(v) for k, v in series.items()}
    bench = base(bench)

    lo = min(min(s.min() for s in series.values()), bench.min())
    hi = max(max(s.max() for s in series.values()), bench.max())
    ymin = 100 if lo >= 99 else (int(lo // 25) * 25)
    ymax = (int(hi // 25) + 1) * 25
    pad = 5

    fig = plt.figure(figsize=(12, 9), dpi=150, facecolor=SURFACE)
    fig.text(0.055, 0.945, "Inflace se započtením bydlení: podle toho, v jaké jste situaci",
             fontsize=23.5, color=INK, ha="left", va="center", weight="bold")
    last = idx[-1]
    fig.text(0.055, 0.905,
             f"Index cen, prosinec 2015 = 100, do {last.month}/{last.year}. "
             f"Podíl bydlení v rozpočtu {int(round(H * 100))} %.",
             fontsize=12.9, color=INK2, ha="left", va="center")

    # sdílená legenda (>= 2 série => legenda vždy; klíč je krátká čára)
    lx, ly = 0.055, 0.868
    for label, color in (("Situace čtenáře", ACCENT), ("Oficiální CPI (přepočet)", BENCH)):
        fig.add_artist(plt.Line2D([lx, lx + 0.03], [ly, ly], color=color, lw=1.2,
                                  transform=fig.transFigure, solid_capstyle="round"))
        t = fig.text(lx + 0.038, ly, label, fontsize=11.8, color=INK2, ha="left", va="center")
        fig.canvas.draw()
        w = t.get_window_extent().width / fig.bbox.width
        lx += 0.038 + w + 0.03

    axes = fig.subplots(2, 2, sharex=True, sharey=True,
                        gridspec_kw={"left": 0.075, "right": 0.955, "top": 0.755,
                                     "bottom": 0.105, "hspace": 0.50, "wspace": 0.12}).ravel()
    for ax, (key, title, sub) in zip(axes, PANELS):
        ax.set_facecolor(SURFACE)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(BASE)
        ax.spines["bottom"].set_linewidth(0.6)
        ax.set_ylim(ymin - pad, ymax + pad)
        ax.set_yticks(range(ymin, ymax + 1, 25))
        ax.grid(axis="y", color=GRID, lw=0.6, ls="-")
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", length=0, labelsize=10.6, labelcolor=MUTED, pad=5)
        ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(2))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))

        s = series[key]
        ax.plot(x, bench, color=BENCH, lw=1.1, solid_capstyle="round", solid_joinstyle="round", zorder=2)
        if key == "kupujici" and est is not None:
            solid = x <= (est - 1).to_timestamp() + pd.offsets.MonthEnd(0)
            ax.plot(x[solid], s[solid], color=ACCENT, lw=1.3, solid_capstyle="round", zorder=3)
            k0 = max(int(solid.sum()) - 1, 0)
            ax.plot(x[k0:], s.iloc[k0:], color=ACCENT, lw=1.3, ls=(0, (2.2, 2.2)), zorder=3)
        else:
            ax.plot(x, s, color=ACCENT, lw=1.3, solid_capstyle="round", solid_joinstyle="round", zorder=3)
        # koncové body s okrajem barvy povrchu (2 px) a hodnota u situace
        for ser, color in ((bench, BENCH), (s, ACCENT)):
            ax.plot([x[-1]], [ser.iloc[-1]], marker="o", ms=5.2, mfc=color, mec=SURFACE, mew=1.0,
                    zorder=5, clip_on=False)
        ax.annotate(f"{s.iloc[-1]:.0f}", (x[-1], s.iloc[-1]), xytext=(7, 0), textcoords="offset points",
                    fontsize=11.8, color=INK, weight="bold", va="center", ha="left", annotation_clip=False)

        tot, off = s.iloc[-1] - 100, bench.iloc[-1] - 100
        ax.text(0, 1.215, title, transform=ax.transAxes, fontsize=15.7, color=INK, weight="bold",
                ha="left", va="bottom")
        months = len(s) - 1
        pa, off_pa = model.per_annum(tot, months), model.per_annum(off, months)
        ax.text(0, 1.125, f"{_pct(tot)} od 12/2015 ({_pct(pa)} ročně) · oficiální CPI {_pct(off)} ({_pct(off_pa)} ročně)",
                transform=ax.transAxes, fontsize=11.8, color=INK2, ha="left", va="bottom")
        ax.text(0, 1.045, sub, transform=ax.transAxes, fontsize=10.1, color=MUTED, ha="left", va="bottom")
        ax.set_xlim(x[0], x[-1])
    for ax in axes[::2]:
        ax.tick_params(axis="y", labelleft=True)
    for ax in axes[1::2]:
        ax.tick_params(axis="y", labelleft=False)

    foot = ("Zdroj: ČSÚ (CPI, ceny starších bytů), ČNB ARAD (sazby z úvěrů na bydlení), vlastní výpočet. "
            "Experimentální index, nejde o oficiální statistiku.")
    if est is not None:
        foot += f"\nČárkovaně: odhad cen bytů od {est.month}/{est.year} (poslední data ČSÚ za {res['last_hpi_q']})."
    fig.text(0.055, 0.046, foot, fontsize=9.6, color=MUTED, ha="left", va="center", linespacing=1.35)
    fig.text(0.965, 0.018, "pkohout.com", fontsize=11.2, color=ACCENT, ha="right", va="center", weight="bold")

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "graf_inflace_bydleni.png")
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    print(f"Graf: {path}")
    return path
