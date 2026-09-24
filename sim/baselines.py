# -*- coding: utf-8 -*-
"""基线方案。

GROUND_ONLY: 纯地面——所有任务等通信窗口送往地面处理（链路占用 100%）。
STAR_ONLY:   纯星上——只有复杂度 <= 星上能力阈值的任务能在星上硬解，其余失败。

两者都是"极端策略"，星地协同方案（核心创新点）将在两者之间的决策空间中寻找最优，
11-12 月实现。
"""

from model import Metrics, Task
from timeline import SyntheticTimeline


def ground_only(tasks: list[Task], timeline: SyntheticTimeline) -> Metrics:
    m = Metrics()
    for t in tasks:
        # 等下一个通信窗口开始，再花 duration 处理
        start = timeline.next_window_start(t.created_at)
        if start is None or start + t.duration > t.deadline:
            m.record(False, 0.0, used_ground_link=True)
        else:
            m.record(True, start + t.duration - t.created_at, used_ground_link=True)
    return m


def star_only(tasks: list[Task], onboard_capability: float = 0.3) -> Metrics:
    m = Metrics()
    for t in tasks:
        # 星上能力有限：复杂度超阈值的任务星上无解，直接失败
        if t.complexity > onboard_capability or t.created_at + t.duration > t.deadline:
            m.record(False, 0.0, used_ground_link=False)
        else:
            m.record(True, t.duration, used_ground_link=False)
    return m
