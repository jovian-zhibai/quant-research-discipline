#!/usr/bin/env python3
"""自用量化的三件算术：成本、期望值、试验记账。

用法：
  quant_check.py cost --capital 100000 --trades 100 --roundtrip-bps 30
  quant_check.py breakeven --capital 100000 --hours 300 --hourly 50 --p 0.10 --net-annual 0.15
  quant_check.py trial add --db trials.json --strategy btc-ma --params "fast=20,slow=60" \
      --is-sharpe 1.8 --oos-sharpe 0.9
  quant_check.py trial stats --db trials.json

设计立场：先算账再研究。任何"回测很漂亮"都不能替代"成本后为正"。
"""

import argparse
import json
import math
import os
import sys
from datetime import date

COST_CEILING = 0.15   # 年成本占比上限
CAPITAL_FLOOR = 300_000  # 本金门槛（人民币，估算阈值）


def cmd_cost(args):
    if args.capital <= 0 or args.trades < 0:
        sys.exit("--capital 需 > 0，--trades 需 ≥ 0")
    cost_rate = args.trades * args.roundtrip_bps / 10000
    print(f"年交易次数：{args.trades}　单次往返成本：{args.roundtrip_bps} bp")
    print(f"年成本占本金：{cost_rate:.2%}")
    print(f"打平所需年化毛利：≥ {cost_rate:.2%}（仅为覆盖成本，未含税与资金占用）")
    print(f"按本金 {args.capital:,.0f} 元计，一年被成本吃掉：{args.capital * cost_rate:,.0f} 元")
    print()
    if cost_rate > COST_CEILING:
        print(f"✗ 超过 {COST_CEILING:.0%} 闸门：换手过高，策略再好也会被成本吃光。先降频。")
    else:
        print(f"✓ 在 {COST_CEILING:.0%} 闸门以内")
    print("\n每次交易次数变化对应的成本占比：")
    for t in (20, 50, 100, 200, 300):
        print(f"  {t:>4} 次/年 → {t * args.roundtrip_bps / 10000:.1%}")


def cmd_breakeven(args):
    if not 0 < args.p < 1:
        sys.exit("--p 必须在 (0,1) 之间")
    time_cost = args.hours * args.hourly
    profit = args.capital * args.net_annual
    expected = args.p * profit - time_cost - args.fixed_cost
    p_needed = (time_cost + args.fixed_cost) / profit if profit > 0 else float("inf")

    print(f"本金：{args.capital:,.0f}　成功时年化净收益假设：{args.net_annual:.1%}")
    print(f"成功时的年收益：{profit:,.0f} 元")
    print(f"投入时间：{args.hours} 小时 × {args.hourly} 元/小时 = {time_cost:,.0f} 元机会成本")
    if args.fixed_cost:
        print(f"固定成本（服务器/订阅/数据）：{args.fixed_cost:,.0f} 元")
    print(f"做成可用策略的概率 p：{args.p:.0%}")
    print()
    print(f"期望值 = p × 收益 − 时间成本 − 固定成本 = {expected:,.0f} 元")
    print(f"打平所需成功率：p ≥ {p_needed:.1%}" + ("（>100%，数学上不可能）" if p_needed > 1 else ""))
    print()
    if expected < 0:
        print("✗ 期望值为负。这不是投资，是学费。可以当学习投入，别记成投资回报。")
    else:
        print("✓ 期望值为正（注意：仍依赖 p 的估计，p 本身无公开数据可证）")
    if args.capital < CAPITAL_FLOOR:
        print(f"✗ 本金低于 {CAPITAL_FLOOR:,.0f} 元门槛：分母太小，摊不平时间成本。")
    print()
    print("不同本金下的期望值（同一 p 与年化假设）：")
    for c in (30_000, 100_000, 300_000, 500_000, 1_000_000):
        e = args.p * (c * args.net_annual) - time_cost - args.fixed_cost
        print(f"  本金 {c:>9,.0f} → 期望 {e:>10,.0f} 元")


