# -*- coding: utf-8 -*-
"""参数扫描实验：多种子 × 多场景，输出聚合结果表。

用法：
    python experiments.py            # 终端打印结果表
    python experiments.py --save     # 同时写入 benchmark/results/

这是论文实验数据的来源框架：每个参数组合跑 n_seeds 个随机种子取均值，
保证结论不是"某个随机场景下的巧合"。
"""

import statistics as stats
import sys
from pathlib import Path

from baselines import ground_only, star_only
from queueing import ground_queued, star_ground_coop_queued
from scenario import gen_tasks
from strategies import star_ground_coop
from timeline import SyntheticTimeline

N_TASKS = 100
N_SEEDS = 5
ONBOARD_CAP = 0.3


def run_matrix(period: float, capacity: int, seeds: range) -> dict[str, dict]:
    """返回 {策略: {success: 均值, latency: 均值, link: 均值}}。"""
    acc: dict[str, dict[str, list]] = {
        s: {"success": [], "latency": [], "link": []}
        for s in ("纯地面", "纯星上", "星地协同")
    }
    for seed in seeds:
        tasks = gen_tasks(n=N_TASKS, seed=seed)
        for name, m in (
            ("纯地面", ground_only(tasks, SyntheticTimeline(period=period, capacity=capacity))),
            ("纯星上", star_only(tasks, onboard_capability=ONBOARD_CAP)),
            ("星地协同", star_ground_coop(tasks, SyntheticTimeline(period=period, capacity=capacity), onboard_capability=ONBOARD_CAP)),
        ):
            acc[name]["success"].append(m.success_rate)
            acc[name]["latency"].append(m.avg_latency)
            acc[name]["link"].append(m.ground_transfers)
    return {
        name: {k: stats.mean(v) for k, v in metrics.items()}
        for name, metrics in acc.items()
    }


# v0.3 排队策略矩阵：窗口时长即串行带宽，窗口越短越贴近真实受限链路
QUEUED_VARIANTS = {
    "纯地面+EDF":      lambda tasks, tl: ground_queued(tasks, tl, edf=True),
    "纯地面+FCFS":     lambda tasks, tl: ground_queued(tasks, tl, edf=False),
    "协同a-EDF":       lambda tasks, tl: star_ground_coop_queued(tasks, tl, onboard_capability=ONBOARD_CAP, edf=True),
    "协同a-FCFS":      lambda tasks, tl: star_ground_coop_queued(tasks, tl, onboard_capability=ONBOARD_CAP, edf=False),
    "协同b-EDF可行":   lambda tasks, tl: star_ground_coop_queued(tasks, tl, onboard_capability=ONBOARD_CAP, edf=True, admit="feasible"),
    "协同b-FCFS可行":  lambda tasks, tl: star_ground_coop_queued(tasks, tl, onboard_capability=ONBOARD_CAP, edf=False, admit="feasible"),
}


def run_queued_matrix(period: float, duration: float, seeds: range) -> dict[str, dict]:
    """排队感知矩阵：{变体: {success/latency/link 均值}}。

    与 run_matrix 的区别：容量语义不同——窗口内串行服务，
    窗口时长就是带宽预算，所以扫 period × duration 双因素。
    """
    acc: dict[str, dict[str, list]] = {
        s: {"success": [], "latency": [], "link": []} for s in QUEUED_VARIANTS
    }
    for seed in seeds:
        tasks = gen_tasks(n=N_TASKS, seed=seed)
        for name, fn in QUEUED_VARIANTS.items():
            m = fn(tasks, SyntheticTimeline(period=period, duration=duration))
            acc[name]["success"].append(m.success_rate)
            acc[name]["latency"].append(m.avg_latency)
            acc[name]["link"].append(m.ground_transfers)
    return {
        name: {k: stats.mean(v) for k, v in metrics.items()}
        for name, metrics in acc.items()
    }


def main() -> None:
    seeds = range(N_SEEDS)
    lines = [
        "# 参数扫描实验结果",
        "",
        f"- 任务数/场景：{N_TASKS}；随机种子数：{N_SEEDS}（取均值）；星上能力阈值：{ONBOARD_CAP}",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(任务数)",
        "",
        "| 过境周期 | 窗口容量 | 纯地面 | 纯星上 | 星地协同 |",
        "|---|---|---|---|---|",
    ]
    for period in (3600.0, 5400.0, 7200.0):
        for capacity in (999, 4):
            r = run_matrix(period, capacity, seeds)
            cell = lambda s: f"{r[s]['success']:.0%}/{r[s]['latency']:.0f}s/{r[s]['link']:.0f}"
            lines.append(f"| {period/3600:g}h | {capacity} | {cell('纯地面')} | {cell('纯星上')} | {cell('星地协同')} |")

    report = "\n".join(lines)
    print(report)
    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "sweep_v0.2.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"\n已保存：{out}")

    # v0.3 排队感知矩阵：period × duration 双因素
    q_lines = [
        "# v0.3 排队感知参数扫描（period × 窗口时长）",
        "",
        f"- 任务数/场景：{N_TASKS}；随机种子数：{N_SEEDS}（取均值）；星上能力阈值：{ONBOARD_CAP}",
        "- 语义：窗口内串行服务，窗口时长 = 带宽预算（时长越短链路越受限）",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(任务数)",
        "",
        "| 过境周期 | 窗口时长 | " + " | ".join(QUEUED_VARIANTS) + " |",
        "|" + "---|" * (2 + len(QUEUED_VARIANTS)),
    ]
    for period in (3600.0, 5400.0, 7200.0):
        for duration in (300.0, 600.0, 900.0):
            r = run_queued_matrix(period, duration, seeds)
            cells = " | ".join(
                f"{r[s]['success']:.0%}/{r[s]['latency']:.0f}s/{r[s]['link']:.0f}"
                for s in QUEUED_VARIANTS
            )
            q_lines.append(f"| {period/3600:g}h | {duration/60:g}min | {cells} |")

    q_report = "\n".join(q_lines)
    print("\n" + q_report)
    if "--save" in sys.argv:
        q_out = Path(__file__).parent.parent / "benchmark" / "results" / "sweep_v0.3.md"
        q_out.write_text(q_report, encoding="utf-8")
        print(f"\n已保存：{q_out}")


if __name__ == "__main__":
    main()
