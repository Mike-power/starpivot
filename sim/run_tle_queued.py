# -*- coding: utf-8 -*-
"""TLE 真实轨道 + 排队感知调度：论文主实验场景。

与 run_tle.py 的区别：v0.2 假设窗口内任务并行、带宽可无限细分；
本脚本用 v0.3 排队模型（窗口内串行服务，窗口时长 = 带宽预算），
更贴近真实星地链路——过境窗口只有几分钟，任务逐个传输。

用法：
    python run_tle_queued.py            # 终端打印
    python run_tle_queued.py --save     # 结果写入 benchmark/results/

说明：排队路径不修改窗口的 capacity/loads 字段，同一次运行内
所有策略可安全共享同一时间线实例；任务多种子取均值（固定种子可复现），
窗口随实际日期变化（论文可讨论的真实世界因素）。
"""

import statistics as stats
import sys
from pathlib import Path

from experiments import QUEUED_VARIANTS
from scenario import gen_tasks
from timeline_tle import TleTimeline

ONBOARD_CAP = 0.3
N_TASKS = 100
N_SEEDS = 5


def main() -> None:
    timeline = TleTimeline(horizon=86400.0)  # 容量字段在排队模型下不使用

    acc: dict[str, dict[str, list]] = {
        s: {"success": [], "latency": [], "link": []} for s in QUEUED_VARIANTS
    }
    for seed in range(N_SEEDS):
        tasks = gen_tasks(n=N_TASKS, seed=seed)
        for name, fn in QUEUED_VARIANTS.items():
            m = fn(tasks, timeline)
            acc[name]["success"].append(m.success_rate)
            acc[name]["latency"].append(m.avg_latency)
            acc[name]["link"].append(m.ground_transfers)

    lines = [
        "# TLE 真实轨道 + 排队感知调度（论文主实验）",
        "",
        f"- 卫星：ISS（NORAD 25544，CelesTrak 公开 TLE）",
        f"- {timeline.summary()}",
        f"- 任务：{N_TASKS} 个/场景 × {N_SEEDS} 种子（取均值）/ 星上能力阈值 {ONBOARD_CAP}",
        "- 语义：窗口内串行服务，窗口时长即带宽预算",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(任务数)",
        "",
        "| 策略 | 成功率 | 平均延迟 | 链路占用 |",
        "|---|---|---|---|",
    ]
    for name in QUEUED_VARIANTS:
        r = {k: stats.mean(v) for k, v in acc[name].items()}
        row = f"| {name} | {r['success']:.0%} | {r['latency']:.0f}s | {r['link']:.0f} |"
        lines.append(row)
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "tle_iss_queued.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
