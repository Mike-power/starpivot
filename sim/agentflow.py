# -*- coding: utf-8 -*-
"""v0.8 Agent 多步工作流（创新度杠杆 L5 骨架，2026.9.27）。

动机：真实智能体任务不是单步问答，而是多步工作流（规划→工具调用→
汇总……）。多步带来两个结构性变化：
  1. 步骤串行依赖：第 i+1 步的可用时刻 = 第 i 步完成时刻——
     地面排队不再是静态批次，而是事件驱动的就绪链；
  2. 前缀跨步复用：同 workflow 的全部步骤共享系统提示前缀，
     且不同 workflow 若属同一智能体应用，前缀也相同——
     "一次前缀，全天复用"从单任务红利升级为工作流红利。

执行语义（诚实声明）：
  - 每步的路由在 workflow 创建时按该步的 (正确性, 置信度) 实现决定
    （c ≥ τ 且星上来得及 → 星上提交；否则地面升级）；
  - 星上步即时完成（ready + duration），并触发下一步就绪；
  - 地面步进入窗口排队（EDF + 可行性检查），完成时刻触发下一步就绪；
  - 任一步答错（误收）或超截止期 → 整个 workflow 失败（all-or-nothing）；
  - workflow 延迟 = 末步完成时刻 − 创建时刻。

概率契约：与 confidence.py 同形（σ(k(θ−x)) + bias + N(0,σ)），
但使用独立随机流（offset 20000），避免与单任务实验共享抽样。
"""

import math
import random
from dataclasses import dataclass, field

from energy import link_energy_j, onboard_energy_j
from model import Metrics
from queueing import _tx_time


def correctness_prob(x: float, theta_true: float = 0.3, sharpness: float = 10.0) -> float:
    return 1.0 / (1.0 + math.exp(-sharpness * (theta_true - x)))


@dataclass
class AgentStep:
    """工作流中的一个步骤。prefix_id 标识其所属智能体应用（共享前缀）。"""

    step_id: int
    workflow_id: int
    complexity: float            # 本步复杂度 x
    duration: float              # 星上处理/链路传输基准耗时（秒）
    prefix_id: int = 1           # 同一智能体应用的全部 workflow 共享前缀
    tx_prefix: float = 60.0      # 前缀首次上行的传输耗时（缓存未命中支付）
    tx_delta: float = 25.0       # 步骤增量传输耗时（每次必付，假设值）


@dataclass
class AgentWorkflow:
    workflow_id: int
    created_at: float
    deadline: float
    steps: list[AgentStep]


@dataclass
class StepProfile:
    correct: bool
    confidence: float


def gen_workflows(
    n: int = 50,
    n_steps: int = 3,
    seed: int = 0,
    horizon: float = 86400.0,
) -> list[AgentWorkflow]:
    """生成多步工作流流（独立随机流 offset 30000）。"""
    rng = random.Random(30_000 + seed)
    workflows: list[AgentWorkflow] = []
    sid = 0
    for wid in range(n):
        created = rng.uniform(0.0, horizon * 0.5)
        deadline = created + rng.uniform(14400.0, 57600.0)  # 4-16h 容忍（批处理级工作流）
        steps = []
        for _ in range(n_steps):
            steps.append(AgentStep(
                step_id=sid,
                workflow_id=wid,
                complexity=rng.uniform(0.0, 1.0),
                duration=rng.uniform(30.0, 120.0),
            ))
            sid += 1
        workflows.append(AgentWorkflow(wid, created, deadline, steps))
    return workflows


def gen_step_profiles(
    workflows: list[AgentWorkflow],
    theta_true: float = 0.3,
    sharpness: float = 10.0,
    bias: float = 0.0,
    sigma: float = 0.1,
    seed: int = 0,
) -> dict[int, StepProfile]:
    """逐步生成 (正确性, 置信度) 实现，同种子全策略共享（offset 20000）。"""
    rng = random.Random(20_000 + seed)
    profiles: dict[int, StepProfile] = {}
    for wf in workflows:
        for s in wf.steps:
            p = correctness_prob(s.complexity, theta_true, sharpness)
            correct = rng.random() < p
            c = min(1.0, max(0.0, p + bias + rng.gauss(0.0, sigma)))
            profiles[s.step_id] = StepProfile(correct=correct, confidence=c)
    return profiles


@dataclass
class _WfState:
    idx: int = 0                 # 下一个待执行步骤下标
    ready: float = 0.0           # 下一步就绪时刻
    alive: bool = True
    waiting: bool = False        # 有地面步在排队（就绪链被其阻塞）
    fail_cause: str = ""         # onboard_wrong / deadline / unfinished
    finish: float | None = None


