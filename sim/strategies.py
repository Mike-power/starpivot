# -*- coding: utf-8 -*-
"""星地协同调度策略（v0.2 链路感知版）。

核心思想：对每个任务，同时评估两个选项的端到端延迟——
  A. 送往地面：预约最早的**有空闲槽位**的通信窗口（带宽受限，窗口可能满员顺延）
  B. 星上硬解：复杂度不超星上能力阈值即可
选可行且更快者；都不可行才失败。

v0.1 的局限是假设链路无限带宽；v0.2 把"窗口满员"纳入决策后，
链路拥塞时星上方案的低延迟从"优势"变成"其他任务的生命线"。
后续升级（拟申请专利的技术路线）：
  - 任务排队建模：窗口内任务的排序优化（紧急者优先）
  - 链路带宽连续建模：按数据量而非任务数计量
  - 星上置信度决策：小模型不确定时主动上送，减少返工
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
        # 选项 A：地面——只查询不占用，决策定了再 commit
        w = timeline.find(t.created_at)
        ground_ok = False
        ground_latency = float("inf")
        if w is not None:
            start = max(w.start, t.created_at)
            ground_ok = start + t.duration <= t.deadline
            ground_latency = start + t.duration - t.created_at

        # 选项 B：星上小模型硬解
        onboard_ok = (
            t.complexity <= onboard_capability
            and t.created_at + t.duration <= t.deadline
        )
        onboard_latency = t.duration if onboard_ok else float("inf")

        # 贪心决策：可行方案取延迟最小；并列优先星上（把链路槽位让给别的任务）
        if onboard_ok and (onboard_latency <= ground_latency):
            m.record(True, onboard_latency, used_ground_link=False)
        elif ground_ok:
            timeline.commit(w, t.created_at)
            m.record(True, ground_latency, used_ground_link=True)
        else:
            m.record(False, 0.0, used_ground_link=False)
    return m
