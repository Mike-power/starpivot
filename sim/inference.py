# -*- coding: utf-8 -*-
"""v0.9 TTFT/TPOT 真实推理延迟耦合。

v0.3-v0.8 的黑箱假设：链路传输耗时 = 任务时长（duration），地面推理
"瞬间完成"。真实 LLM serving 中地面处理延迟由三段组成：

  地面处理延迟 = 链路传输（前缀 + 增量 token）          ← 占窗口带宽
               + TTFT（prefill，输入长度驱动）           ← 不占窗口带宽*
               + TPOT（decode，输出长度驱动）            ← 不占窗口带宽*

* 简化声明：prefill/decode 在窗口结束后由地面站计算，结果下传是小
payload（数百 token，毫秒级），窗口带宽只被任务上行的 prefix+delta
token 占用。这是 README 声明的工程假设，常数待 12 月实测校准。

关键洞察（本实验要量化的）：L2 前缀缓存命中**不止省链路秒数**，还省
prefill 计算（命中时 prefill 只算 delta 部分）。v0.3-v0.8 只统计了
链路红利，prefill 红利被漏算——前缀缓存的真实收益接近翻倍。

token 口径假设（README 声明）：
  - input_tokens 含共享前缀部分；
  - 前缀 token 占比 = tx_prefix / (tx_prefix + tx_delta)，即按链路
    耗时占比把 input_tokens 拆成 prefix/delta 两段；
  - 缓存未命中：tx 与 prefill 都付全量；命中：只付 delta。

专利视角：把推理侧 TTFT/TPOT 引入窗口调度，使"窗口占用"与"任务完成
时刻"解耦，是调度目标函数从带宽约束扩展到"带宽+算力"双约束的建模
特征，可与创新点③（prefix caching）合并主张。
"""

import random

from model import Task

# --- 工程常数（假设值，待 12 月实测校准，README 声明）---
TX_TOKENS_PER_S = 50.0        # 星地上行链路吞吐（token/s，窄带假设）
PREFILL_TOKENS_PER_S = 1000.0  # 地面 prefill 算力（token/s）
DECODE_TOKENS_PER_S = 20.0     # 地面 decode 吞吐（token/s，TPOT=50ms/token）


def assign_tokens(tasks: list[Task], seed: int) -> None:
    """给任务填 input/output_tokens（就地修改）。

    用独立随机流（seed 偏移 40_000），不触碰 gen_tasks 的 RNG 流，
    保护既有实验的基线可复现性（README 记录过 prefix_cfg 改流导致
    基线漂移的前科）。
    """
    rng = random.Random(40_000 + seed)
    for t in tasks:
        t.input_tokens = rng.randint(200, 2000)
        t.output_tokens = rng.randint(50, 500)


def _prefix_ratio(t: Task) -> float:
    """共享前缀占 input_tokens 的比例，按链路耗时占比估计。"""
    total = t.tx_prefix + t.tx_delta
    if total <= 0 or t.input_tokens <= 0:
        return 0.0
    return min(1.0, t.tx_prefix / total)


def serve_time(t: Task, cache: dict | None) -> tuple[float, float]:
    """返回 (tx_seconds, compute_seconds)。

    tx_seconds：占窗口带宽的上行传输耗时。
    compute_seconds：TTFT + TPOT，窗口后地面计算，不占带宽但计入
    任务完成时刻（created_at → completion 的端到端延迟）。

    input_tokens=0 时退回 v0.3-v0.8 语义：tx=duration、compute=0，
    保证未 assign_tokens 的旧实验行为完全不变（回归保障）。
    """
    if t.input_tokens <= 0:
        return t.duration, 0.0

    prefix_tokens = t.input_tokens * _prefix_ratio(t)
    delta_tokens = t.input_tokens - prefix_tokens
    hit = cache is not None and t.prefix_id in cache

    uplink_tokens = delta_tokens if hit else prefix_tokens + delta_tokens
    tx = uplink_tokens / TX_TOKENS_PER_S
    compute = uplink_tokens / PREFILL_TOKENS_PER_S + t.output_tokens / DECODE_TOKENS_PER_S
    return tx, compute


def assign_step_tokens(workflows, seed: int) -> None:
    """给 Agent 工作流的每步填 input/output_tokens（就地修改）。

    用独立随机流（seed 偏移 50_000），与 assign_tokens（40_000 段）、
    gen_workflows（30_000 段）、gen_step_profiles（20_000 段）互不干扰。
    对 AgentStep 同样适用（duck typing：字段名与 Task 一致），
    input_tokens=0 时 serve_time 自动退回 duration 语义。
    """
    rng = random.Random(50_000 + seed)
    for wf in workflows:
        for s in wf.steps:
            s.input_tokens = rng.randint(200, 2000)
            s.output_tokens = rng.randint(50, 500)
