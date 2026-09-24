# -*- coding: utf-8 -*-
"""仿真入口：生成场景 → 运行基线 → 输出对比。"""

from baselines import ground_only, star_only
from scenario import gen_tasks
from timeline import SyntheticTimeline


def main() -> None:
    tasks = gen_tasks(n=100, seed=42)
    timeline = SyntheticTimeline(horizon=86400.0)

    print("场景：100 个任务 / 1 天 / 每 90 分钟一次 10 分钟通信窗口\n")
    print(ground_only(tasks, timeline).report("纯地面"))
    print(star_only(tasks, onboard_capability=0.3).report("纯星上"))
    print("\n提示：两个基线各有明显短板——纯地面链路占用 100% 且延迟受窗口支配；")
    print("纯星上成功率受复杂度阈值限制。星地协同方案（本项目核心）将在此决策空间寻优。")


if __name__ == "__main__":
    main()
