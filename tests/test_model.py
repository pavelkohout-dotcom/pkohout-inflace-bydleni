import json
import os
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import model  # noqa: E402


def load():
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    cpi = pd.read_csv(os.path.join(ROOT, "data", "cpi_levels.csv"), index_col=0)
    cpi.index = pd.PeriodIndex(cpi.index, freq="M")
    hpi = pd.read_csv(os.path.join(ROOT, "data", "hpi_existing_q.csv"), index_col=0).iloc[:, 0]
    hpi.index = pd.PeriodIndex(hpi.index, freq="Q")
    rates = pd.read_csv(os.path.join(ROOT, "data", "arad_rates.csv"), index_col=0)
    rates.index = pd.PeriodIndex(rates.index, freq="M")
    return cfg, cpi, hpi, rates


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.cpi, cls.hpi, cls.rates = load()
        cls.res = model.build(cls.cpi, cls.hpi, cls.rates, cls.cfg)

    def test_annuity_known_value(self):
        self.assertAlmostEqual(float(model.annuity(6.0, 30)), 0.0059955, places=6)
        self.assertAlmostEqual(float(model.annuity(0.0, 30)), 1 / 360, places=9)

    def test_weights_sum_to_1000(self):
        self.assertAlmostEqual(sum(self.cfg["weights_2024_promile"].values()), 1000.0, delta=0.1)

    def test_reference_period_mean_is_one(self):
        r0, r1 = self.res["ref_period"]
        for key in ("cpi", "vlastnik", "najemnik", "drzitel", "kupujici"):
            s = model.situation_index(self.res, key, 0.30)
            self.assertAlmostEqual(float(s.loc[r0:r1].mean()), 1.0, places=6, msg=key)

    def test_zero_housing_share_equals_basket_without_housing(self):
        s = model.situation_index(self.res, "kupujici", 0.0)
        pd.testing.assert_series_equal(s, self.res["n"], check_names=False)

    def test_laspeyres_equals_chained_effective_shares(self):
        """Lineární vzorec H*hc+(1-H)*n musí dát totéž co řetězení s měnícími se podíly."""
        H = 0.30
        hc, n = self.res["hc"]["kupujici"], self.res["n"]
        chain = [1.0]
        for t in range(1, len(n)):
            s_h = H * hc.iloc[t - 1] / (H * hc.iloc[t - 1] + (1 - H) * n.iloc[t - 1])
            chain.append(chain[-1] * (s_h * hc.iloc[t] / hc.iloc[t - 1] + (1 - s_h) * n.iloc[t] / n.iloc[t - 1]))
        chain = pd.Series(chain, index=n.index)
        direct = model.situation_index(self.res, "kupujici", H)
        ratio = direct / direct.iloc[0]
        np.testing.assert_allclose(chain.values, ratio.values, rtol=1e-9)

    def test_replica_close_to_official(self):
        off, rep = self.res["cpi_official"], self.res["cpi_replica"]
        yo = (off / off.shift(12) - 1) * 100
        yr = (rep / rep.shift(12) - 1) * 100
        err = (yr - yo).loc["2024-01":].dropna()
        self.assertLess(float(err.abs().mean()), 0.25)

    def test_matches_earlier_analysis_at_2026_05(self):
        """Hodnoty z ruční analýzy (podíl bydlení 30 %, 12/2015 -> 5/2026)."""
        expected = {"kupujici": 87.9, "najemnik": 55.3, "drzitel": 37.3, "vlastnik": 55.2, "cpi": 56.5}
        for key, exp in expected.items():
            s = model.situation_index(self.res, key, 0.30)
            got = (s.loc["2026-05"] / s.loc["2015-12"] - 1) * 100
            self.assertAlmostEqual(float(got), exp, delta=0.15, msg=key)

    def test_per_annum(self):
        self.assertAlmostEqual(model.per_annum(100, 120), 7.1773, places=3)   # zdvojnásobení za 10 let
        self.assertAlmostEqual(model.per_annum(21, 24), 10.0, places=6)       # +21 % za 2 roky = 10 % ročně
        self.assertAlmostEqual(model.per_annum(5, 12), 5.0, places=9)         # 12 měsíců: beze změny
        self.assertAlmostEqual(model.per_annum(-19, 24), -10.0, places=6)     # záporná změna

    def test_hpi_estimate_flagged(self):
        est = self.res["hpi_est_from"]
        self.assertIsNotNone(est)
        self.assertGreater(est, pd.Period("2026-05", freq="M"))


if __name__ == "__main__":
    unittest.main()
