# -*- coding: utf-8 -*-
"""v0.3 排队感知调度。

v0.2 的局限：假设窗口内任务并行处理、带宽无限细分。
v0.3 更贴近真实链路：
  - 窗口内任务**串行**服务（逐个占用链路），窗口时长即带宽预算；
  - 窗口开始时从等待队列中选任务，EDF（最早截止优先）或 FCFS（先来先服务）；
  - 未选中的任务顺延到下一窗口，超时则失败。

专利视角：窗口内任务排序策略（紧急者优先）是"通信窗口感知的星地分层
推理调度方法"的第二个技术特征；FCFS 对照组构成消融实验。
"""

from energy import link_energy_j, onboard_energy_j
from model import Metrics, Task
from timeline import ContactWindow, SyntheticTimeline


def _tx_time(t: Task, cache: dict | None) -> float:
    """任务的链路传输耗时。

    cache=None（默认）：保持 v0.3-v0.7 语义，传输耗时 = duration。
    cache=dict（L2 前缀增量）：前缀未命中付 tx_prefix + tx_delta，
    命中只付 tx_delta；dict 同时充当统计载体（prefix_id → 命中次数），
    miss = 该 id 首次出现，hit = 计数 ≥ 1 之后再出现。
    """
    if cache is None:
        return t.duration
    if t.prefix_id not in cache:
        return t.tx_prefix + t.tx_delta
    return t.tx_delta


def _serve_pending(
    pending: list[Task],
    windows: list[ContactWindow],
    edf: bool,
    admit: str = "all",
    cache: dict | None = None,
    serve_fn=None,
) -> Metrics:
    """串行服务：每个窗口从已产生的等待任务中按策略选任务逐个执行。

    服务规则：任务必须在窗口开始前产生；窗口从 start 开始串行执行，
    第 j 个任务的开始时刻 = window.start + 前 j-1 个任务的传输耗时之和。
    链路占用按实际传输成功的任务数计。

    admit 参数（论文消融维度之一）：
      "all"      按序 admitting——即使某任务排上队也必超时，仍占用带宽（v0.3a）；
      "feasible" 可行性检查——估算某任务即使立即服务也会超时，则快速失败、
                 不占带宽，把槽位让给后面的任务（v0.3b）。

    cache 参数（L2）：传 dict 启用前缀增量传输（见 _tx_time），
    首个任务付全量前缀，此后地面前缀缓存命中（对接 ground 侧 vLLM
    prefix caching 的创新点③）；传 None 保持 duration 语义。

    serve_fn 参数（v0.9）：可插拔服务耗时函数 (task, cache) ->
    (tx_seconds, compute_seconds)，见 inference.serve_time。窗口占用
    只加 tx_seconds；任务完成时刻 = start + tx + compute（compute
    为窗口后地面推理时间，不占带宽）。传 None 时 tx=_tx_time、
    compute=0，与 v0.3-v0.8 行为逐字节一致（回归保障）。
    """
    m = Metrics()
    leftover = sorted(pending, key=lambda t: t.created_at)
    for w in windows:
        candidates = [t for t in leftover if t.created_at <= w.start]
        if not candidates:
            continue
        candidates.sort(key=lambda t: (t.deadline if edf else t.created_at))
        offset = 0.0
        served = []
        for t in candidates:
            if serve_fn is not None:
                tx, compute = serve_fn(t, cache)
            else:
                tx, compute = _tx_time(t, cache), 0.0
            start = w.start + offset
            completion = start + tx + compute
            if completion > w.end:      # 窗口带宽耗尽，剩余顺延
                break
            served.append(t)
            offset += tx
            if cache is not None:
                cache[t.prefix_id] = cache.get(t.prefix_id, 0) + 1  # 数据已发出，无论结果
            if completion <= t.deadline:
                m.record(True, completion - t.created_at, used_ground_link=True, priority=t.priority,
                         e_link=link_energy_j(tx))
            elif admit == "feasible":   # 必超时：快速失败，把 offset 让出来
                offset -= tx            # 撤销本次占用
                # 能耗照常计入：数据已物理发出，结果虽被丢弃，电已经花了
                m.record(False, 0.0, used_ground_link=False, priority=t.priority,
                         e_link=link_energy_j(tx))
            else:                        # 排上队但处理完已超时（v0.3a 行为）
                m.record(False, 0.0, used_ground_link=True, priority=t.priority,
                         e_link=link_energy_j(tx))
        leftover = [t for t in leftover if t not in served]
    for t in leftover:                   # 仿真结束仍未排上队
        m.record(False, 0.0, used_ground_link=False, priority=t.priority)
    return m


def ground_queued(tasks: list[Task], timeline: SyntheticTimeline, edf: bool = True, admit: str = "all", cache: dict | None = None) -> Metrics:
    """纯地面 + 排队：所有任务进入等待队列，按窗口逐个服务。"""
    return _serve_pending(list(tasks), timeline.windows, edf, admit, cache)


def star_ground_coop_queued(
    tasks: list[Task],
    timeline: SyntheticTimeline,
    onboard_capability: float = 0.3,
    edf: bool = True,
    admit: str = "all",
    cache: dict | None = None,
    serve_fn=None,
) -> Metrics:
    """星地协同 v0.3：星上决策 + 地面排队。

    任务产生时先评估"星上硬解"（即时完成）与"送地面"（假设独占窗口的
    乐观估计）的延迟，星上可行且更快则星上处理；否则进入地面等待队列，
    由 _serve_pending 按 EDF/FCFS 服务。

    cache（L2）：传 dict 启用前缀增量传输，地面估计按 _tx_time 口径
    （缓存未命中按全量前缀估计，偏保守）。
    serve_fn（v0.9）：透传给 _serve_pending，见该函数文档。
    """
    pending: list[Task] = []
    m = Metrics()
    for t in sorted(tasks, key=lambda x: x.created_at):
        # 选项 B：星上即时处理
        onboard_ok = (
            t.complexity <= onboard_capability
            and t.created_at + t.duration <= t.deadline
        )
        # 选项 A：地面乐观估计（独占最早可行窗口）
        if serve_fn is not None:
            tx, compute = serve_fn(t, cache)
        else:
            tx, compute = _tx_time(t, cache), 0.0
        g_completion = None
        for w in timeline.windows:
            if w.end >= t.created_at:
                comp = max(w.start, t.created_at) + tx + compute
                if comp <= w.end:
                    g_completion = comp
                    break
        ground_ok = g_completion is not None and g_completion <= t.deadline

        if onboard_ok and (not ground_ok or t.duration < g_completion - t.created_at):
            m.record(True, t.duration, used_ground_link=False, priority=t.priority,
                     e_onboard=onboard_energy_j(t.duration))
        elif ground_ok:
            pending.append(t)
        else:
            m.record(False, 0.0, used_ground_link=False, priority=t.priority)
    q = _serve_pending(pending, timeline.windows, edf, admit, cache, serve_fn)
    # 合并两部分指标
    m.total += q.total
    m.succeeded += q.succeeded
    m.latency_sum += q.latency_sum
    m.ground_transfers += q.ground_transfers
    m.energy_onboard_j += q.energy_onboard_j
    m.energy_link_j += q.energy_link_j
    return m
