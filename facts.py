"""从交换册还原事实：按 seq 快照、假期相对日、团与季的关联。

entry / coverage / grants 行各自携带全局操作序号 seq；
快照 S 取每个键 seq<=S 的最高版本。场馆补齐家庭凭证、承办方
改报覆盖级别、收件人授权变化，都体现为同键更高 seq 的新行。
channel / calendars / template 不带 seq，视为与快照无关的常驻资料。
"""
from datetime import date

SEQUENCED_TABLES = ("entry", "coverage", "grants")


def current_seq(book):
    """全册当前操作序号。"""
    seqs = [row["seq"] for name in SEQUENCED_TABLES for row in book[name] if row.get("seq") is not None]
    return max(seqs, default=0)


def _latest(rows, key_of, seq):
    chosen = {}
    for row in rows:
        row_seq = row.get("seq")
        if row_seq is None or row_seq > seq:
            continue
        key = key_of(row)
        if key not in chosen or chosen[key]["seq"] <= row_seq:
            chosen[key] = row
    return chosen


class Snapshot:
    """某一 seq 下的有效事实：入场记录、覆盖状态、授权状态。"""

    def __init__(self, book, seq):
        self.book = book
        self.seq = seq
        self.entries = sorted(
            _latest(book["entry"], lambda r: r["record"], seq).values(),
            key=lambda r: (r["record"], r["seq"]),
        )
        self.coverage = _latest(book["coverage"], lambda r: (r["season"], r["venue"], r["school"]), seq)
        self.grants = _latest(book["grants"], lambda r: (r["recipient"], r["scope"]), seq)

    def cell(self, season, venue, school):
        """某 (季, 场馆, 学校) 覆盖格的有效记录；无记录返回 None。"""
        return self.coverage.get((season, venue, school))

    def allowed(self, recipient, scope):
        """该 seq 下收件人对 scope 是否仍获授权。"""
        row = self.grants.get((recipient, scope))
        return bool(row and row["allowed"])


def snapshot(book, seq=None):
    """取指定 seq 的有效事实；seq=None 表示当前最新。"""
    return Snapshot(book, current_seq(book) if seq is None else seq)


def holiday_position(calendars, school, day_text):
    """返校历窗口内的 (season, 相对日)；start 当日为 0。窗外返回 None。"""
    day = date.fromisoformat(day_text)
    for row in calendars:
        if row["school"] != school:
            continue
        start = date.fromisoformat(row["start"])
        if start <= day <= date.fromisoformat(row["end"]):
            return row["season"], (day - start).days
    return None


def group_index(entries, calendars):
    """团号 → 出现的季、学校、场馆，用于把渠道订单归因到季。"""
    index = {}
    for row in entries:
        slot = index.setdefault(row["group"], {"seasons": set(), "schools": set(), "venues": set()})
        pos = holiday_position(calendars, row["school"], row["date"])
        if pos:
            slot["seasons"].add(pos[0])
        slot["schools"].add(row["school"])
        slot["venues"].add(row["venue"])
    return index
