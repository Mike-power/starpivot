# -*- coding: utf-8 -*-
"""L4 多星组网：星座规模 scaling 实验。

核心问题：单地面站 + N 星星座（相位偏移合成）时，
窗口池化（单天线窗口并集）下任务成功率如何随星数 N 变化？

- 星座生成：以 ISS TLE 为基准，平近点角加 360°/N 等相位偏移
  （Walker 式相位偏移，同轨道面，非真实多轨道面星座）
- 窗口池化：单天线不能同时跟踪两颗星，对所有星过境窗口取并集
- 策略：协同b-EDF可行（θ=0.3, admit="feasible"）+ 纯星上(θ=0.3) 天花板参照

用法：
    python run_constellation_l4.py            # 终端打印
    python run_constellation_l4.py --save     # 结果写入 benchmark/results/
"""

import statistics as stats
import sys
from pathlib import Path

from baselines import star_only
from queueing import star_ground_coop_queued
from scenario import gen_tasks
from timeline_constellation import ConstellationTimeline

ONBOARD_CAP = 0.3
N_TASKS = 100
N_SEEDS = 5
N_SATS = (1, 2, 4, 8)


def main() -> None:
    lines = [
        "# L4 多星组网：星座规模 scaling（TLE 相位偏移合成星座）",
        "",
        "- 星座：以 ISS TLE 为基准，平近点角等相位偏移合成 N 星（同轨道面）",
        "- 窗口：单地面站（上海）对所有星过境窗口取并集（单天线约束）",
        f"- 任务：{N_TASKS} 个/场景 × {N_SEEDS} 种子（取均值）/ 星上能力阈值 {ONBOARD_CAP}",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(任务数)",
        "",
        "| 星数 N | 窗口概况 | 成功率 | 平均延迟 | 链路占用 |",
        "|---|---|---|---|---|",
    ]

    for n in N_SATS:
        timeline = ConstellationTimeline(n_sats=n, horizon=86400.0)
        succ, lat, link = [], [], []
        for seed in range(N_SEEDS):
            tasks = gen_tasks(n=N_TASKS, seed=seed)
            m = star_ground_coop_queued(
                tasks, timeline, onboard_capability=ONBOARD_CAP,
                edf=True, admit="feasible",
            )
            succ.append(m.success_rate)
            lat.append(m.avg_latency)
            link.append(m.ground_transfers)
        row = (f"| {n} | {timeline.summary().split(' ', 1)[1]} | "
               f"{stats.mean(succ):.0%} | {stats.mean(lat):.0f}s | {stats.mean(link):.0f} |")
        lines.append(row)
        print(row)

    # 天花板参照：纯星上（θ=0.3），与地面站规模无关
    succ, lat, link = [], [], []
    for seed in range(N_SEEDS):
        tasks = gen_tasks(n=N_TASKS, seed=seed)
        m = star_only(tasks, onboard_capability=ONBOARD_CAP)
        succ.append(m.success_rate)
        lat.append(m.avg_latency)
        link.append(m.ground_transfers)
    row = (f"| 天花板参照 | 纯星上 θ={ONBOARD_CAP}（无地面） | "
           f"{stats.mean(succ):.0%} | {stats.mean(lat):.0f}s | {stats.mean(link):.0f} |")
    lines.append(row)
    print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "constellation_l4.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
