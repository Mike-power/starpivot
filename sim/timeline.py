# -*- coding: utf-8 -*-
"""合成通信窗口：按固定周期生成过境窗口。

v0.1 用合成周期模拟；v0.2 接入公开 TLE 轨道数据，用真实过境时间替换本模块。
"""

from dataclasses import dataclass


@dataclass
class ContactWindow:
    start: float
    end: float

    def contains(self, t: float) -> bool:
        return self.start <= t <= self.end


class SyntheticTimeline:
    """周期过境时间线：每 period 秒有一次时长为 duration 的通信窗口。"""

    def __init__(self, period: float = 5400.0, duration: float = 600.0, horizon: float = 86400.0):
        self.period = period      # 过境周期（默认 90 分钟）
        self.duration = duration  # 窗口时长（默认 10 分钟）
        self.horizon = horizon    # 仿真总时长（默认 1 天）
        self.windows = self._build()

    def _build(self) -> list[ContactWindow]:
        windows = []
        t = 0.0
        while t < self.horizon:
            windows.append(ContactWindow(t, t + self.duration))
            t += self.period
        return windows

    def next_window_start(self, t: float) -> float | None:
        """t 时刻之后（含正在进行的窗口）下一次可用窗口起点；无则 None。"""
        for w in self.windows:
            if w.end >= t:
                return max(w.start, t)
        return None
