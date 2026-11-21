"""事实层：seq 快照、假期相对日、团归因。"""
from pathlib import Path
import unittest

from source_book import load
from facts import current_seq, group_index, holiday_position, snapshot

BOOK = load(Path(__file__).resolve().parents[1] / "data" / "samples.json")


class SnapshotTest(unittest.TestCase):
    def test_current_seq(self):
        self.assertEqual(current_seq(BOOK), 3)

    def test_entry_record_takes_highest_seq(self):
        at1 = {r["record"]: r for r in snapshot(BOOK, 1).entries}
        at3 = {r["record"]: r for r in snapshot(BOOK, 3).entries}
        self.assertIsNone(at1["e5"]["household"])       # 批准时还没有家庭凭证
        self.assertEqual(at3["e5"]["household"], "h3")  # 场馆后来补齐
        self.assertNotIn("e6", at1)                     # seq=2 的记录尚未出现
        self.assertEqual(at3["e6"]["household"], "h4")

    def test_coverage_and_grant_versions(self):
        at1, at3 = snapshot(BOOK, 1), snapshot(BOOK, 3)
        self.assertEqual(at1.cell("2026", "湾馆", "S1")["level"], "总量")
        self.assertEqual(at3.cell("2026", "湾馆", "S1")["level"], "明细")
        self.assertIsNone(at1.cell("2026", "湾馆", "S2"))  # seq=1 时还没有覆盖记录
        self.assertTrue(at1.allowed("校务处", "S1"))
        self.assertFalse(at3.allowed("校务处", "S1"))      # seq=3 授权撤回

    def test_relative_holiday_day(self):
        calendars = BOOK["calendars"]
        self.assertEqual(holiday_position(calendars, "S1", "2025-11-14"), ("2025", 0))
        self.assertEqual(holiday_position(calendars, "S2", "2025-11-19"), ("2025", 2))
        self.assertEqual(holiday_position(calendars, "S1", "2026-11-16"), ("2026", 3))
        self.assertIsNone(holiday_position(calendars, "S1", "2025-11-10"))  # 窗外

    def test_group_index(self):
        index = group_index(snapshot(BOOK).entries, BOOK["calendars"])
        self.assertEqual(index["g1"]["seasons"], {"2025"})
        self.assertEqual(index["g3"]["venues"], {"松馆", "湾馆"})
        self.assertNotIn("g5", index)  # 取消的团没有入场记录


if __name__ == "__main__":
    unittest.main()
