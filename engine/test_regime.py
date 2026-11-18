"""Regime detection tests with synthetic OHLC."""
import unittest
import pandas as pd
import numpy as np
from regime import detect_regime


def _df(n=80, trend=1.0, noise=0.2):
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(trend * 0.1, noise, n))
    high = close + rng.uniform(0.1, 0.8, n)
    low = close - rng.uniform(0.1, 0.8, n)
    open_ = close - rng.normal(0, 0.2, n)
    vol = rng.uniform(100, 200, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol}
    )


class TestRegime(unittest.TestCase):
    def test_returns_keys(self):
        r = detect_regime(_df())
        self.assertIn("regime", r)
        self.assertIn("volatility", r)
        self.assertIn("trend", r)

    def test_empty(self):
        r = detect_regime(pd.DataFrame())
        self.assertEqual(r["regime"], "unknown")


if __name__ == "__main__":
    unittest.main()
