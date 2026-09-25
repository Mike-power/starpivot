# -*- coding: utf-8 -*-
"""星地协同调度策略（v0.1 贪心版）。

核心思想：对每个任务，同时评估"送往地面"和"星上硬解"两个选项的
端到端延迟，选可行且更快的那个；都不可行才失败。

这是"通信窗口感知的星地分层推理调度方法"的最小实现，
后续将升级为考虑任务排队、链路带宽、置信度的完整策略（拟申请专利点）。
"""

from model import Metrics, Task
from timeline import SyntheticTimeline


def star_ground_coop(
    tasks: list[Task],
    timeline: SyntheticTimeline,
    onboard_capability: float = 0.3,
) -> Metrics:
    m = Metrics()
    for t in tasks:
        # 选项 A：等通信窗口送地面
        g_start = timeline.next_window_start(t.created_at)
        ground_ok = g_start is not None and g_start + t.duration <= t.deadline
        ground_latency = g_start + t.duration - t.created_at if ground_ok else float("inf")

        # 选项 B：星上小模型硬解（复杂度不能超星上能力阈值）
        onboard_ok = (
            t.complexity <= onboard_capability
            and t.created_at + t.duration <= t.deadline
        )
        onboard_latency = t.duration if onboard_ok else float("inf")

        # 贪心决策：可行方案里取延迟最小者；并列时优先星上（省链路）
        if onboard_ok and (onboard_latency <= ground_latency):
            m.record(True, onboard_latency, used_ground_link=False)
        elif ground_ok:
            m.record(True, ground_latency, used_ground_link=True)
        else:
            m.record(False, 0.0, used_ground_link=False)
    return m
