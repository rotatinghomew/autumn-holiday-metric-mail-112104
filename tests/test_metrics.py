"""指标层：家庭去重、总量格不假定重叠、未齐格只入暂定、成团口径。"""
from pathlib import Path
import unittest

from source_book import load
from facts import snapshot
from metrics import season_report

BOOK = load(Path(__file__).resolve().parents[1] / "data" / "samples.json")


class SeasonReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2025 = season_report(snapshot(BOOK), "2025")
        cls.r2026 = season_report(snapshot(BOOK), "2026")

    def test_household_dedup_across_venues(self):
        # h1 在松馆、湾馆各刷一次：入场人次相加，联合家庭只记一次
        self.assertEqual(self.r2025["entries_closed"], 10)
        self.assertEqual(self.r2025["households_exact"], ["h1"])
        # 2026 的 h3 同样跨两馆
        self.assertEqual(self.r2026["households_exact"], ["h3"])

    def test_total_only_cell_is_not_zero_and_not_assumed(self):
        # 湾馆/S2 2025 只报总量：人次计入，家庭数未报，不以零计
        self.assertIn(("湾馆", "S2"), self.r2025["households_unknown_cells"])
        self.assertEqual(self.r2025["households_exact_count"], 1)  # 只数明细格
        self.assertTrue(any("不以零计" in c for c in self.r2025["caveats"]))

    def test_unclosed_cell_is_provisional_only(self):
        # 湾馆/S2 2026 未报告齐：人次只入暂定，整季不可发布
        self.assertEqual(self.r2026["entries_closed"], 4)
        self.assertEqual(self.r2026["entries_provisional"], 4)
        self.assertIn(("湾馆", "S2"), self.r2026["unclosed_cells"])
        self.assertFalse(self.r2026["publishable"])
        self.assertTrue(self.r2025["publishable"])

    def test_formed_groups_exclude_deferred_and_cancelled(self):
        self.assertEqual(self.r2025["formed_groups"], ["g1", "g2"])
        self.assertEqual(self.r2025["formed_party_units"], 2)
        self.assertEqual(self.r2026["formed_groups"], ["g3"])  # g4 延期不算成团
        self.assertEqual(self.r2026["deferred_orders"], ["t4"])
        self.assertEqual(self.r2026["unattributed_orders"], ["t5"])  # 取消单无法归因

    def test_relative_day_series(self):
        self.assertEqual(self.r2025["relative"][("S1", 0)]["closed"], 6)
        self.assertEqual(self.r2026["relative"][("S2", 0)]["provisional"], 4)

    def test_approved_seq_snapshot_differs(self):
        # 批准时点（seq=1）与当前（seq=3）的联合指标不同：事实已更新
        at1 = season_report(snapshot(BOOK, 1), "2026")
        self.assertEqual(at1["households_unknown_cells"], [("湾馆", "S1")])  # 当时是总量格
        self.assertEqual(at1["entries_provisional"], 0)  # e6 尚未上报


if __name__ == "__main__":
    unittest.main()
