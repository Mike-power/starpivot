# -*- coding: utf-8 -*-
"""v0.6 不确定性感知路由（confidence-aware routing，创新度杠杆 L1）。

动机（docs/创新度分析.md）：v0.3-v0.5 的硬阈值 θ 假设"复杂度 ≤ θ 则星上
必对、> θ 必错"——真实小模型的能力边界是**模糊的**：
任务越难，答对概率越低，且模型自评置信度与正确性强相关但不完美。
本模块把路由判据从"静态硬阈值"换成"运行时置信度"：

  星上小模型对每个任务给出 (答案, 自评置信度 c)：
  - c ≥ τ：提交星上答案（代价：c 高但答案错 = 误收，任务失败）
  - c < τ：升级上送地面排队（代价：本可答对却上送 = 误升级，占链路）

概率模型：correct_prob(x) = σ(k(θ_true - x))
  - k 大 = 能力边界锐利（接近 v0.3-v0.5 的硬阈值近似）
  - k 小 = 边界模糊（难任务仍有相当概率答对 → 硬阈值"浪费能力"）
置信度 c = clip(correct_prob + bias + N(0, σ), 0, 1)
  - bias=0   校准良好（置信度是无噪读数）
  - bias>0   过度自信（错答案也敢给高分 → 误收风险）
  - bias<0   不自信（好答案也只给低分 → 误升级、链路变贵）

可复现性契约：每个任务的 (正确性, 置信度) 由 gen_profiles 按种子一次性
抽取，同种子全部策略共享同一实现——对比差异来自策略，不来自运气。
"""

import math
import random
from dataclasses import dataclass

from model import Metrics, Task
from queueing import _serve_pending
from timeline import SyntheticTimeline


def correctness_prob(complexity: float, theta_true: float = 0.3, sharpness: float = 10.0) -> float:
    """任务复杂度 x 的星上答对概率（logistic 能力曲线）。"""
    return 1.0 / (1.0 + math.exp(-sharpness * (theta_true - complexity)))


@dataclass
class ConfidenceProfile:
    """一个任务在星上小模型上的一次实现：答对与否 + 自评置信度。"""
    correct: bool
    confidence: float


def gen_profiles(
    tasks: list[Task],
    theta_true: float = 0.3,
    sharpness: float = 10.0,
    bias: float = 0.0,
    sigma: float = 0.1,
    seed: int = 0,
) -> dict[int, ConfidenceProfile]:
    """为一批任务生成 (正确性, 置信度) 实现，同种子全策略共享。

    独立于 gen_tasks 的随机流（offset 10000），避免任务分布与
    模型表现的人造相关性。
    """
    rng = random.Random(10_000 + seed)
    profiles: dict[int, ConfidenceProfile] = {}
    for t in tasks:
        p = correctness_prob(t.complexity, theta_true, sharpness)
        correct = rng.random() < p
        c = min(1.0, max(0.0, p + bias + rng.gauss(0.0, sigma)))
        profiles[t.task_id] = ConfidenceProfile(correct=correct, confidence=c)
    return profiles


def _ground_estimate(t, timeline) -> float | None:
    """地面乐观估计：最早能独占窗口槽位的完成时刻（与 v0.3 同语义）。"""
    for w in timeline.windows:
        if w.end >= t.created_at:
            comp = max(w.start, t.created_at) + t.duration
            if comp <= w.end:
                return comp
    return None


def confidence_routed(
    tasks: list[Task],
    timeline: SyntheticTimeline,
    profiles: dict[int, ConfidenceProfile],
    tau: float,
    edf: bool = True,
    admit: str = "feasible",
) -> tuple[Metrics, dict]:
    """星地协同·置信度路由策略。

    c ≥ τ 且 deadline 可达 → 提交星上答案（对错按 profiles 实现）；
    c < τ（或星上来不及）→ 升级地面排队（EDF + 可行性检查）。
    返回 (指标, 诊断计数)。
    """
    pending: list[Task] = []
    m = Metrics()
    diag = {"onboard_accept": 0, "false_accept": 0, "escalated": 0, "false_reject": 0}
    for t in sorted(tasks, key=lambda x: x.created_at):
        prof = profiles[t.task_id]
        onboard_ok = t.created_at + t.duration <= t.deadline
        g_comp = _ground_estimate(t, timeline)
        ground_ok = g_comp is not None and g_comp <= t.deadline

        if prof.confidence >= tau and onboard_ok:
            diag["onboard_accept"] += 1
            if prof.correct:
                m.record(True, t.duration, used_ground_link=False)
            else:
                diag["false_accept"] += 1
                m.record(False, 0.0, used_ground_link=False)
        elif ground_ok:
            diag["escalated"] += 1
            if prof.correct:
                diag["false_reject"] += 1   # 本可星上答对，却花了链路
            pending.append(t)
        else:
            m.record(False, 0.0, used_ground_link=False)
    q = _serve_pending(pending, timeline.windows, edf, admit)
    m.total += q.total
    m.succeeded += q.succeeded
    m.latency_sum += q.latency_sum
    m.ground_transfers += q.ground_transfers
    return m, diag


def static_threshold_prob(
    tasks: list[Task],
    timeline: SyntheticTimeline,
    profiles: dict[int, ConfidenceProfile],
    theta_est: float,
    edf: bool = True,
    admit: str = "feasible",
) -> tuple[Metrics, dict]:
    """硬阈值基线（概率版）：x ≤ θ_est 才尝试星上，语义对齐 v0.3-v0.5，
    但正确性同样按 profiles 的概率实现——与置信度路由同场公平对比。"""
    pending: list[Task] = []
    m = Metrics()
    diag = {"onboard_accept": 0, "false_accept": 0, "escalated": 0, "false_reject": 0}
    for t in sorted(tasks, key=lambda x: x.created_at):
        prof = profiles[t.task_id]
        onboard_ok = t.complexity <= theta_est and t.created_at + t.duration <= t.deadline
        g_comp = _ground_estimate(t, timeline)
        ground_ok = g_comp is not None and g_comp <= t.deadline

        if onboard_ok:
            diag["onboard_accept"] += 1
            if prof.correct:
                m.record(True, t.duration, used_ground_link=False)
            else:
                diag["false_accept"] += 1
                m.record(False, 0.0, used_ground_link=False)
        elif ground_ok:
            diag["escalated"] += 1
            if prof.correct:
                diag["false_reject"] += 1
            pending.append(t)
        else:
            m.record(False, 0.0, used_ground_link=False)
    q = _serve_pending(pending, timeline.windows, edf, admit)
    m.total += q.total
    m.succeeded += q.succeeded
    m.latency_sum += q.latency_sum
    m.ground_transfers += q.ground_transfers
    return m, diag


def pure_star_prob(tasks: list[Task], profiles: dict[int, ConfidenceProfile]) -> Metrics:
    """纯星上（概率版）：全部任务星上硬做，无地面兜底。"""
    m = Metrics()
    for t in tasks:
        prof = profiles[t.task_id]
        ok = prof.correct and t.created_at + t.duration <= t.deadline
        m.record(ok, t.duration if ok else 0.0, used_ground_link=False)
    return m
