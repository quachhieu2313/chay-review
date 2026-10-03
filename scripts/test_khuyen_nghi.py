import unittest

from khuyen_nghi import backtest_momentum, percentile_scores, score_universe


class RecommendationTests(unittest.TestCase):
    def test_percentiles_handle_ties_and_lower_is_better(self):
        values = {"A": 1, "B": 2, "C": 2, "D": 4}
        high = percentile_scores(values)
        low = percentile_scores(values, higher_is_better=False)
        self.assertEqual(high["B"], high["C"])
        self.assertGreater(high["D"], high["A"])
        self.assertLess(low["D"], low["A"])

    def test_composite_rescales_available_factors_and_stays_bounded(self):
        rows = [
            {"ma": f"M{i}", "nganh": "Bank", "roe": float(i), "margin": None, "pe": float(i + 5),
             "pb": None, "volatility": float(i + 2), "drawdown": -float(i + 1), "so_quy": i,
             "so_etf": i // 2, "fund_weight": float(i), "returns": {"3m": i / 100, "6m": i / 80}, "gia": 100 + i,
             "ma50": 99, "ma200": 98, "eps": 1}
            for i in range(6)
        ]
        score_universe(rows)
        for row in rows:
            self.assertIsNotNone(row["scores"]["3m"])
            self.assertGreaterEqual(row["scores"]["3m"], 0)
            self.assertLessEqual(row["scores"]["3m"], 100)
            self.assertGreaterEqual(row["coverage"]["3m"], 65)

    def test_composite_excludes_rows_below_coverage_threshold(self):
        rows = [
            {"ma": f"M{i}", "nganh": "Bank", "roe": None, "margin": None, "pe": None,
             "pb": None, "volatility": float(i + 1), "drawdown": -float(i + 1), "so_quy": None,
             "so_etf": None, "fund_weight": None, "returns": {"3m": i / 10, "6m": i / 10}, "gia": 100 + i,
             "ma50": 99, "ma200": 98, "eps": None}
            for i in range(6)
        ]
        score_universe(rows)
        self.assertTrue(all(row["scores"]["3m"] is None for row in rows))

    def test_backtest_uses_only_prior_momentum_to_rank(self):
        dates = [f"2020-01-{day:02}" for day in range(1, 21)]
        index_closes = [100 + day for day in range(20)]
        histories = {}
        for ticker, factor in [("WIN", 2.0), ("LOSE", 0.5)]:
            closes = [100 + factor * day for day in range(20)]
            histories[ticker] = (dates, closes)
        # The minimum usable universe is 20 to keep top and bottom baskets disjoint.
        for i in range(18):
            histories[f"M{i}"] = (dates, [100 + (0.9 + i * 0.01) * day for day in range(20)])
        result = backtest_momentum(histories, dates, index_closes, 2, 2, max_periods=5)
        self.assertGreater(result["so_ky"], 0)
        self.assertGreater(result["top_tb_pct"], result["day_duoi_tb_pct"])


if __name__ == "__main__":
    unittest.main()