def load(db):
    if not os.path.exists(db):
        return {"trials": []}
    with open(db, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            sys.exit(f"不是合法 JSON：{db}")
    data.setdefault("trials", [])
    return data


def cmd_trial_add(args):
    for name, v in (("--is-sharpe", args.is_sharpe), ("--oos-sharpe", args.oos_sharpe)):
        if v is not None and not math.isfinite(v):
            sys.exit(f"{name} 不是有限数值")
    data = load(args.db)
    item = {
        "id": max((t["id"] for t in data["trials"]), default=0) + 1,
        "created": date.today().isoformat(),
        "strategy": args.strategy,
        "params": args.params,
        "is_sharpe": args.is_sharpe,
        "oos_sharpe": args.oos_sharpe,
        "note": args.note or "",
    }
    data["trials"].append(item)
    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    with open(args.db, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已记录 trial #{item['id']}：{args.strategy}（{args.params}）")


def cmd_trial_stats(args):
    data = load(args.db)
    trials = data["trials"]
    if not trials:
        print("还没有记录任何试验。未记账的 Sharpe 一律视为无效。")
        return

    n = len(trials)
    is_scores = [t["is_sharpe"] for t in trials if t.get("is_sharpe") is not None]
    pairs = [(t["is_sharpe"], t["oos_sharpe"]) for t in trials
             if t.get("is_sharpe") is not None and t.get("oos_sharpe") is not None]

    print(f"试验总次数：{n}")
    if is_scores:
        best = max(is_scores)
        # 零信号下 N 次独立试验的最大值期望 ≈ sqrt(2 ln N) 个标准差
        noise_line = math.sqrt(2 * math.log(max(n, 2)))
        print(f"最高样本内 Sharpe：{best:.2f}")
        print(f"零信号下 {n} 次试验的最大值期望约：{noise_line:.2f}（近似）")
        if best <= noise_line:
            print("✗ 最高分并未超过'纯噪声也能达到'的水平。这不是发现，是抽样。")
        else:
            print("✓ 最高分高于噪声线；仍需样本外与成本后为正佐证。")
    if pairs:
        decays = [o / i for i, o in pairs if i not in (0, None)]
        if decays:
            print(f"样本外/样本内 平均衰减：{sum(decays) / len(decays):.0%}（闸门要求 ≥ 50%）")
    print(f"越过 30 次试验的线了吗：{'是（多重检验偏差显著）' if n > 30 else '否'}")


def main():
    p = argparse.ArgumentParser(description="自用量化研究的三件算术")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cost", help="年成本占比与打平毛利")
    c.add_argument("--capital", type=float, required=True)
    c.add_argument("--trades", type=int, required=True, help="年往返交易次数")
    c.add_argument("--roundtrip-bps", type=float, default=30, help="单次往返成本（基点）")
    c.set_defaults(func=cmd_cost)

    b = sub.add_parser("breakeven", help="期望值与合作门槛")
    b.add_argument("--capital", type=float, required=True)
    b.add_argument("--hours", type=float, required=True, help="投入小时数")
    b.add_argument("--hourly", type=float, default=50, help="时薪折算")
    b.add_argument("--p", type=float, default=0.10, help="做成可用策略的概率")
    b.add_argument("--net-annual", type=float, default=0.15, help="成功时年化净收益")
    b.add_argument("--fixed-cost", type=float, default=0, help="固定成本")
    b.set_defaults(func=cmd_breakeven)

    t = sub.add_parser("trial", help="试验记账")
    tsub = t.add_subparsers(dest="tcmd", required=True)
    ta = tsub.add_parser("add")
    ta.add_argument("--db", required=True)
    ta.add_argument("--strategy", required=True)
    ta.add_argument("--params", required=True)
    ta.add_argument("--is-sharpe", type=float)
    ta.add_argument("--oos-sharpe", type=float)
    ta.add_argument("--note", default="")
    ta.set_defaults(func=cmd_trial_add)
    ts = tsub.add_parser("stats")
    ts.add_argument("--db", required=True)
    ts.set_defaults(func=cmd_trial_stats)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
