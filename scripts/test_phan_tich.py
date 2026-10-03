import unittest

from phan_tich import _chup, so_sanh_top10
from cap_nhat_du_lieu import _kiem_tra_danh_muc_quy


class TopTenComparisonTests(unittest.TestCase):
    def test_undisclosed_tickers_are_not_treated_as_zero(self):
        domestic = [
            {"ma": "D1", "ngay": "2026-10-01", "top": [("AAA", 6), ("ONLYD", 3)]},
        ]
        foreign = [
            {"ma": "F1", "ngay": "2026-10-02", "top": [("AAA", 4), ("ONLYF", 2)]},
        ]

        rows, meta = so_sanh_top10(domestic, foreign, {}, {})

        self.assertEqual([row["ma"] for row in rows], ["AAA"])
        self.assertEqual(rows[0]["noi_tb"], 6)
        self.assertEqual(rows[0]["ngoai_tb"], 4)
        self.assertEqual(rows[0]["so_noi"], 1)
        self.assertEqual(rows[0]["so_ngoai"], 1)
        self.assertIsNone(rows[0]["vn100"])
        self.assertEqual(meta["pham_vi"], "top10")

    def test_tickers_outside_published_top_ten_are_not_in_comparison(self):
        domestic_top = [(f"D{i}", 20 - i) for i in range(10)] + [("OUTSIDE", 1)]
        foreign_top = [(f"F{i}", 20 - i) for i in range(10)] + [("OUTSIDE", 1)]
        domestic = [{"ma": "D", "ngay": "2026-10-01", "top": domestic_top}]
        foreign = [{"ma": "F", "ngay": "2026-10-01", "top": foreign_top}]

        rows, _ = so_sanh_top10(domestic, foreign, {}, {})

        self.assertEqual(rows, [])

    def test_means_use_only_funds_that_disclose_the_ticker(self):
        domestic = [
            {"ma": "D1", "ngay": "2026-10-01", "top": [("AAA", 6)]},
            {"ma": "D2", "ngay": "2026-10-02", "top": [("AAA", 4)]},
            {"ma": "D3", "ngay": "2026-10-03", "top": [("BBB", 8)]},
        ]
        foreign = [
            {"ma": "F1", "ngay": "2026-10-03", "top": [("AAA", 3)]},
        ]

        rows, meta = so_sanh_top10(domestic, foreign, {"AAA": 5}, {})

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["noi_tb"], 5)
        self.assertEqual(rows[0]["so_noi"], 2)
        self.assertEqual(rows[0]["vn100"], 5)
        self.assertEqual(meta["noi_so_quy"], 3)
        self.assertEqual(meta["ngoai_mau"][0]["ma"], "F1")
        self.assertEqual(meta["ngoai_mau"][0]["ngay"], "2026-10-03")

    def test_only_compares_symbols_disclosed_in_both_samples(self):
        domestic = [{"ma": "D", "ngay": "2026-10-01", "top": [("AAA", 1)]}]
        foreign = [{"ma": "F", "ngay": "2026-10-01", "top": [("BBB", 1)]}]

        rows, _ = so_sanh_top10(domestic, foreign, {}, {})

        self.assertEqual(rows, [])

    def test_duplicate_ticker_rows_count_once_per_fund(self):
        domestic = [{"ma": "D", "ngay": "2026-10-01", "top": [("AAA", 1), ("AAA", 2)]}]
        foreign = [{"ma": "F", "ngay": "2026-10-01", "top": [("AAA", 4)]}]

        rows, _ = so_sanh_top10(domestic, foreign, {}, {})

        self.assertEqual(rows[0]["so_noi"], 1)
        self.assertEqual(rows[0]["noi_tb"], 3)


class FundSnapshotValidationTests(unittest.TestCase):
    def test_rejects_invalid_weights(self):
        with self.assertRaisesRegex(ValueError, "ngoài phạm vi"):
            _kiem_tra_danh_muc_quy({"ma": "F1", "ngay": "2026-10-01", "top": [("AAA", 101)]})

    def test_rejects_duplicate_tickers(self):
        with self.assertRaisesRegex(ValueError, "bị lặp"):
            _kiem_tra_danh_muc_quy({"ma": "F1", "ngay": "2026-10-01", "top": [("AAA", 4), ("AAA", 2)]})

    def test_rejects_implausible_total_weight(self):
        with self.assertRaisesRegex(ValueError, "vượt ngưỡng"):
            _kiem_tra_danh_muc_quy({"ma": "F1", "ngay": "2026-10-01", "top": [("AAA", 60), ("BBB", 42)]})

    def test_rejects_negative_share_count(self):
        with self.assertRaisesRegex(ValueError, "số lượng cổ phiếu ngoài phạm vi"):
            _kiem_tra_danh_muc_quy({
                "ma": "F1", "ngay": "2026-10-01", "top": [("AAA", 10)], "so_cp": {"AAA": -1}
            })


class SameDateCorrectionTests(unittest.TestCase):
    def test_records_correction_before_replacing_same_date_snapshot(self):
        history = {"F1": [{"ngay": "2026-10-01", "pct": {"AAA": 4, "OLD": 1}}]}
        events = []

        changed = _chup(
            history, "F1", "2026-10-01", None, {"AAA": 5, "NEW": 2}, events,
            {"ghi_nhan_luc": "2026-10-03T07:00:00+07:00"},
        )

        self.assertTrue(changed)
        self.assertEqual(history["F1"][-1]["pct"], {"AAA": 5, "NEW": 2})
        self.assertEqual(events[0]["thay_doi"]["pct"]["AAA"]["truoc"], 4)
        self.assertEqual(events[0]["thay_doi"]["pct"]["OLD"]["co_sau"], False)
        self.assertEqual(events[0]["thay_doi"]["pct"]["NEW"]["co_truoc"], False)

    def test_same_snapshot_does_not_create_correction_event(self):
        history = {"F1": [{"ngay": "2026-10-01", "pct": {"AAA": 4}}]}
        events = []

        changed = _chup(history, "F1", "2026-10-01", None, {"AAA": 4}, events)

        self.assertFalse(changed)
        self.assertEqual(events, [])

    def test_records_correction_to_an_older_disclosure(self):
        history = {"F1": [
            {"ngay": "2026-09-30", "pct": {"AAA": 4}},
            {"ngay": "2026-10-01", "pct": {"AAA": 5}},
        ]}
        events = []

        changed = _chup(history, "F1", "2026-09-30", None, {"AAA": 4.5}, events)

        self.assertTrue(changed)
        self.assertEqual(history["F1"][0]["pct"]["AAA"], 4.5)
        self.assertEqual(history["F1"][1]["ngay"], "2026-10-01")
        self.assertEqual(events[0]["ngay_danh_muc"], "2026-09-30")


if __name__ == "__main__":
    unittest.main()
