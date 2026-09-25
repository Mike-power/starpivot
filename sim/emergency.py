# -*- coding: utf-8 -*-
"""v0.4 应急重规划：事件驱动在线调度。

设计文档：docs/应急重规划场景设计.md。

与 v0.3 的本质区别：v0.3 是静态排程——任务集与窗口集在仿真前固定，
调度器本质是离线最优。v0.4 引入三类应急事件，调度器只能在线反应：

  - insert       应急任务插入（priority=1，deadline 极紧 1800s）
  - window_loss  窗口丢失（天气/站间冲突，队列任务顺延）
  - window_shift 窗口抖动（start/end 平移 ±delta，预报误差）

策略消融（对应设计文档第 4 节）：
  static           静态基线：对"事后完整信息"跑 v0.3b，不做在线反应
                   （被动但全知——代表"无重规划机制"的系统下限参考）
  preempt          抢占式：每个窗口服务前重排候选队列，应急任务插队
  preempt_feasible 抢占 + 可行性检查（检验 v0.3b 机制在动态环境是否依然成立）

简化假设（骨架阶段，见设计文档第 7 节）：
  - 在线策略对窗口的乐观估计看不到未来的扰动（真实在线系统的正常局限）；
  - 窗口内服务不中断（抢占发生在窗口边界，即队列排序时刻）。
"""

import random
from dataclasses import dataclass
from types import SimpleNamespace

from model import Metrics, Task
from queueing import star_ground_coop_queued
from scenario import gen_tasks
from timeline import ContactWindow

EMERGENCY_DEADLINE = 1800.0   # 应急任务最大可容忍等待（秒）


@dataclass
class Disruption:
    """一个应急事件。"""
    time: float                 # 事件发生时刻（仿真秒）
    kind: str                   # "insert" | "window_loss" | "window_shift"
    window_idx: int = -1        # window_loss / window_shift 的目标窗口下标
    delta: float = 0.0          # window_shift 的偏移量（秒）
    task: Task | None = None    # insert 事件携带的应急任务


def gen_scenario(
    windows: list[ContactWindow],
    n: int = 100,
    emergency_rate: float = 0.05,
    loss_rate: float = 0.1,
    shift_prob: float = 0.05,
    seed: int = 42,
    horizon: float = 86400.0,
) -> tuple[list[Task], list[Disruption]]:
    """生成场景：常规任务 + 应急事件序列（固定种子可复现）。

    应急任务不出现在任务集里，只通过 insert 事件"中途"到达——
    这是应急语义的核心：在线调度器事先不知道它们。
    """
    rng = random.Random(seed)
    tasks = gen_tasks(n=n, seed=seed, horizon=horizon)
    disruptions: list[Disruption] = []

    n_emg = int(n * emergency_rate)
    for k in range(n_emg):
        created = rng.uniform(0, horizon * 0.8)
        emg = Task(
            task_id=10000 + k,
            created_at=created,
            duration=rng.uniform(30, 300),
            complexity=rng.uniform(0, 1),
            deadline=created + EMERGENCY_DEADLINE,
            priority=1,
        )
        disruptions.append(Disruption(time=created, kind="insert", task=emg))

    if loss_rate > 0:
        n_loss = max(1, int(len(windows) * loss_rate))
        for idx in rng.sample(range(len(windows)), min(n_loss, len(windows))):
            disruptions.append(Disruption(
                time=windows[idx].start - 60.0, kind="window_loss", window_idx=idx))

    if shift_prob > 0:
        for idx, w in enumerate(windows):
            if rng.random() < shift_prob:
                disruptions.append(Disruption(
                    time=w.start - 120.0, kind="window_shift",
                    window_idx=idx, delta=rng.choice((-300.0, 300.0))))

    disruptions.sort(key=lambda d: d.time)
    return tasks, disruptions


def _apply_disruption_to_windows(d: Disruption, wins: list[ContactWindow], removed: set[int]) -> None:
    if d.kind == "window_loss":
        removed.add(d.window_idx)
    elif d.kind == "window_shift":
        w = wins[d.window_idx]
        w.start += d.delta
        w.end += d.delta


