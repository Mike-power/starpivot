# -*- coding: utf-8 -*-
"""仿真入口：生成场景 → 运行基线 → 输出对比。"""

from baselines import ground_only, star_only
from scenario import gen_tasks
from strategies import star_ground_coop
from timeline import SyntheticTimeline


def main() -> None:
    tasks = gen_tasks(n=100, seed=42)
    timeline = SyntheticTimeline(horizon=86400.0)

    print("场景：100 个任务 / 1 天 / 每 90 分钟一次 10 分钟通信窗口\n")
    print(ground_only(tasks, timeline).report("纯地面  "))
    print(star_only(tasks, onboard_capability=0.3).report("纯星上  "))
    print(star_ground_coop(tasks, timeline, onboard_capability=0.3).report("星地协同"))


if __name__ == "__main__":
    main()
