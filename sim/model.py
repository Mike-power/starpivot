# -*- coding: utf-8 -*-
"""仿真核心模型：任务、卫星状态、指标。"""

from dataclasses import dataclass, field


@dataclass
class Task:
    """一个卫星任务请求。

    complexity: 任务复杂度 0.0~1.0。
        模拟"星上算力受限"：只有复杂度 <= 星上能力阈值的任务才可能由星上小模型处理，
        复杂任务理论上需要地面大模型——这正是星地协同调度要决策的核心变量。
    deadline: 任务最晚可开始处理的时间（秒），用于判定超时失败。
    """

    task_id: int
    created_at: float          # 任务产生时刻（仿真秒）
    duration: float            # 处理耗时（秒）
    complexity: float          # 0.0 ~ 1.0
    deadline: float            # 超时时刻（created_at + 最大可容忍等待）
    priority: int = 0          # 0=常规, 1=应急（v0.4 应急重规划场景）

    def expired(self, now: float) -> bool:
        return now > self.deadline


@dataclass
class Metrics:
    """三维度核心指标（第四维度显存/功耗在真机部署阶段测量）。"""

    total: int = 0
    succeeded: int = 0
    latency_sum: float = 0.0          # 任务产生 → 处理完成的总延迟
    ground_transfers: int = 0         # 占用星地链路的任务数（链路占用）
    emergency_total: int = 0          # v0.4：应急任务数
    emergency_succeeded: int = 0      # v0.4：应急任务成功数
    energy_onboard_j: float = 0.0     # v0.7：星上推理累计能耗（焦耳）
    energy_link_j: float = 0.0        # v0.7：星地链路累计能耗（焦耳）

    def record(
        self,
        success: bool,
        latency: float,
        used_ground_link: bool,
        priority: int = 0,
        e_onboard: float = 0.0,   # v0.7：本次星上推理能耗（J）
        e_link: float = 0.0,      # v0.7：本次链路传输能耗（J）
    ) -> None:
        self.total += 1
        if success:
            self.succeeded += 1
            self.latency_sum += latency
        if used_ground_link:
            self.ground_transfers += 1
        if priority:
            self.emergency_total += 1
            if success:
                self.emergency_succeeded += 1
        self.energy_onboard_j += e_onboard
        self.energy_link_j += e_link

    @property
    def success_rate(self) -> float:
        return self.succeeded / self.total if self.total else 0.0

    @property
    def avg_latency(self) -> float:
        return self.latency_sum / self.succeeded if self.succeeded else float("inf")

    @property
    def emergency_success_rate(self) -> float:
        """v0.4：应急任务成功率（系统对最不能失败任务的保障能力）。"""
        return self.emergency_succeeded / self.emergency_total if self.emergency_total else float("nan")

    @property
    def energy_total_wh(self) -> float:
        """v0.7：系统总能耗（Wh）= 星上推理 + 链路传输。"""
        from energy import to_wh
        return to_wh(self.energy_onboard_j + self.energy_link_j)

    @property
    def energy_per_success_wh(self) -> float:
        """v0.7：单成功任务能耗（Wh/个）——能效核心指标。"""
        from energy import to_wh
        if not self.succeeded:
            return float("inf")
        return to_wh(self.energy_onboard_j + self.energy_link_j) / self.succeeded

    def report(self, name: str) -> str:
        return (
            f"[{name}] 任务 {self.total} | 成功率 {self.success_rate:.0%} | "
            f"平均延迟 {self.avg_latency:8.1f}s | 链路占用 {self.ground_transfers} | "
            f"能耗 {self.energy_total_wh:.2f}Wh"
        )
