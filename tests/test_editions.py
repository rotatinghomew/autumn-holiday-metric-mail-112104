"""口径层：列名复用判定、同比对齐、历史区段可重算性。"""
from pathlib import Path
import unittest

from source_book import load
from editions import align_relative, column_plan, measure_series, recompute_segments

BOOK = load(Path(__file__).resolve().parents[1] / "data" / "samples.json")


class ColumnPlanTest(unittest.TestCase):
    def test_reuse_same_meaning(self):
        [verdict] = column_plan(BOOK, "2026", "联合", [("入场量", "进场人次")])
        self.assertEqual(verdict["判定"], "复用")

    def test_conflict_same_name_different_meaning(self):
        [verdict] = column_plan(BOOK, "2026", "联合", [("亲子量", "订单家庭")])
        self.assertEqual(verdict["判定"], "冲突")
        self.assertIn("同列名不得掩盖定义差异", verdict["原因"])

    def test_new_column_notes_history(self):
        [verdict] = column_plan(BOOK, "2025", "联合", [("核实量", "核实到场家庭")])
        self.assertEqual(verdict["判定"], "新增")
        self.assertEqual(verdict["备注"], "全新列")


class MeasureSeriesTest(unittest.TestCase):
    def test_same_name_different_meaning_cannot_join(self):
        series = {row["列"]: row for row in measure_series(BOOK)}
        joint = series["亲子量"]
        self.assertEqual(joint["拼接"], "禁止")
        self.assertIn("同名异义", joint["原因"])
        # 两种口径分别报告：订单家庭两年都可算，核实家庭各有缺口
        self.assertEqual(joint["分别报告"]["订单家庭"], {"2025": 2, "2026": 1})
        self.assertEqual(joint["分别报告"]["核实到场家庭"]["2025"]["确切"], 1)
        self.assertEqual(joint["分别报告"]["核实到场家庭"]["2025"]["未报格"], ["湾馆/S2"])
        self.assertEqual(joint["分别报告"]["核实到场家庭"]["2026"]["未齐格"], ["湾馆/S2"])

    def test_same_meaning_can_join_within_closed_scope(self):
        series = {row["列"]: row for row in measure_series(BOOK)}
        self.assertEqual(series["入场量"]["拼接"], "可对齐")
        self.assertEqual(series["入场量"]["数值"]["2025"]["正式"], 10)

    def test_dimension_column_conflict_is_flagged(self):
        series = {row["列"]: row for row in measure_series(BOOK)}
        # 观察窗 2025=自然周、2026=相对假期日：维度列同样不得默默拼接
        self.assertEqual(series["观察窗"]["拼接"], "禁止")


class AlignRelativeTest(unittest.TestCase):
    def test_align_by_relative_day(self):
        rows = {(r["学校"], r["相对日"]): r for r in align_relative(BOOK)}
        s1 = rows[("S1", 0)]
        self.assertEqual(s1["判定"], "可对齐")
        self.assertEqual(s1["各季"]["2025"]["人次"], 6)
        self.assertEqual(s1["各季"]["2026"]["人次"], 4)
        self.assertEqual(s1["范围"], "S1 相对日0")

    def test_unclosed_segment_cannot_align(self):
        rows = {(r["学校"], r["相对日"]): r for r in align_relative(BOOK)}
        s2 = rows[("S2", 0)]
        self.assertEqual(s2["判定"], "不可对齐")
        self.assertIn("量未齐", s2["原因"])
        # 不能对齐也给分别数值
        self.assertEqual(s2["各季"]["2025"]["人次"], 4)
        self.assertEqual(s2["各季"]["2026"]["暂定人次"], 4)


class RecomputeSegmentsTest(unittest.TestCase):
    def test_household_meaning_segments(self):
        plan = recompute_segments(BOOK, "核实到场家庭")
        self.assertIn("2025 松馆/S1", plan["可重算"])
        self.assertIn("2026 湾馆/S1", plan["可重算"])
        keep = {item["区段"]: item["原因"] for item in plan["并列保留"]}
        self.assertIn("2025 湾馆/S2", keep)   # 总量上报，无法重算去重
        self.assertIn("2026 湾馆/S2", keep)   # 量未齐
        self.assertIn("总量", keep["2025 湾馆/S2"])

    def test_unknown_meaning_rejected(self):
        with self.assertRaises(ValueError):
            recompute_segments(BOOK, "拍脑袋口径")


if __name__ == "__main__":
    unittest.main()
