# -*- coding: utf-8 -*-
"""L7 v0.10 准入控制（admission）：工作流创建时的关键路径可行性过滤。

动机（v0.9d 负结果的指向）：调度侧杠杆穷尽后，剩余超时死源于
"工作流关键路径 × 截止期"的结构性矛盾。与其让注定超时的工作流
白白燃烧链路与能耗，不如在创建时按乐观关键路径估计做准入决策——
主要收益是省能耗与带宽，次要收益（仅稀缺 regime）是通过缓解争用
救活边界工作流。

两个策略：
- "reject"（可行性过滤）：估计完成时刻 > 截止期 → 拒绝，不进入引擎；
- "relax"（截止期协商）：估计不可行 → 截止期放宽 γ 倍后再准入，
  以延迟容忍换成功（对照组：需求侧杠杆 vs 资源侧杠杆）；
- "hybrid"（组合）：先协商，协商后仍不可行 → 拒绝——把 relax 的
  成功收益和 reject 的能耗收益叠加，检验两杠杆是否正交。

估计口径（乐观、无争用）：
- 每步按期望路由：correctness_prob(x) ≥ τ 视为星上步（即时，耗时
  step.duration），否则地面步（等待 = 就绪时刻到下一窗口开始的
  相位 + tx + compute，服务乐观取窗口起点）；
- 不抽样、不读取 profile 实现——只用创建时刻可知的信息，
  符合"创建时决策"的工程语义。

诚实声明：这是乐观估计（无视争用与误收重试），会漏判一部分
实际超时的工作流（估计可行但死于争用）——准入不是预言机，
而是"显著削减无效燃烧"的统计机制，收益以能耗/链路口径度量。
"""

import bisect

from agentflow import correctness_prob

INF = float("inf")


def estimate_finish(wf, win_starts: list[float], tau: float,
                    serve_fn=None) -> float:
    """乐观关键路径估计：返回估计完成时刻（无穷大 = 地面步无窗可用）。"""
    t = wf.created_at
    for step in wf.steps:
        if correctness_prob(step.complexity) >= tau:
            t += step.duration                       # 星上步：即时串联
        else:
            if serve_fn is not None:
                tx, compute = serve_fn(step, {})     # 独立缓存 dict：保守口径
            else:
                tx, compute = step.duration, 0.0
            i = bisect.bisect_right(win_starts, t)
            if i >= len(win_starts):
                return INF
            t = win_starts[i] + tx + compute         # 乐观：下一窗口起点即服务
    return t


def admit_workflows(workflows, win_starts, tau, policy: str = "off",
                    gamma: float = 1.5, serve_fn=None):
    """创建时准入过滤。

    policy: "off"    全量准入（基线）
            "reject" 关键路径不可行 → 拒绝（返回拒绝数）
            "relax"  不可行 → 截止期 ×γ 后准入（截止期协商）
            "hybrid" 先 relax，仍不可行 → 拒绝（组合杠杆）
    返回 (accepted, rejected_count)。
    """
    if policy == "off":
        return list(workflows), 0
    accepted: list = []
    rejected = 0
    for wf in workflows:
        est = estimate_finish(wf, win_starts, tau, serve_fn)
        if est <= wf.deadline:
            accepted.append(wf)
            continue
        # 不可行：relax 与 hybrid 先协商（created_at 为锚，避免重复放宽漂移）
        if policy in ("relax", "hybrid"):
            wf.deadline = wf.created_at + (wf.deadline - wf.created_at) * gamma
            est = estimate_finish(wf, win_starts, tau, serve_fn)
            if est <= wf.deadline:
                accepted.append(wf)
                continue
        if policy in ("reject", "hybrid"):
            rejected += 1
        else:  # 纯 relax：协商后照单全收
            accepted.append(wf)
    return accepted, rejected
