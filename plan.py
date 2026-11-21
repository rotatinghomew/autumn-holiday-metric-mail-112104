"""分发计划：授权快照、批次一致、回执确认、更正承接、重排期处置。

工作簿列固定，不新增列；页面构成由授权 scope 推导：
- scope=联合 → 共享总页（联盟汇总，全部格 closed 才可发，保证同批共享总数一致）；
- scope=学校 → 所辖页，只看参与本校的团；
- scope=场馆 → 所辖页，只看本馆；
- 仅有联合 scope 的收件人（如旅行社）只收可核对的联盟汇总。

投递结果用词：送达 / 待发 / 待数据 / 待授权 / 已改期 / 已改派。
已送达行不可改；同一 (edition, week, recipient) 在送达之后出现的新行即更正，
承接该期。
"""
from facts import current_seq, holiday_position, snapshot
from metrics import season_report

STATUS = ("送达", "待发", "待数据", "待授权", "已改期", "已改派")


def _schools(book):
    return {r["school"] for r in book["calendars"]}


def _venues(book):
    return {r["venue"] for r in book["coverage"]} | {r["venue"] for r in book["entry"]}


def pages_for(book, snap, recipient):
    """该快照授权下收件人应得的页面清单。"""
    schools, venues = _schools(book), _venues(book)
    pages = []
    for (name, scope), row in sorted(snap.grants.items()):
        if name != recipient or not row["allowed"]:
            continue
        if scope == "联合":
            pages.append({"key": ("联合",), "tab": "联合", "scope": "联合"})
        elif scope in schools:
            pages.append({"key": ("所辖", "school", scope), "tab": "所辖", "scope": scope, "维度": "school"})
        elif scope in venues:
            pages.append({"key": ("所辖", "venue", scope), "tab": "所辖", "scope": scope, "维度": "venue"})
    return pages


def page_label(page):
    return page["scope"] if page["tab"] == "联合" else f"所辖/{page['scope']}"


def page_content(book, snap, season, page):
    """页面发布内容（指纹）：任何相关事实变化都会改变内容。"""
    report = season_report(snap, season)
    if page["tab"] == "联合":
        return {
            "人次": report["entries_closed"],
            "暂定人次": report["entries_provisional"],
            "核实家庭": report["households_exact"],
            "家庭未报格": [f"{v}/{s}" for v, s in report["households_unknown_cells"]],
            "未齐格": [f"{v}/{s}" for v, s in report["unclosed_cells"]],
            "成团": report["formed_groups"],
            "订单家庭": report["formed_party_units"],
        }
    detail = {}
    for row in snap.entries:
        pos = holiday_position(book["calendars"], row["school"], row["date"])
        if not pos or pos[0] != season:
            continue
        if page["维度"] == "school" and row["school"] != page["scope"]:
            continue
        if page["维度"] == "venue" and row["venue"] != page["scope"]:
            continue
        key = (row["venue"], row["school"], row["group"])
        detail[key] = detail.get(key, 0) + row["entries"]
    return {"rows": [[v, s, g, n] for (v, s, g), n in sorted(detail.items())]}


def page_closed(book, snap, season, page):
    """页面涉及的覆盖格是否全部报告齐；返回 (是否可发, 未齐格)。"""
    report = season_report(snap, season)
    gaps = []
    for (venue, school), cell in report["cells"].items():
        if page["tab"] == "所辖":
            if page["维度"] == "school" and school != page["scope"]:
                continue
            if page["维度"] == "venue" and venue != page["scope"]:
                continue
        if not cell["closed"]:
            gaps.append(f"{venue}/{school}")
    return (not gaps, gaps)


def _page_verdict(book, approved, now, season, page, approved_seq):
    stale = page_content(book, approved, season, page) != page_content(book, now, season, page)
    closed, gaps = page_closed(book, now, season, page)
    if not closed:
        return {"页": page_label(page), "处置": "待数据", "缺口": gaps, "原因": "量未齐"}
    if stale:
        return {"页": page_label(page), "处置": "改派", "原因": "事实已更新，按当前 seq 重算", "approved_seq": now.seq}
    return {"页": page_label(page), "处置": "可发", "approved_seq": approved_seq}


def _overall(items):
    sendable = [i for i in items if i["处置"] in ("可发", "改派")]
    if sendable and len(sendable) == len(items):
        return "可发"
    if sendable:
        return "改派"
    if any(i["处置"] == "待数据" for i in items):
        return "待数据"
    if any(i["处置"] == "待授权" for i in items):
        return "待授权"
    return "移出队列"


