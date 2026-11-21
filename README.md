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

## 检视

使用 Python 3.11，资料读取不依赖第三方包。

```sh
python3 source_book.py data/samples.json
python3 -m unittest discover -s tests -v
```

资料读取命令列出各表记录数；测试检查交叉引用与格式，不生成分析结果。
