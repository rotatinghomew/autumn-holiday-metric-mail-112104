"""分发层：授权撤回、事实更新、批次一致、回执、更正承接、重排期处置。"""
import copy
from pathlib import Path
import unittest

from source_book import load
from plan import evaluate, receipts, reschedule

BOOK = load(Path(__file__).resolve().parents[1] / "data" / "samples.json")


def drop_seq_after(book, seq, tables):
    kept = copy.deepcopy(book)
    for name in tables:
        kept[name] = [r for r in kept[name] if r.get("seq", 0) <= seq]
    return kept


def pending_of(result, recipient):
    return next(item for item in result["待发评估"] if item["收件人"] == recipient)


class EvaluateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = evaluate(BOOK)

    def test_withdrawn_scope_blocks_approved_material(self):
        item = pending_of(self.result, "校务处")
        pages = {p["页"]: p for p in item["页面"]}
        # S1 授权已撤回：原批准材料不能直接发
        self.assertEqual(pages["所辖/S1"]["处置"], "待授权")
        self.assertIn("授权已撤回", pages["所辖/S1"]["原因"])
        # 联合页仍获授权，但湾馆/S2 量未齐
        self.assertEqual(pages["联合"]["处置"], "待数据")
        self.assertEqual(pages["联合"]["缺口"], ["湾馆/S2"])
        self.assertEqual(item["处置"], "待数据")

    def test_agency_only_gets_joint_summary(self):
        item = pending_of(self.result, "旅行社")
        self.assertEqual([p["页"] for p in item["页面"]], ["联合"])
        self.assertEqual(item["处置"], "待数据")

    def test_delivered_stale_material_gets_chained_correction(self):
        [corr] = self.result["更正建议"]
        self.assertEqual(corr["收件人"], "馆方")
        self.assertEqual(corr["承接"], {"edition": "2026", "week": "46", "approved_seq": 1})
        self.assertEqual(set(corr["变化页"]), {"联合", "所辖/湾馆"})
        self.assertEqual(corr["处置"], "待数据")  # 湾馆/S2 未齐，更正也要等数据

    def test_receipts_show_seen_versions_and_unsent(self):
        got = receipts(BOOK)
        self.assertEqual(got["馆方"]["已送达版本"], [{"edition": "2026", "week": "46", "approved_seq": 1}])
        self.assertEqual(got["校务处"]["已送达版本"], [{"edition": "2025", "week": "46", "approved_seq": 1}])
        self.assertEqual([u["week"] for u in got["校务处"]["未发"]], ["46"])
        self.assertEqual(got["旅行社"]["已送达版本"], [])


class RescheduleTest(unittest.TestCase):
    def test_sample_book_dispositions_are_differentiated(self):
        plan = reschedule(BOOK, "47", "11-24")
        by_recipient = {}
        for row in plan["新增"]:
            by_recipient.setdefault(row["recipient"], []).append(row)
        # 量未齐：留队等数据，不是继续待发
        self.assertEqual(by_recipient["校务处"][0]["result"], "待数据")
        self.assertEqual(by_recipient["旅行社"][0]["result"], "待数据")
        # 更正承接原期次，不另起新周次
        [corr] = by_recipient["馆方"]
        self.assertEqual((corr["edition"], corr["week"]), ("2026", "46"))
        self.assertEqual(corr["承接"]["approved_seq"], 1)
        # 没有一键把所有人留在待发队列
        self.assertFalse(any(r["result"] == "待发" for r in plan["新增"]))
        # 旧待发行标记改期；送达行不动
        self.assertEqual({u["recipient"] for u in plan["更新"]}, {"校务处", "旅行社"})
        self.assertTrue(all(u["result"] == "已改期" for u in plan["更新"]))

    def test_reschedule_does_not_mutate_book(self):
        before = copy.deepcopy(BOOK)
        reschedule(BOOK, "47", "11-24")
        self.assertEqual(BOOK, before)

    def test_batch_shares_one_snapshot(self):
        plan = reschedule(BOOK, "47", "11-24")
        self.assertEqual({r["approved_seq"] for r in plan["新增"]}, {plan["seq"]})


class SyntheticScenarioTest(unittest.TestCase):
    def test_unchanged_facts_stay_sendable(self):
        # 没有任何后续变更：批准仍有效，全部可发
        book = drop_seq_after(BOOK, 1, ("entry", "coverage", "grants"))
        result = evaluate(book)
        for item in result["待发评估"]:
            self.assertEqual(item["处置"], "可发", item)
        self.assertEqual(result["更正建议"], [])
        plan = reschedule(book, "47", "11-24")
        self.assertTrue(all(r["result"] == "待发" for r in plan["新增"]))

    def test_partial_reassignment_keeps_accurate_authorized_pages(self):
        # 只撤回 S1 授权、事实未变：联合页仍准确且有权，改派后继续发
        book = drop_seq_after(BOOK, 1, ("entry", "coverage"))
        result = evaluate(book)
        item = pending_of(result, "校务处")
        pages = {p["页"]: p for p in item["页面"]}
        self.assertEqual(pages["联合"]["处置"], "可发")
        self.assertEqual(pages["所辖/S1"]["处置"], "待授权")
        self.assertEqual(item["处置"], "改派")
        plan = reschedule(book, "47", "11-24")
        row = next(r for r in plan["新增"] if r["recipient"] == "校务处")
        self.assertEqual(row["result"], "待发")  # 有权且准确的部分不陪绑等待
        # 已送达的馆方内容未变，不需要更正
        self.assertEqual(result["更正建议"], [])


if __name__ == "__main__":
    unittest.main()
