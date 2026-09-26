# -*- coding: utf-8 -*-
"""基线方案。

GROUND_ONLY: 纯地面——所有任务预约通信窗口送往地面（链路占用 100%）。
STAR_ONLY:   纯星上——只有复杂度 <= 星上能力阈值的任务能在星上硬解，其余失败。

两者都是"极端策略"；星地协同策略见 strategies.py。
链路容量约束（窗口槽位有限）对所有使用链路的策略一视同仁。
"""

from energy import link_energy_j, onboard_energy_j
from model import Metrics, Task
from timeline import SyntheticTimeline


def ground_only(tasks: list[Task], timeline: SyntheticTimeline) -> Metrics:
    m = Metrics()
    for t in tasks:
        w = timeline.find(t.created_at)          # 满员窗口自动顺延到下一个
        if w is None:
            m.record(False, 0.0, used_ground_link=True)
            continue
        start = timeline.commit(w, t.created_at)
        if start + t.duration > t.deadline:
            m.record(False, 0.0, used_ground_link=True, e_link=link_energy_j(t.duration))
        else:
            m.record(True, start + t.duration - t.created_at, used_ground_link=True,
                     e_link=link_energy_j(t.duration))
    return m


def star_only(tasks: list[Task], onboard_capability: float = 0.3) -> Metrics:
    m = Metrics()
    for t in tasks:
        # 星上能力有限：复杂度超阈值的任务星上无解，直接失败
        if t.complexity > onboard_capability or t.created_at + t.duration > t.deadline:
            m.record(False, 0.0, used_ground_link=False)
        else:
            m.record(True, t.duration, used_ground_link=False,
                     e_onboard=onboard_energy_j(t.duration))
    return m
