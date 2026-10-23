# Investment Research Frameworks / 投资研究框架

中文投资研究问题清单与备忘录模板，用于整理公开证据、记录反证与复核条件。

## 使用方法

复制下方备忘录，为每个研究对象建立独立记录。每条论点附一手证据、披露日期和反证条件。人物视角仅用于提出问题，不作为结论依据。

## 林奇视角：可理解的业务

- 公司卖什么，谁付款，为何复购？
- 区分增长、周期反弹、困境反转和资产重估，分别验证。
- 将门店和订单观察与财务披露对照；体验只是线索。
- 增长需要多少资本？应收、存货和债务是否同步扩大？
- 什么指标会使原故事失效？

## 巴菲特视角：现金与资本配置

- 收入如何变成可分配现金？维持竞争力需要多少再投入？
- 客户为什么留下？竞争者能否低价复制？
- 管理层如何在再投资、收购、回购和分红之间取舍？
- 每股价值是否增长？检查股本稀释。
- 分开讨论企业质量和价格。

## 芒格视角：逆向与能力边界

- 什么机制会导致永久损失？
- 管理层与中介各有什么激励？
- 是否忽略基准案例、替代解释和机会成本？
- 哪些重要问题无法判断？
- 什么反方证据会改变结论？

## 并购研究

- 列明法律主体、股权关系与交易前后控制权。
- 区分现金、换股、或有支付、融资承诺与到账资金。
- 检查交割条件、批准、稀释、锁定与终止条款。
- 区分公告事实、管理层预期和个人推断。
- 未披露的审计、估值和资金来源列入待核实事项。

## 空白研究备忘录

研究对象：
研究日期：
资料截止日期：

### 业务与假设

客户、产品、付款方式、主要成本：
核心问题：
核心假设：
替代解释：

### 证据登记

| 论点 | 一手来源 | 披露日期 | 事实或推断 | 反证条件 |
| --- | --- | --- | --- | --- |
| 待填写 | | | | |

### 财务与资本配置

现金流、再投入、债务期限、股本变动；注明指标口径：

### 情景分析

| 情景 | 关键假设 | 计算方法 | 不确定性 |
| --- | --- | --- | --- |
| 保守 | | | |
| 基准 | | | |
| 乐观 | | | |

### 反方与复核

永久损失机制：
矛盾证据：
尚未核实的事项：
已验证的结论：
暂不下结论的部分：
下次复核时间或事件：

### 更新记录

| 日期 | 新证据 | 对判断的影响 |
| --- | --- | --- |
| | | |

## 范围与贡献

这是重新整理的研究方法，不是人物原文转载、投资建议、收益预测或自动交易系统，不含实时行情或估值。欢迎通过 Issue 或 Pull Request 改进清单与模板，请只提交可公开的信息。

## MIT License

Copyright (c) 2026 Patrick-linux

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Research Notebook CLI — v0.2.0

Python 3.10+，仅使用标准库，不需要安装依赖、API 密钥或联网。下载 research.py 后，在自己的本地工作目录运行：

```sh
python research.py --db demo.sqlite add "Fictional Example" --body "Initial hypothesis" --tags demo,software
python research.py --db demo.sqlite list --query Fictional --tag demo
python research.py --db demo.sqlite edit 1 --body "Revised hypothesis"
python research.py --db demo.sqlite history 1
python research.py --db demo.sqlite diff 1 1 2
python research.py --db demo.sqlite evidence 1 --claim "Synthetic claim" --source https://example.com/report --date 2026-10-23 --kind inference --falsifier "Counterexample"
python research.py --db demo.sqlite show 1
python research.py --db demo.sqlite export notebook.json --format json
python research.py --db demo.sqlite export notebook.csv --format csv
python research.py --db demo.sqlite export notebook.md --format md
python research.py --db imported.sqlite import notebook.json
python research.py selftest
```

### 能力与数据规则

- SQLite 本地保存笔记，支持中文搜索和规范化标签。
- 每次实质修改保留版本；无变化的保存不产生新版本。
- 证据记录区分 fact、inference、unknown，要求有效来源链接和披露日期，可记录反证条件。
- JSON 导入保留正文、标签和证据，为每条笔记分配新 ID；一次导入失败会整体回滚。重复导入会创建副本。
- 导出快照不包含修改历史；Markdown 保留证据，CSV 是笔记摘要，JSON 可重新导入。
- CSV 对可能被表格软件识别为公式的文本做前缀转义；不要把 CSV 当作无损备份格式。
- 导出拒绝覆盖已有文件或数据库。数据库没有加密，请保存在受保护的本地目录。
- 笔记的版本历史目前覆盖标题、正文、标签；证据采用追加记录，不纳入正文版本对比。
- 程序不会主动访问来源网址、获取行情、上传笔记或执行交易。导出内容可能含你自行输入的隐私，应自行审阅后再分享。

### 情景计算

```sh
python research.py scenario --cash-flow 100 --growth 0.03 --discount 0.10 --terminal-growth 0.02 --years 5
```

输入为最近一期现金流和小数形式的增长、折现率。未来第 t 年现金流为 CF0 × (1+g)^t，逐期折现；终值使用最后一期现金流 × (1+终期增长率)/(折现率−终期增长率)，再折现到今天。输出分开列示显性期现值、终值现值及终值占比。

使用不同假设分别运行，即可比较保守、基准和乐观情景。金额单位与输入相同，不是每股目标价；模型未计债务、股数变化、税收或概率权重。折现率必须大于终期增长率，程序拒绝非有限输入。

### 验证

`python research.py selftest` 包含 11 项自动测试，覆盖中文搜索、版本差异、无效证据、导入回滚、已知现金流计算结果、非法假设和 CSV 公式转义。另已验证新增→修改→证据→导出→导入的命令行流程。

### 更新日志

- 2026-10-23 / v0.2.0：加入可运行的本地研究笔记工具、证据追踪、现金流情景计算、三种导出与 JSON 导入，补充自动测试与隐私文件忽略规则。
- 2026-10-23 / 初始版：发布研究问题清单和空白备忘录模板。

当前是早期版本，尚无外部采用量或长期运行记录。后续改进将由实际问题与可复现反馈驱动。
