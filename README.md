# 跨校短假客群指标的分级解读与联营分发

合作方以工作簿列名接收同一期汇总及授权页。日历为当地日期，投递仅使用本地回执。

## 资料交换

`data/samples.json` 是合成样册。`fields` 给出有序列名，`rows` 按该顺序记录数据，`meaning` 标明单位或来源区别。没有填写的值用 `null` 表示。

- `calendars`：学校秋假窗口；假期相对日从 start 开始。 列：`season`, `school`, `city`, `start`, `end`。
- `entry`：household 为空表示没有可核对的家庭凭证。 列：`record`, `date`, `venue`, `school`, `group`, `household`, `entries`, `seq`。
- `channel`：party_units 指订单家庭份；取消单不当成成团。 列：`order`, `group`, `household`, `status`, `party_units`。
- `coverage`：level 为明细或总量；closed 表示承办方是否明确报告齐。 列：`season`, `venue`, `school`, `level`, `closed`, `seq`。
- `template`：已有工作簿的精确列名与当期定义；同一列名可有历史口径。 列：`edition`, `tab`, `names`, `meanings`。
- `grants`：scope=联合或具体学校/场馆；最高 seq 记录权限变化。 列：`recipient`, `scope`, `allowed`, `seq`。
- `dispatch`：旧回执与当前已排期但未发的记录。 列：`edition`, `week`, `recipient`, `approved_seq`, `due`, `result`。

`entry` / `coverage` / `grants` 的 `seq` 是全局操作序号：同一键取最高 seq 为有效版本。场馆补齐家庭凭证、承办方改报覆盖级别、收件人授权变化，都是同键更高 seq 的新行；`approved_seq` 即批准时点的快照序号。

## 指标定义（metrics.DEFINITIONS）

- **参与者**：进场人次，`entry.entries` 求和，同一 `record` 取最高 seq。
- **家庭**：核实到场家庭，明细且报告齐的格内 `household` 去重。跨馆刷同一凭证只记一次；总量上报的格家庭数未报，不假定重叠，也不以零计。
- **成团**：渠道订单存在核销记录的团；延期、取消不计入。
- **假期相对日**：入场日期与该校当季 `start` 的日差，`start` 当日为 0；两座城错峰放假时按 (学校, 相对日) 对齐。

未报告齐（closed=false）的格只入暂定人次，不进正式发布值；每个数字都带来源记录号。

## 列口径与同比（editions.py）

- 复用列名必须口径一致；同名异义禁止拼接，也不得用同一列名掩盖定义差异（如 `亲子量` 2025=订单家庭、2026=核实到场家庭）。能对齐的注明范围（各季 closed 区段），不能对齐的给出原因和分别可报告的数值。
- 历史区段能否用新口径重算取决于事实粒度：明细且齐的区段可重算；总量上报或量未齐的区段只能并列保留原指标。

## 分发规则（plan.py）

页面由授权 scope 推导：`联合` → 共享总页；学校/场馆 scope → 所辖页（学校只看参与本校的团）；仅有联合 scope 的收件人只收可核对的联盟汇总。共享总页要求涉及格全部报告齐才可发，且同一批分发的共享总数取自同一 seq，不会彼此冲突。

- 授权撤回后，原批准材料不能直接发；仍准确且有权查看的部分改派后继续发，其余不陪绑。
- 已送达材料不可覆盖。同一 (edition, week, recipient) 在送达之后的新行即更正，承接该期；回执可确认谁看过哪个版本、谁还没发。
- 投递结果用词：`送达` / `待发` / `待数据` / `待授权` / `已改期` / `已改派`。以新周次重用排期时，量未齐的留队等数据、授权未齐的移出待发等授权，不会一键把所有人留在待发队列。

## 检视

使用 Python 3.11，资料读取不依赖第三方包。

```sh
python3 source_book.py data/samples.json                 # 各表记录数
python3 briefing.py data/samples.json                    # 全览：定义、指标、同比、分发
python3 briefing.py data/samples.json metrics --season 2026
python3 briefing.py data/samples.json yoy
python3 briefing.py data/samples.json columns 亲子量=核实到场家庭 --edition 2026 --tab 联合
python3 briefing.py data/samples.json dispatch
python3 briefing.py data/samples.json reschedule --week 47 --due 11-24
python3 -m unittest discover -s tests -v
```

`source_book.py` 只核对表头、行宽和基础引用；分析结果由 `briefing.py` 生成。
