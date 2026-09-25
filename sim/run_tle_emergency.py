# -*- coding: utf-8 -*-
"""v0.4 应急重规划 × TLE 真实轨道：论文实验完整版。

与 run_emergency.py（合成窗口）的区别：窗口来自 ISS 真实过境
（每天约 3 次、累计约 20 分钟），链路稀缺是真实默认值——
应急任务的"等不起窗口"困境在真实轨道下被推到极端。

用法：
    python run_tle_emergency.py            # 终端打印
    python run_tle_emergency.py --save     # 结果写入 benchmark/results/tle_emergency.md

说明：窗口随实际日期变化（每次运行不同），任务多种子取均值（固定种子可复现）。
"""

import statistics as stats
import sys
from pathlib import Path

from emergency import gen_scenario, run_online, run_static
from timeline_tle import TleTimeline

ONBOARD_CAP = 0.3
N_TASKS = 100
N_SEEDS = 5
STRATEGIES = ("static", "preempt", "preempt_feasible")


def main() -> None:
    timeline = TleTimeline(horizon=86400.0)  # 容量字段在排队/应急模型下不使用

    lines = [
        "# v0.4 应急重规划 × TLE 真实轨道（论文实验完整版）",
        "",
        f"- 卫星：ISS（NORAD 25544，CelesTrak 公开 TLE）",
        f"- {timeline.summary()}",
        f"- 任务：{N_TASKS} 个/场景 × {N_SEEDS} 种子（取均值）；星上能力阈值 {ONBOARD_CAP}",
        "- 应急任务：deadline 1800s；窗口抖动 ±300s（概率 5%，背景扰动）",
        "- 语义：窗口内串行服务，窗口时长即带宽预算",
        "- 指标：整体成功率 | 应急成功率 | 平均延迟(s) | 链路占用",
        "",
        "| 应急率 | 丢失率 | 策略 | 整体成功率 | 应急成功率 | 平均延迟 | 链路占用 |",
        "|---|---|---|---|---|---|---|",
    ]
    for emg_rate in (0.0, 0.05, 0.1):
        for loss_rate in (0.0, 0.1, 0.2):
            cells = {s: {"success": [], "emg": [], "latency": [], "link": []} for s in STRATEGIES}
            for seed in range(N_SEEDS):
                tasks, disruptions = gen_scenario(
                    timeline.windows, n=N_TASKS, emergency_rate=emg_rate,
                    loss_rate=loss_rate, seed=seed)
                for s in STRATEGIES:
                    if s == "static":
                        m = run_static(tasks, disruptions, list(timeline.windows))
                    else:
                        m = run_online(tasks, disruptions, list(timeline.windows),
                                       strategy=s, onboard_capability=ONBOARD_CAP)
                    cells[s]["success"].append(m.success_rate)
                    cells[s]["emg"].append(m.emergency_success_rate)
                    cells[s]["latency"].append(m.avg_latency)
                    cells[s]["link"].append(m.ground_transfers)
            for s in STRATEGIES:
                row = (
                    f"| {emg_rate:.0%} | {loss_rate:.0%} | {s} "
                    f"| {stats.mean(cells[s]['success']):.0%} "
                    f"| {stats.mean(cells[s]['emg']):.0%} "
                    f"| {stats.mean(cells[s]['latency']):.0f}s "
                    f"| {stats.mean(cells[s]['link']):.0f} |"
                )
                lines.append(row)
                print(row)
            print()

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "tle_emergency.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"已保存：{out}")


if __name__ == "__main__":
    main()
