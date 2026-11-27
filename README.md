# quant-research-discipline

**面向自用资金的低频量化研究纪律：先算成本与期望值，再谈策略。**

A discipline-first quant research workflow. It does not hunt for alpha; it first tells you whether hunting is economically possible at your capital size.

> 不构成投资建议。不向他人提供信号，不代客管理资金。交易所在地区的政策风险自担，本金按"可全损"处理。

## 为什么先算账

散户亏钱的入口不是"策略不好"，是**换手率 × 成本**：

| 年往返次数 | 成本占本金/年 |
|---|---|
| 20 | 6% |
| 50 | 15% |
| 100 | 30% |
| 200 | 60% |

年成本占比 > 15% 即否决——15% 对应约 50 次/年，这是自用低频的上限。

再用期望值筛一遍：

```
期望 = p × (本金 × 年化净收益) − 时间成本 − 固定成本
```

本金 10 万、p=10%、年化 15%、投入 300 小时（时薪 50）时，期望约 **−15,000 元**；打平所需成功率超过 100%，数学上不可能。

**结论：本金低于 30 万人民币（估算阈值），自用量化的经济性不成立——除非你把它当学费。**

## 四条验收闸门

1. **成本后为正** — 扣手续费、点差、滑点、funding 后净收益 > 0
2. **样本外不衰减** — 样本外 / 样本内 ≥ 50%，必须 walk-forward + purge
3. **试验次数已记账** — 不记账的 Sharpe 视为无效
4. **第三方可复现** — 给数据、参数、成本假设，他人能跑出同量级结果

第 3 条最容易被跳过，也最致命：零信号下试 N 次得到的最大 Sharpe 期望约为 `√(2 ln N)`。试 30 次看到 2.6，那还在噪声线以内。

## 结构

```
.
├── SKILL.md
├── references/
│   ├── cost-and-turnover.md          # 成本构成、换手表、盈亏平衡推导、三种死法
│   └── acceptance-gates.md           # 四道闸门细则、噪声线表、10 条自欺清单
└── scripts/
    └── quant_check.py                # cost / breakeven / trial add|stats
```

## 用法

```bash
# 1) 成本占比与打平所需毛利
python3 scripts/quant_check.py cost --capital 100000 --trades 100 --roundtrip-bps 30

# 2) 期望值与合作门槛
python3 scripts/quant_check.py breakeven --capital 100000 --hours 300 \
  --hourly 50 --p 0.10 --net-annual 0.15 --fixed-cost 2000

# 3) 试验记账 + 噪声线比对
python3 scripts/quant_check.py trial add --db trials.json \
  --strategy btc-ma --params "fast=20,slow=60" --is-sharpe 1.8 --oos-sharpe 0.9
python3 scripts/quant_check.py trial stats --db trials.json
```

`cost` 输出示例：

```
年成本占本金：30.00%
打平所需年化毛利：≥ 30.00%
✗ 超过 15% 闸门：换手过高，策略再好也会被成本吃光。先降频。
```

## 退出码

- **参数非法**（本金 ≤ 0、概率不在 (0,1)、Sharpe 非有限数值、台账 JSON 损坏等）：退出码 `1`，错误信息打印到终端。
- **闸门未过**（成本超线、期望为负、本金低于门槛、最高分未超噪声线）：仅打印 `✗` 提示，退出码仍为 `0`，便于在脚本或流水线中串联；如需按失败阻断，请在外部判断输出或自行封装。

## paper trading 的正确用途

模拟盘只验证**执行链路**（下单、撮合、滑点、异常恢复），**不验证 alpha**。把"模拟盘赚钱"当成"策略有效"，是本领域最常见的自欺——它的 P&L 账本是自证的，没有外部核验。

## 安装

```bash
cp -R quant-research-discipline ~/.doubao/agent_mode/workspace/.user_skills/
```

## License

MIT
