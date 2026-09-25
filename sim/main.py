# -*- coding: utf-8 -*-
"""仿真入口：生成场景 → 运行各版本策略 → 输出对比。

对比三组场景：
  无限链路（capacity=999）：v0.1 原始设定，作对照
  受限链路（capacity=4）  ：贴近真实带宽约束，星地协同的核心战场
  排队感知（v0.3）        ：窗口内串行服务 + EDF/FCFS，最贴近真实链路
"""

from baselines import ground_only, star_only
from queueing import ground_queued, star_ground_coop_queued
from scenario import gen_tasks
from strategies import star_ground_coop
from timeline import SyntheticTimeline

CAP_ONBOARD = 0.3


def run_case(name: str, capacity: int) -> None:
    tasks = gen_tasks(n=100, seed=42)
    timeline = SyntheticTimeline(horizon=86400.0, capacity=capacity)
    print(f"--- {name}（窗口容量 {capacity}）---")
    print(ground_only(tasks, timeline).report("纯地面    "))
    timeline = SyntheticTimeline(horizon=86400.0, capacity=capacity)  # 时间线不复用，槽位独立
    print(star_only(tasks, onboard_capability=CAP_ONBOARD).report("纯星上    "))
    timeline = SyntheticTimeline(horizon=86400.0, capacity=capacity)
    print(star_ground_coop(tasks, timeline, onboard_capability=CAP_ONBOARD).report("协同 v0.2 "))
    print()


def run_queued_case(name: str) -> None:
    """v0.3：窗口内串行服务，链路带宽 = 窗口时长；EDF vs FCFS 消融。"""
    tasks = gen_tasks(n=100, seed=42)
    timeline = SyntheticTimeline(horizon=86400.0)  # 容量字段在排队模型下不使用
    print(f"--- {name} ---")
    print(ground_queued(tasks, timeline, edf=True).report("纯地面+EDF      "))
    print(star_ground_coop_queued(tasks, timeline, onboard_capability=CAP_ONBOARD, edf=True).report("协同v0.3a-EDF    "))
    print(star_ground_coop_queued(tasks, timeline, onboard_capability=CAP_ONBOARD, edf=False).report("协同v0.3a-FCFS   "))
    print(star_ground_coop_queued(tasks, timeline, onboard_capability=CAP_ONBOARD, edf=True, admit="feasible").report("协同v0.3b-EDF可行"))
    print(star_ground_coop_queued(tasks, timeline, onboard_capability=CAP_ONBOARD, edf=False, admit="feasible").report("协同v0.3b-FCFS可行"))
    print()


def main() -> None:
    print("场景：100 个任务 / 1 天 / 每 90 分钟一次 10 分钟通信窗口 / 星上能力阈值 0.3\n")
    run_case("对照组：无限链路", capacity=999)
    run_case("实验组：受限链路", capacity=4)
    run_queued_case("v0.3 排队感知：窗口内串行服务 + 紧急度优先（容量语义=窗口时长）")


if __name__ == "__main__":
    main()