def run_static(tasks: list[Task], disruptions: list[Disruption], windows: list[ContactWindow],
               onboard_capability: float = 0.3) -> Metrics:
    """静态基线：扰动全部"事后"应用（窗口已删/已移、应急任务已到场），
    再跑 v0.3b 最优调度。代表没有重规划机制的系统。"""
    removed: set[int] = set()
    for d in disruptions:
        _apply_disruption_to_windows(d, windows, removed)
    final_windows = [w for i, w in enumerate(windows) if i not in removed]
    all_tasks = tasks + [d.task for d in disruptions if d.kind == "insert" and d.task]
    # star_ground_coop_queued 只用到 timeline.windows，用 SimpleNamespace 适配
    return star_ground_coop_queued(
        all_tasks, SimpleNamespace(windows=final_windows),
        onboard_capability=onboard_capability, edf=True, admit="feasible")


def run_online(tasks: list[Task], disruptions: list[Disruption], windows: list[ContactWindow],
               strategy: str = "preempt", onboard_capability: float = 0.3,
               edf: bool = True) -> Metrics:
    """事件驱动在线调度：每个窗口服务前先应用该时刻前的全部扰动并重新排序。"""
    assert strategy in ("preempt", "preempt_feasible")
    m = Metrics()
    pending: list[Task] = []
    removed: set[int] = set()
    wins = [ContactWindow(w.start, w.end, w.capacity) for w in windows]  # 拷贝，避免污染共享时间线
    arrivals = sorted(tasks, key=lambda t: t.created_at)

    def decide(t: Task) -> None:
        """任务到达决策（与 v0.3 星地协同同一规则）：星上硬解 / 入队 / 必死。"""
        onboard_ok = (
            t.complexity <= onboard_capability
            and t.created_at + t.duration <= t.deadline
        )
        g_completion = None
        for w in wins:
            if w.end >= t.created_at:
                comp = max(w.start, t.created_at) + t.duration
                if comp <= w.end:
                    g_completion = comp
                    break
        ground_ok = g_completion is not None and g_completion <= t.deadline
        if onboard_ok and (not ground_ok or t.duration < g_completion - t.created_at):
            m.record(True, t.duration, used_ground_link=False, priority=t.priority)
        elif ground_ok:
            pending.append(t)
        else:
            m.record(False, 0.0, used_ground_link=False, priority=t.priority)

    ai, di = 0, 0  # arrivals / disruptions 游标
    for wi, w in enumerate(wins):
        # 窗口服务前：先处理 time <= w.start 的扰动与到达
        while di < len(disruptions) and disruptions[di].time <= w.start:
            d = disruptions[di]
            if d.kind == "insert" and d.task is not None:
                decide(d.task)
            else:
                _apply_disruption_to_windows(d, wins, removed)
            di += 1
        if wi in removed:
            continue
        while ai < len(arrivals) and arrivals[ai].created_at <= w.start:
            decide(arrivals[ai])
            ai += 1

        # 抢占语义：应急任务（priority=1）排在队首，其余按 EDF/FCFS
        cands = [t for t in pending if t.created_at <= w.start]
        cands.sort(key=lambda t: (-t.priority, t.deadline if edf else t.created_at))

        offset = 0.0
        served = []
        for t in cands:
            start = w.start + offset
            completion = start + t.duration
            if completion > w.end:      # 窗口带宽耗尽，剩余顺延
                break
            served.append(t)
            offset += t.duration
            if completion <= t.deadline:
                m.record(True, completion - t.created_at, used_ground_link=True, priority=t.priority)
            elif strategy == "preempt_feasible":
                offset -= t.duration    # 必死任务不占带宽，槽位让给后面的任务
                m.record(False, 0.0, used_ground_link=False, priority=t.priority)
            else:
                m.record(False, 0.0, used_ground_link=True, priority=t.priority)
        pending = [t for t in pending if t not in served]

    # 仿真结束仍未排上队（含扰动残留事件对应的任务）
    while ai < len(arrivals):
        decide(arrivals[ai]); ai += 1
    while di < len(disruptions):
        d = disruptions[di]
        if d.kind == "insert" and d.task is not None:
            decide(d.task)
        di += 1
    for t in pending:
        m.record(False, 0.0, used_ground_link=False, priority=t.priority)
    return m