def evaluate(book):
    """评估当前册：待发是否仍有效、已送达是否需要更正、回执状态。"""
    seq = current_seq(book)
    now = snapshot(book, seq)
    result = {"seq": seq, "批次": f"本批共享总数一律取自 seq={seq}，同批不会彼此冲突", "待发评估": [], "更正建议": [], "回执": receipts(book)}
    for row in book["dispatch"]:
        recipient, edition = row["recipient"], row["edition"]
        if row["result"] == "待发":
            approved = snapshot(book, row["approved_seq"])
            then_pages = {p["key"]: p for p in pages_for(book, approved, recipient)}
            now_pages = {p["key"]: p for p in pages_for(book, now, recipient)}
            items = []
            for key, page in then_pages.items():
                if key not in now_pages:
                    items.append({"页": page_label(page), "处置": "待授权", "原因": "授权已撤回，原批准材料不能直接发"})
                else:
                    items.append(_page_verdict(book, approved, now, edition, page, row["approved_seq"]))
            for key, page in now_pages.items():
                if key not in then_pages:
                    items.append(_page_verdict(book, approved, now, edition, page, row["approved_seq"]))
            result["待发评估"].append({
                "收件人": recipient, "edition": edition, "week": row["week"],
                "页面": items, "处置": _overall(items),
            })
        elif row["result"] == "送达":
            approved = snapshot(book, row["approved_seq"])
            changed = [
                page_label(page)
                for page in pages_for(book, approved, recipient)
                if page_content(book, approved, edition, page) != page_content(book, now, edition, page)
            ]
            if changed:
                closable = all(page_closed(book, now, edition, p)[0] for p in pages_for(book, now, recipient))
                result["更正建议"].append({
                    "收件人": recipient,
                    "承接": {"edition": edition, "week": row["week"], "approved_seq": row["approved_seq"]},
                    "变化页": changed,
                    "新approved_seq": seq,
                    "处置": "更正待发" if closable else "待数据",
                })
    return result


def receipts(book):
    """按本地回执确认：谁看过哪个版本、谁还没发。"""
    seen, unsent = {}, {}
    for row in book["dispatch"]:
        recipient = row["recipient"]
        if row["result"] == "送达":
            seen.setdefault(recipient, []).append(
                {"edition": row["edition"], "week": row["week"], "approved_seq": row["approved_seq"]}
            )
        else:
            unsent[(recipient, row["edition"], row["week"])] = {
                "edition": row["edition"], "week": row["week"],
                "approved_seq": row["approved_seq"], "result": row["result"],
            }
    out = {}
    for recipient in sorted(set(seen) | {k[0] for k in unsent}):
        out[recipient] = {
            "已送达版本": seen.get(recipient, []),
            "未发": [v for k, v in sorted(unsent.items()) if k[0] == recipient],
        }
    return out


def reschedule(book, week, due):
    """以新周次重用排期：返回新增与更新行，不改动原册。

    量未齐 → 待数据（留队标注缺口）；授权未齐 → 待授权（移出待发）；
    仍准确且有权查看的部分 → 改派后继续发。已送达行不动；
    更正承接原 (edition, week)，同一批共享同一 seq。
    """
    seq = current_seq(book)
    ev = evaluate(book)
    adds, updates = [], []
    for item in ev["待发评估"]:
        updates.append({
            "edition": item["edition"], "week": item["week"], "recipient": item["收件人"], "result": "已改期",
        })
        overall = item["处置"]
        status = {"可发": "待发", "改派": "待发", "待数据": "待数据"}.get(overall, "待授权")
        adds.append({
            "edition": item["edition"], "week": week, "recipient": item["收件人"],
            "approved_seq": seq, "due": due, "result": status, "页面": item["页面"],
        })
    for corr in ev["更正建议"]:
        adds.append({
            "edition": corr["承接"]["edition"], "week": corr["承接"]["week"],
            "recipient": corr["收件人"], "approved_seq": seq, "due": due,
            "result": "待发" if corr["处置"] == "更正待发" else "待数据",
            "承接": corr["承接"],
        })
    batch = {r["approved_seq"] for r in adds if r["result"] == "待发"}
    if len(batch) > 1:
        raise ValueError(f"同批 approved_seq 不一致：{sorted(batch)}")
    return {"seq": seq, "新增": adds, "更新": updates}
