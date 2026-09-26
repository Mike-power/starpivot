# -*- coding: utf-8 -*-
"""置信度路由消融扫描（v0.6，创新度杠杆 L1 的实验证据）。

扫描三维：
  能力边界锐利度 k ∈ {10（接近硬阈值近似）, 5（边界模糊，难任务仍有戏）}
  置信度校准   bias ∈ {0 校准, +0.15 过度自信, -0.15 不自信}
  路由阈值     τ ∈ {0.3, 0.5, 0.7}
对照组（每个 k×bias 格）：硬阈值 θ_est=0.3（概率版）、纯地面+EDF可行、纯星上（概率版）。

核心问题（论文 4.x 节素材）：
  Q1 边界模糊时，置信度路由能否捞回硬阈值"不敢做"的任务？
  Q2 模型过度自信时，τ 能不能兜住误收错误答案的风险？
  Q3 校准失配下系统退化是否平滑（可调 τ 补偿）？

用法：
    python run_confidence_sweep.py            # 终端打印
    python run_confidence_sweep.py --save     # 结果写入 benchmark/results/
"""

import statistics as stats
import sys
from pathlib import Path

from confidence import (confidence_routed, gen_profiles, pure_star_prob,
                        static_threshold_prob)
from experiments import N_SEEDS, N_TASKS
from queueing import ground_queued
from scenario import gen_tasks
from timeline_tle import TleTimeline

THETA_TRUE = 0.3   # 小模型真实能力边界（正确概率 50% 处）
THETA_EST = 0.3    # 硬阈值基线的估计边界
TAUS = (0.3, 0.5, 0.7)
SHARPNESSES = (10.0, 5.0)
REGIMES = (("校准", 0.0), ("过度自信", 0.15), ("不自信", -0.15))


def main() -> None:
    timeline = TleTimeline(horizon=86400.0)  # 排队路径不修改窗口，全程共享安全

    # acc[sharp][regime] = {"static": {...}, "ground": {...}, "star": {...},
    #                       ("conf", tau): {"m": [...], "fa": [...], "fr": [...]}}
    acc: dict[float, dict[str, dict]] = {}
    for k in SHARPNESSES:
        acc[k] = {}
        for regime, _bias in REGIMES:
            cell: dict = {
                "static": {"success": [], "latency": [], "link": []},
                "ground": {"success": [], "latency": [], "link": []},
                "star":   {"success": [], "latency": [], "link": []},
            }
            for tau in TAUS:
                cell[("conf", tau)] = {"success": [], "latency": [], "link": [],
                                       "false_accept": [], "false_reject": [], "escalated": []}
            acc[k][regime] = cell

    for seed in range(N_SEEDS):
        tasks = gen_tasks(n=N_TASKS, seed=seed)
        for k in SHARPNESSES:
            for regime, bias in REGIMES:
                profiles = gen_profiles(tasks, theta_true=THETA_TRUE, sharpness=k,
                                        bias=bias, seed=seed)
                cell = acc[k][regime]
                runs = {
                    "static": static_threshold_prob(tasks, timeline, profiles, THETA_EST)[0],
                    "ground": ground_queued(tasks, timeline, edf=True, admit="feasible"),
                    "star":   pure_star_prob(tasks, profiles),
                }
                for name, m in runs.items():
                    cell[name]["success"].append(m.success_rate)
                    cell[name]["latency"].append(m.avg_latency)
                    cell[name]["link"].append(m.ground_transfers)
                for tau in TAUS:
                    m, diag = confidence_routed(tasks, timeline, profiles, tau)
                    c = cell[("conf", tau)]
                    c["success"].append(m.success_rate)
                    c["latency"].append(m.avg_latency)
                    c["link"].append(m.ground_transfers)
                    c["false_accept"].append(diag["false_accept"])
                    c["false_reject"].append(diag["false_reject"])
                    c["escalated"].append(diag["escalated"])

    def mean(d, key):
        return stats.mean(d[key])

    def sl(d):  # success / latency / link 三合一单元格
        return f"{mean(d, 'success'):.0%}/{mean(d, 'latency'):.0f}s/{mean(d, 'link'):.0f}"

    lines = [
        "# v0.6 置信度路由消融扫描（TLE 真实轨道）",
        "",
        "- 卫星：ISS（NORAD 25544，CelesTrak 公开 TLE）",
        f"- {timeline.summary()}",
        f"- 任务：{N_TASKS} 个/场景 × {N_SEEDS} 种子；真实能力 θ_true={THETA_TRUE}，硬阈值基线 θ_est={THETA_EST}",
        "- 概率模型：答对概率 σ(k(θ_true−x))；置信度 = 答对概率 + bias + N(0,0.1)，clip 到 [0,1]",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(任务数)；误收 = 置信度≥τ但答案错；误升级 = 本可星上答对却上送",
        "",
        "## 基线对照表（每个边界×校准格）",
        "",
        "| 边界 k | 校准 | 硬阈值θ=0.3 | 纯地面+EDF可行 | 纯星上(概率版) |",
        "|---|---|---|---|---|",
    ]
    for k in SHARPNESSES:
        for regime, _ in REGIMES:
            cell = acc[k][regime]
            lines.append(f"| {k:g} | {regime} | {sl(cell['static'])} | {sl(cell['ground'])} | {sl(cell['star'])} |")

    lines += [
        "",
        "## 置信度路由（τ 扫描）",
        "",
        "| 边界 k | 校准 | τ | 置信度路由 | 误收 | 误升级 | 升级总数 | Δ成功率 vs 硬阈值 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k in SHARPNESSES:
        for regime, _ in REGIMES:
            cell = acc[k][regime]
            base = mean(cell["static"], "success")
            for tau in TAUS:
                c = cell[("conf", tau)]
                delta = mean(c, "success") - base
                row = (f"| {k:g} | {regime} | {tau:.1f} | {sl(c)} "
                       f"| {mean(c, 'false_accept'):.1f} | {mean(c, 'false_reject'):.1f} | {mean(c, 'escalated'):.1f} "
                       f"| {delta:+.1%} |")
                lines.append(row)
    for row in lines:
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "confidence_sweep.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
