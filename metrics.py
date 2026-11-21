"""指标定义与可报告性：参与者、家庭、成团、假期相对日。

可报告性规则：
- 明细且 closed 的格：家庭凭证可核对，跨馆同一凭证在联合家庭指标中只记一次。
- 总量且 closed 的格：人次计入，家庭数未报；不假定重叠程度，也不以零代替。
- 未 closed 的格：量未齐，人次只入暂定，不进正式发布值。

每个数字都带出来源记录号（共同事实支持），便于核对。
"""
from facts import group_index, holiday_position

DEFINITIONS = {
    "参与者": "进场人次：entry.entries 求和，同一 record 取最高 seq。",
    "家庭": "核实到场家庭：明细且齐的格内 household 去重；总量格家庭数未报，不以零计。",
    "成团": "渠道订单存在核销记录的团；延期、取消不计入。",
    "假期相对日": "入场日期与该校当季 start 的日差，start 当日为 0。",
}


def season_report(snap, season):
    """汇总某一季在某快照下的指标与可报告性。"""
    calendars = snap.book["calendars"]
    cells = {}
    outside = []
    for row in snap.entries:
        pos = holiday_position(calendars, row["school"], row["date"])
        if pos is None:
            outside.append(row["record"])
            continue
        row_season, rel = pos
        if row_season != season:
            continue
        key = (row["venue"], row["school"])
        cell = cells.setdefault(key, {"rows": [], "rel_days": {}})
        cell["rows"].append(row)
        cell["rel_days"][rel] = cell["rel_days"].get(rel, 0) + row["entries"]

    cell_reports = {}
    for (venue, school), cell in sorted(cells.items()):
        cov = snap.cell(season, venue, school)
        level = cov["level"] if cov else None
        closed = bool(cov and cov["closed"])
        detailed = level == "明细"
        households = sorted({r["household"] for r in cell["rows"] if r["household"]}) if detailed else None
        uncredentialed = sum(r["entries"] for r in cell["rows"] if not r["household"]) if detailed else None
        cell_reports[(venue, school)] = {
            "level": level or "无覆盖记录",
            "closed": closed,
            "entries": sum(r["entries"] for r in cell["rows"]),
            "households": households,
            "uncredentialed_entries": uncredentialed,
            "rel_days": dict(sorted(cell["rel_days"].items())),
            "sources": [r["record"] for r in cell["rows"]],
        }

    closed_cells = {k: c for k, c in cell_reports.items() if c["closed"]}
    unclosed = [k for k, c in cell_reports.items() if not c["closed"]]
    exact_households = sorted({h for c in closed_cells.values() for h in c["households"] or []})
    unknown_household_cells = [k for k, c in closed_cells.items() if c["households"] is None]

    relative = {}
    for (venue, school), cell in cell_reports.items():
        for rel, n in cell["rel_days"].items():
            slot = relative.setdefault((school, rel), {"closed": 0, "provisional": 0})
            slot["closed" if cell["closed"] else "provisional"] += n

    groups = group_index(snap.entries, calendars)
    formed, party_units, deferred, cancelled, unattributed = [], 0, [], [], []
    for order in snap.book["channel"]:
        seasons = groups.get(order["group"], {}).get("seasons", set())
        owned = season in seasons
        status = order["status"]
        if status == "核销":
            if owned:
                if order["group"] not in formed:
                    formed.append(order["group"])
                party_units += order["party_units"] or 0
            elif not seasons:
                unattributed.append(order["order"])
        elif owned:
            (deferred if status == "延期" else cancelled).append(order["order"])
        elif not seasons:
            unattributed.append(order["order"])

    caveats = []
    if unknown_household_cells:
        caveats.append("总量上报格的家庭数未报，不以零计：" + "、".join(f"{v}/{s}" for v, s in unknown_household_cells))
    if unclosed:
        caveats.append("量未齐格只入暂定：" + "、".join(f"{v}/{s}" for v, s in unclosed))
    if outside:
        caveats.append("窗外记录不进假期指标：" + "、".join(outside))
    if unattributed:
        caveats.append("订单无法归因到季：" + "、".join(unattributed))

    return {
        "season": season,
        "seq": snap.seq,
        "cells": cell_reports,
        "entries_closed": sum(c["entries"] for c in closed_cells.values()),
        "entries_provisional": sum(cell_reports[k]["entries"] for k in unclosed),
        "households_exact": exact_households,
        "households_exact_count": len(exact_households),
        "households_unknown_cells": unknown_household_cells,
        "uncredentialed_entries": sum(c["uncredentialed_entries"] or 0 for c in closed_cells.values()),
        "unclosed_cells": unclosed,
        "publishable": not unclosed,
        "relative": relative,
        "formed_groups": sorted(formed),
        "formed_party_units": party_units,
        "deferred_orders": deferred,
        "cancelled_orders": cancelled,
        "unattributed_orders": unattributed,
        "outside_window": outside,
        "caveats": caveats,
    }
