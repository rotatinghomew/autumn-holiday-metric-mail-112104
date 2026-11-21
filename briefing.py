"""秋假客群简报：指标、同比、列口径与分发计划。

用法：
    python3 briefing.py data/samples.json                  # 全览
    python3 briefing.py data/samples.json metrics --season 2026
    python3 briefing.py data/samples.json yoy
    python3 briefing.py data/samples.json columns 亲子量=核实到场家庭 ...
    python3 briefing.py data/samples.json dispatch
    python3 briefing.py data/samples.json reschedule --week 47 --due 11-24
"""
import argparse
import json

from source_book import load
from facts import current_seq, snapshot
from metrics import DEFINITIONS, season_report
from editions import align_relative, column_plan, measure_series, recompute_segments
from plan import evaluate, reschedule


def render_report(report):
    """把 season_report 转成可 JSON 序列化的形状。"""
    return {
        "季": report["season"],
        "seq": report["seq"],
        "入场人次": {"正式": report["entries_closed"], "暂定": report["entries_provisional"]},
        "核实到场家庭": {
            "确切": report["households_exact_count"],
            "名单": report["households_exact"],
            "未报格": [f"{v}/{s}" for v, s in report["households_unknown_cells"]],
        },
        "未带凭证人次": report["uncredentialed_entries"],
        "成团": report["formed_groups"],
        "订单家庭": report["formed_party_units"],
        "延期订单": report["deferred_orders"],
        "取消订单": report["cancelled_orders"],
        "相对假期日": {f"{s}@{r}": v for (s, r), v in sorted(report["relative"].items())},
        "格": {f"{v}/{s}": c for (v, s), c in report["cells"].items()},
        "未齐格": [f"{v}/{s}" for v, s in report["unclosed_cells"]],
        "可发布": report["publishable"],
        "注意": report["caveats"],
    }


def main():
    parser = argparse.ArgumentParser(description="秋假客群简报：指标、同比、列口径与分发计划")
    parser.add_argument("path")
    sub = parser.add_subparsers(dest="cmd")

    p_metrics = sub.add_parser("metrics", help="当季指标与可报告性")
    p_metrics.add_argument("--season", required=True)

    sub.add_parser("yoy", help="同比：相对假期日对齐与列口径")

    p_columns = sub.add_parser("columns", help="判定拟写列 列名=口径")
    p_columns.add_argument("pairs", nargs="+")
    p_columns.add_argument("--edition", required=True)
    p_columns.add_argument("--tab", default="联合")

    sub.add_parser("dispatch", help="分发评估与回执")

    p_reschedule = sub.add_parser("reschedule", help="以新周次重用排期")
    p_reschedule.add_argument("--week", required=True)
    p_reschedule.add_argument("--due", required=True)

    args = parser.parse_args()
    book = load(args.path)

    if args.cmd == "metrics":
        out = render_report(season_report(snapshot(book), args.season))
    elif args.cmd == "yoy":
        out = {"相对假期日对齐": align_relative(book), "列口径": measure_series(book)}
    elif args.cmd == "columns":
        proposals = [tuple(p.split("=", 1)) for p in args.pairs]
        out = {
            "拟写列": column_plan(book, args.edition, args.tab, proposals),
            "重算范围": [recompute_segments(book, m) for _, m in proposals],
        }
    elif args.cmd == "dispatch":
        out = evaluate(book)
    elif args.cmd == "reschedule":
        out = reschedule(book, args.week, args.due)
    else:
        snap = snapshot(book)
        seasons = sorted({c["season"] for c in book["calendars"]})
        out = {
            "定义": DEFINITIONS,
            "当前seq": current_seq(book),
            "指标": {s: render_report(season_report(snap, s)) for s in seasons},
            "同比": {"相对假期日对齐": align_relative(book), "列口径": measure_series(book)},
            "分发": evaluate(book),
        }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
