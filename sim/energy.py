# -*- coding: utf-8 -*-
"""能耗模型（v0.7，创新度杠杆 L3）。

《航天器工程》读者关心的不只是成功率，还有功耗预算。本模块给仿真
加上第二 scarce resource：能量。口径与假设（论文需如实声明）：

  - 星上推理功耗 15 W：Jetson AGX Orin 模组级典型推理功耗量级（假设值）
  - 星地发射功耗 10 W：星载发射机工作功耗量级（假设值）
  - 地面站能耗不计：非稀缺资源
  - 任务 duration 同时用于计算与传输能耗计量：已知简化。真实场景
    数传仅秒级、推理十秒~分钟级，本口径高估链路相对成本——
    结论方向上偏"保守夸大连路能耗"，论文讨论节需声明
  - 单位：内部焦耳，报告统一换算 Wh（1 Wh = 3600 J）
"""

J_PER_WH = 3600.0

ONBOARD_W = 15.0   # 星上小模型推理功率（假设）
TX_W = 10.0        # 星地链路上行发射功率（假设）


def onboard_energy_j(duration_s: float) -> float:
    """星上处理一个任务的能耗（焦耳）。"""
    return ONBOARD_W * duration_s


def link_energy_j(duration_s: float) -> float:
    """任务占用星地链路一次传输的能耗（焦耳）。"""
    return TX_W * duration_s


def to_wh(joules: float) -> float:
    return joules / J_PER_WH
