# -*- coding: utf-8 -*-
"""合成通信窗口：按固定周期生成过境窗口，支持链路容量约束。

v0.2：每个窗口有容量上限（带宽受限），任务需要"预约"窗口槽位。
预约分两步——find() 只查询不占用，commit() 确认占用；
决策型策略（见 strategies.py）需要先比较再决定，两步拆分避免"占而不用的脏槽位"。
v0.3 计划：接入公开 TLE 轨道数据，用真实过境时间替换合成周期。
"""

from dataclasses import dataclass


@dataclass
class ContactWindow:
    start: float
    end: float
    capacity: int
    loads: int = 0  # 已预约的任务数

    def can_serve(self, t: float) -> bool:
        return self.end >= t and self.loads < self.capacity

    @property
    def full(self) -> bool:
        return self.loads >= self.capacity


class SyntheticTimeline:
    """周期过境时间线：每 period 秒一次时长 duration 的通信窗口。

    capacity: 单个窗口可传输的最大任务数，模拟带宽受限；
              不超过 capacity 个任务可在窗口开始时并行处理。
    """

    def __init__(
        self,
        period: float = 5400.0,
        duration: float = 600.0,
        horizon: float = 86400.0,
        capacity: int = 4,
    ):
        self.period = period
        self.duration = duration
        self.horizon = horizon
        self.capacity = capacity
        self.windows = self._build()

    def _build(self) -> list[ContactWindow]:
        windows = []
        t = 0.0
        while t < self.horizon:
            windows.append(ContactWindow(t, t + self.duration, self.capacity))
            t += self.period
        return windows

    def find(self, t: float) -> ContactWindow | None:
        """查询 t 时刻可预约的最早窗口（不占用槽位）。"""
        for w in self.windows:
            if w.can_serve(t):
                return w
        return None

    def commit(self, w: ContactWindow, t: float) -> float:
        """确认预约 w，占用一个槽位，返回处理开始时间 max(w.start, t)。"""
        w.loads += 1
        return max(w.start, t)
