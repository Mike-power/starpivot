# -*- coding: utf-8 -*-
"""仰角阈值敏感性实验：min_elev_deg × 排队策略。

真实星座设计的核心权衡：仰角阈值设得低 → 过境次数多但窗口短、
链路质量差（路径长、多径干扰）；阈值设得高 → 窗口质量好但次数少。
本实验量化这个权衡对调度效果的影响，为「阈值选多少」提供数据支撑。

用法：
    python run_tle_elev_sweep.py            # 终端打印
    python run_tle_elev_sweep.py --save     # 结果写入 benchmark/results/tle_elev_sweep.md

说明：每个仰角档位重建 TleTimeline（过境窗口随阈值变化），
任务多种子取均值；窗口随实际日期变化（论文可讨论的真实世界因素）。
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
ELEV_LEVELS = (0.0, 5.0, 10.0, 20.0)


def main() -> None:
    lines = [
        "# 仰角阈值敏感性实验（TLE 真实轨道 × 排队策略）",
        "",
        f"- 卫星：ISS（NORAD 25544，CelesTrak 公开 TLE）",
        f"- 任务：{N_TASKS} 个/场景 × {N_SEEDS} 种子（取均值）；星上能力阈值 {ONBOARD_CAP}",
        "- 语义：窗口内串行服务；仰角阈值越低，过境越多、单窗越短（带宽 vs 次数的权衡）",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(任务数) | 窗口数 | 累计窗口时长(min)",
        "",
        "| 仰角阈值 | 窗口数 | 累计时长 | " + " | ".join(QUEUED_VARIANTS) + " |",
        "|" + "---|" * (3 + len(QUEUED_VARIANTS)),
    ]
    for elev in ELEV_LEVELS:
        timeline = TleTimeline(horizon=86400.0, min_elev_deg=elev)
        n_win = len(timeline.windows)
        total_min = sum(w.end - w.start for w in timeline.windows) / 60

        acc = {s: {"success": [], "latency": [], "link": []} for s in QUEUED_VARIANTS}
        for seed in range(N_SEEDS):
            tasks = gen_tasks(n=N_TASKS, seed=seed)
            for name, fn in QUEUED_VARIANTS.items():
                m = fn(tasks, timeline)
                acc[name]["success"].append(m.success_rate)
                acc[name]["latency"].append(m.avg_latency)
                acc[name]["link"].append(m.ground_transfers)

        cells = " | ".join(
            f"{stats.mean(acc[s]['success']):.0%}/{stats.mean(acc[s]['latency']):.0f}s"
            for s in QUEUED_VARIANTS
        )
        row = f"| {elev:.0f}° | {n_win} | {total_min:.0f}min | {cells} |"
        lines.append(row)
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "tle_elev_sweep.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
