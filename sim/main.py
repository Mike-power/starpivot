# -*- coding: utf-8 -*-
"""仿真入口：生成场景 → 运行三方案 → 输出对比。

对比两组场景：
  无限链路（capacity=999）：v0.1 原始设定，作对照
  受限链路（capacity=4）  ：贴近真实带宽约束，星地协同的核心战场
"""

from baselines import ground_only, star_only
from scenario import gen_tasks
from strategies import star_ground_coop
from timeline import SyntheticTimeline

CAP_ONBOARD = 0.3


def run_case(name: str, capacity: int) -> None:
    tasks = gen_tasks(n=100, seed=42)
    timeline = SyntheticTimeline(horizon=86400.0, capacity=capacity)
    print(f"--- {name}（窗口容量 {capacity}）---")
    print(ground_only(tasks, timeline).report("纯地面  "))
    timeline = SyntheticTimeline(horizon=86400.0, capacity=capacity)  # 时间线不复用，槽位独立
    print(star_only(tasks, onboard_capability=CAP_ONBOARD).report("纯星上  "))
    timeline = SyntheticTimeline(horizon=86400.0, capacity=capacity)
    print(star_ground_coop(tasks, timeline, onboard_capability=CAP_ONBOARD).report("星地协同"))
    print()


def main() -> None:
    print("场景：100 个任务 / 1 天 / 每 90 分钟一次 10 分钟通信窗口 / 星上能力阈值 0.3\n")
    run_case("对照组：无限链路", capacity=999)
    run_case("实验组：受限链路", capacity=4)


if __name__ == "__main__":
    main()