def run_agentflow(
    workflows: list[AgentWorkflow],
    profiles: dict[int, StepProfile],
    windows: list,
    tau: float,
    edf: bool = True,
    admit: str = "feasible",
    use_cache: bool = True,
    retry_onboard: bool = False,
) -> tuple[Metrics, dict]:
    """事件驱动的多步工作流调度引擎。

    retry_onboard（步级补偿）：星上提交答错时不杀工作流，降级把该步
    送地面排队兜底（占用链路换工作流存活）。返回 (workflow 级 Metrics, 诊断计数)。
    Metrics 以 workflow 为单位 record（成功/延迟/链路占用/能耗）。
    """
    cache: dict | None = {} if use_cache else None
    states = {
        wf.workflow_id: _WfState(ready=wf.created_at)
        for wf in workflows
    }
    pending: list[dict] = []     # 地面步队列项 {step, ready_at, deadline, wid}
    m = Metrics()
    diag = {
        "onboard_steps": 0, "ground_steps": 0,
        "prefix_hit": 0, "prefix_miss": 0, "retried_steps": 0,
        "fail_onboard_wrong": 0, "fail_deadline": 0, "fail_unfinished": 0,
    }
    by_id = {wf.workflow_id: wf for wf in workflows}

    def fail(wid: int, cause: str, now: float) -> None:
        st = states[wid]
        if not st.alive:
            return
        st.alive = False
        st.fail_cause = cause
        diag[f"fail_{cause}"] += 1
        # 清掉该 workflow 未服务的地面步
        pending[:] = [e for e in pending if e["wid"] != wid]

    def advance(wf: AgentWorkflow, from_time: float) -> None:
        """从 from_time 起尽可能推进 onboard 步链；遇地面步入队并阻塞。"""
        st = states[wf.workflow_id]
        st.waiting = False           # 调用方确保前序地面步已完成
        while st.alive and st.idx < len(wf.steps):
            step = wf.steps[st.idx]
            prof = profiles[step.step_id]
            onboard_ok = from_time + step.duration <= wf.deadline
            if prof.confidence >= tau and onboard_ok:
                # 星上提交：即时完成；答错 = 误收
                if not prof.correct:
                    if retry_onboard:
                        # 步级补偿：误收不杀工作流，降级送地面兜底
                        diag["retried_steps"] += 1
                        pending.append({
                            "step": step, "ready_at": from_time,
                            "deadline": wf.deadline, "wid": wf.workflow_id,
                        })
                        diag["ground_steps"] += 1
                        st.idx += 1
                        st.ready = from_time
                        st.waiting = True
                        return
                    fail(wf.workflow_id, "onboard_wrong", from_time)
                    return
                diag["onboard_steps"] += 1
                m.energy_onboard_j += onboard_energy_j(step.duration)
                from_time += step.duration
                st.idx += 1
            else:
                # 地面升级：入队等待窗口（就绪时刻 = 前一步完成时刻）
                pending.append({
                    "step": step, "ready_at": from_time,
                    "deadline": wf.deadline, "wid": wf.workflow_id,
                })
                diag["ground_steps"] += 1
                st.idx += 1
                st.ready = from_time
                st.waiting = True        # 就绪链被该地面步阻塞
                return
        if st.idx >= len(wf.steps):
            st.alive = False
            st.finish = from_time
            if from_time <= wf.deadline:
                m.record(True, from_time - wf.created_at, used_ground_link=False)
            else:
                diag["fail_deadline"] += 1

    # 初始推进：所有 workflow 的首步（星上链可连续完成数步）
    for wf in workflows:
        advance(wf, wf.created_at)

    # 窗口服务循环（按开始时刻排序）
    for w in sorted(windows, key=lambda x: x.start):
        # 窗口开始前推进 onboard 链（仅限未被地面步阻塞的 workflow）
        for wf in workflows:
            st = states[wf.workflow_id]
            if (st.alive and not st.waiting
                    and st.idx < len(wf.steps) and st.ready <= w.start):
                advance(wf, st.ready)
        candidates = [e for e in pending if e["ready_at"] <= w.start]
        if not candidates:
            continue
        candidates.sort(key=lambda e: (e["deadline"] if edf else e["ready_at"]))
        offset = 0.0
        for e in candidates:
            step = e["step"]
            tx = _tx_time(step, cache)
            completion = w.start + offset + tx
            if completion > w.end:
                break                            # 窗口带宽耗尽，顺延下一窗口
            if cache is not None:
                if step.prefix_id in cache:
                    diag["prefix_hit"] += 1
                else:
                    diag["prefix_miss"] += 1
                cache[step.prefix_id] = cache.get(step.prefix_id, 0) + 1
            m.energy_link_j += link_energy_j(tx)
            if completion > e["deadline"]:
                if admit == "feasible":
                    # 必超时：快速失败，把带宽让出来（数据已发，电照花）
                    m.energy_link_j += 0.0
                    fail(e["wid"], "deadline", completion)
                    continue
                else:
                    fail(e["wid"], "deadline", completion)
                    offset += tx                 # v0.3a 语义：占用带宽但失败
                    continue
            # 地面步完成 → 推进后续 onboard 链
            # 建模假设：地面大模型答案正确（profile.correct 是星上小模型的
            # 实现，不能套用到地面步）——星上误收已由 retry/误收死路径刻画
            offset += tx
            m.ground_transfers += 1
            pending.remove(e)
            advance(by_id[e["wid"]], completion)

    # 仿真结束仍未完成的 workflow
    for wf in workflows:
        st = states[wf.workflow_id]
        if st.alive and st.finish is None:
            diag["fail_unfinished"] += 1
            st.alive = False
        if not st.alive and st.finish is None:
            m.record(False, 0.0, used_ground_link=False)
    return m, diag
