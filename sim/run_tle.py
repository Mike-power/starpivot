# -*- coding: utf-8 -*-
"""TLE 真实轨道场景：三方案对比。

用法：
    python run_tle.py            # 终端打印
    python run_tle.py --save     # 结果写入 benchmark/results/

说明：任务时刻以"今天"为仿真起点，每次运行任务相同（固定种子）、
窗口随实际日期变化——这本身是论文可讨论的真实世界因素。
"""

import sys
from pathlib import Path

from baselines import ground_only, star_only
from scenario import gen_tasks
from strategies import star_ground_coop
from timeline_tle import TleTimeline

ONBOARD_CAP = 0.3
CAPACITY = 4


def main() -> None:
    tasks = gen_tasks(n=100, seed=42)
    timeline = TleTimeline(horizon=86400.0, capacity=CAPACITY)

    lines = [
        "# TLE 真实轨道场景：三方案对比",
        "",
        f"- 卫星：ISS（NORAD 25544，CelesTrak 公开 TLE）",
        f"- {timeline.summary()}",
        f"- 任务：100 个 / 星上能力阈值 {ONBOARD_CAP} / 窗口容量 {CAPACITY}",
        "",
        "| 策略 | 成功率 | 平均延迟 | 链路占用 |",
        "|---|---|---|---|",
    ]
    for name, m in (
        ("纯地面", ground_only(tasks, TleTimeline(horizon=86400.0, capacity=CAPACITY))),
        ("纯星上", star_only(tasks, onboard_capability=ONBOARD_CAP)),
        ("星地协同", star_ground_coop(tasks, TleTimeline(horizon=86400.0, capacity=CAPACITY), onboard_capability=ONBOARD_CAP)),
    ):
        row = f"| {name} | {m.success_rate:.0%} | {m.avg_latency:.0f}s | {m.ground_transfers} |"
        lines.append(row)
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "tle_iss.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
