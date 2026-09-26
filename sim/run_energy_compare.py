# -*- coding: utf-8 -*-
"""能耗效率对比（v0.7，创新度杠杆 L3 的实验证据）。

在 TLE 真实轨道、链路极稀缺 regime 下对比五类方案的能耗画像：
  - 纯地面+EDF可行：链路能耗大头，成功率极低 → 单成功能耗爆炸
  - 纯星上(θ=0.3)：零链路能耗但成功率低
  - 硬阈值 / 置信度路由：分层混合

核心指标：单成功任务能耗（Wh/个）= 总能耗 / 成功数——
工程含义"每交付一个正确结果，卫星要付出多少电池/太阳翼预算"。

能耗口径见 energy.py（星上 15W / 发射 10W 假设，duration 双用途简化）。

用法：
    python run_energy_compare.py            # 终端打印
    python run_energy_compare.py --save     # 结果写入 benchmark/results/
"""

import statistics as stats
import sys
from pathlib import Path

from confidence import (confidence_routed, gen_profiles, pure_star_prob,
                        static_threshold_prob)
from energy import to_wh
from experiments import N_SEEDS, N_TASKS
from queueing import ground_queued
from scenario import gen_tasks
from timeline_tle import TleTimeline

THETA_TRUE = 0.3
K = 10.0        # 锐利边界（与 confidence_sweep 主设置一致）
BIAS = 0.0      # 校准良好


def main() -> None:
    timeline = TleTimeline(horizon=86400.0)

    variants = ("纯地面+EDF可行", "纯星上(θ=0.3)", "硬阈值θ=0.3",
                "置信度路由τ=0.5", "置信度路由τ=0.3")
    acc: dict[str, dict[str, list]] = {
        v: {"success": [], "false_accept": [], "e_star_wh": [], "e_link_wh": [], "e_total_wh": [], "e_per_ok_wh": []}
        for v in variants
    }

    for seed in range(N_SEEDS):
        tasks = gen_tasks(n=N_TASKS, seed=seed)
        profiles = gen_profiles(tasks, theta_true=THETA_TRUE, sharpness=K, bias=BIAS, seed=seed)

        r_static, d_static = static_threshold_prob(tasks, timeline, profiles, THETA_TRUE)
        r_c05, d_c05 = confidence_routed(tasks, timeline, profiles, 0.5)
        r_c03, d_c03 = confidence_routed(tasks, timeline, profiles, 0.3)

        runs = {
            "纯地面+EDF可行": ground_queued(tasks, timeline, edf=True, admit="feasible"),
            "纯星上(θ=0.3)":  pure_star_prob(tasks, profiles),
            "硬阈值θ=0.3":    r_static,
            "置信度路由τ=0.5": r_c05,
            "置信度路由τ=0.3": r_c03,
        }
        fa = {
            "纯地面+EDF可行": 0.0, "纯星上(θ=0.3)": 0.0,
            "硬阈值θ=0.3": d_static["false_accept"],
            "置信度路由τ=0.5": d_c05["false_accept"],
            "置信度路由τ=0.3": d_c03["false_accept"],
        }
        for name, m in runs.items():
            e_star = to_wh(m.energy_onboard_j)
            e_link = to_wh(m.energy_link_j)
            a = acc[name]
            a["success"].append(m.success_rate)
            a["false_accept"].append(fa[name])
            a["e_star_wh"].append(e_star)
            a["e_link_wh"].append(e_link)
            a["e_total_wh"].append(e_star + e_link)
            a["e_per_ok_wh"].append(
                (e_star + e_link) / m.succeeded if m.succeeded else float("inf")
            )

    lines = [
        "# v0.7 能耗效率对比（TLE 真实轨道）",
        "",
        "- 卫星：ISS（NORAD 25544，CelesTrak 公开 TLE）",
        f"- {timeline.summary()}",
        f"- 任务：{N_TASKS} 个/场景 × {N_SEEDS} 种子；能力边界 θ={THETA_TRUE}，k={K:g}，校准良好",
        "- 能耗口径：星上推理 15W、链路发射 10W（假设值，见 energy.py）；duration 双用途简化",
        "- 指标：成功率 | 误收/100任务 | 星上能耗(Wh) | 链路能耗(Wh) | 总能耗(Wh) | **单成功能耗(Wh/个)**",
        "",
        "| 方案 | 成功率 | 误收/100 | 星上Wh | 链路Wh | 总Wh | 单成功Wh |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in variants:
        a = acc[name]
        per_ok = stats.mean(a["e_per_ok_wh"])
        per_ok_s = f"{per_ok:.2f}" if per_ok != float("inf") else "∞"
        row = (f"| {name} | {stats.mean(a['success']):.0%} | {stats.mean(a['false_accept']):.1f} "
               f"| {stats.mean(a['e_star_wh']):.1f} | {stats.mean(a['e_link_wh']):.1f} "
               f"| {stats.mean(a['e_total_wh']):.1f} | {per_ok_s} |")
        lines.append(row)
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "energy_compare.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
