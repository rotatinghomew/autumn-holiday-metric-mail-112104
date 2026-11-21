"""工作簿列口径与同比对齐。

合作方工作簿列名固定：复用列名必须口径一致，同名异义不得拼接、
不得用同一列名掩盖定义差异。历史区段能否用新口径重算，取决于
该区段的事实粒度（明细/总量/未齐）。
"""
from facts import snapshot
from metrics import season_report

MEANING_KINDS = {
    "进场人次": "measure",
    "核实到场家庭": "measure",
    "订单家庭": "measure",
}


def column_registry(book):
    """(edition, tab) → {列名: 口径}，以及 列名 → {口径: [edition]}。"""
    by_edition = {}
    by_name = {}
    for row in book["template"]:
        for name, meaning in zip(row["names"], row["meanings"]):
            by_edition.setdefault((row["edition"], row["tab"]), {})[name] = meaning
            by_name.setdefault(name, {}).setdefault(meaning, []).append(row["edition"])
    return {"by_edition": by_edition, "by_name": by_name}


def column_plan(book, edition, tab, proposals):
    """判定拟写列 (列名, 口径)：复用 / 冲突 / 新增。"""
    reg = column_registry(book)
    plan = []
    for name, meaning in proposals:
        target = reg["by_edition"].get((edition, tab), {})
        if name in target:
            if target[name] == meaning:
                plan.append({"列": name, "判定": "复用", "口径": meaning})
            else:
                plan.append({
                    "列": name,
                    "判定": "冲突",
                    "口径": meaning,
                    "原因": f"{edition}/{tab} 已把「{name}」定义为「{target[name]}」，同列名不得掩盖定义差异；需另起列名或新版本",
                })
        else:
            history = reg["by_name"].get(name, {})
            note = "全新列" if not history else "历史同名口径：" + "、".join(
                f"{m}（{','.join(eds)}）" for m, eds in history.items()
            )
            plan.append({"列": name, "判定": "新增", "口径": meaning, "备注": note})
    return plan


def recompute_segments(book, meaning, seq=None):
    """用新口径可重算的历史区段，与只能并列保留原指标的区段。"""
    if meaning not in MEANING_KINDS:
        raise ValueError(f"未知口径：{meaning}（已知：{'、'.join(MEANING_KINDS)}）")
    snap = snapshot(book, seq)
    seasons = sorted({c["season"] for c in book["calendars"]})
    redo, keep = [], []
    need_detail = meaning == "核实到场家庭"
    for season in seasons:
        report = season_report(snap, season)
        if meaning == "订单家庭":
            redo.append(f"{season}（成团 {len(report['formed_groups'])}，订单家庭 {report['formed_party_units']}）")
            for order in report["unattributed_orders"]:
                keep.append({"区段": f"{season} 订单 {order}", "原因": "团号无入场记录，无法归因到季"})
            continue
        for (venue, school), cell in report["cells"].items():
            label = f"{season} {venue}/{school}"
            if not cell["closed"]:
                keep.append({"区段": label, "原因": "量未齐，只能并列保留原指标"})
            elif need_detail and cell["level"] != "明细":
                keep.append({"区段": label, "原因": "总量上报，无法重算家庭去重，只能并列保留原指标"})
            else:
                redo.append(label)
    return {"口径": meaning, "可重算": redo, "并列保留": keep}


def align_relative(book, seq=None):
    """按 (学校, 相对假期日) 对齐各季入场量；量未齐的轴点不可对齐。"""
    snap = snapshot(book, seq)
    seasons = sorted({c["season"] for c in book["calendars"]})
    reports = {s: season_report(snap, s) for s in seasons}
    axis = sorted({key for r in reports.values() for key in r["relative"]})
    rows = []
    for school, rel in axis:
        values, problems = {}, []
        for season in seasons:
            rep = reports[season]
            point = rep["relative"].get((school, rel))
            if point is None:
                values[season] = None
                continue
            school_cells = [c for (v, s2), c in rep["cells"].items() if s2 == school]
            if any(not c["closed"] for c in school_cells):
                problems.append(f"{season} {school} 量未齐")
            values[season] = {"人次": point["closed"], "暂定人次": point["provisional"]}
        row = {"学校": school, "相对日": rel, "各季": values}
        if problems:
            row["判定"] = "不可对齐"
            row["原因"] = "；".join(problems)
        elif any(v is None for v in values.values()):
            row["判定"] = "部分季无记录"
        else:
            row["判定"] = "可对齐"
            row["范围"] = f"{school} 相对日{rel}"
        rows.append(row)
    return rows


def measure_series(book, seq=None):
    """各列名跨 edition 的口径；同名异义禁止拼接，给出分别可报告的数值。"""
    reg = column_registry(book)
    snap = snapshot(book, seq)
    seasons = sorted({c["season"] for c in book["calendars"]})
    reports = {s: season_report(snap, s) for s in seasons}
    out = []
    for name, meanings in sorted(reg["by_name"].items()):
        entry = {"列": name, "历代口径": {m: eds for m, eds in meanings.items()}}
        known = [m for m in meanings if m in MEANING_KINDS]
        if len(meanings) > 1:
            entry["拼接"] = "禁止"
            entry["原因"] = "同名异义：" + "；".join(
                f"「{m}」见 {','.join(eds)}" for m, eds in meanings.items()
            )
            if known:
                entry["分别报告"] = {m: _meaning_values(m, reports) for m in known}
        elif not known:
            entry["类型"] = "维度列"
        else:
            entry["拼接"] = "可对齐"
            entry["范围"] = "各季 closed 区段"
            entry["数值"] = _meaning_values(known[0], reports)
        out.append(entry)
    return out


def _meaning_values(meaning, reports):
    values = {}
    for season, rep in reports.items():
        if meaning == "进场人次":
            values[season] = {"正式": rep["entries_closed"], "暂定": rep["entries_provisional"]}
        elif meaning == "核实到场家庭":
            values[season] = {
                "确切": rep["households_exact_count"],
                "未报格": [f"{v}/{s}" for v, s in rep["households_unknown_cells"]],
                "未齐格": [f"{v}/{s}" for v, s in rep["unclosed_cells"]],
            }
        elif meaning == "订单家庭":
            values[season] = rep["formed_party_units"]
    return values
