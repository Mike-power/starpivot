# -*- coding: utf-8 -*-
"""L6c v0.9c 三杠杆叠加实验：组网 × 缓存 × 真实推理延迟。

v0.8c 证明"补偿 × 组网"超可加（N=8 处 τ=0.3 成功率 57%→85%）；
v0.9b 证明 token 口径 + 前缀缓存让工作流成功率翻倍（22%→54%）。
本实验回答：三个杠杆一起上，85% 的上限还能不能突破？

矩阵：N ∈ {1,2,4,8} × 两种服务耗时口径（τ=0.3、步级重试开、缓存开
固定，只换 serve_fn）：
  ① duration 黑箱（= v0.8c 语义，回归锚点）
  ③ TTFT/TPOT + L2 前缀缓存（v0.9b 口径）

用法：
    python run_inference_l6c.py            # 终端打印
    python run_inference_l6c.py --save     # 结果写入 benchmark/results/

口径同 run_inference_l6/l6b：token 由 assign_step_tokens（独立 RNG
流 50_000 段）填充；TX 50 / PREFILL 1000 / DECODE 20 tok/s 为工程
假设，待 12 月实测校准。
"""

import statistics as stats
import sys
from pathlib import Path

from agentflow import gen_step_profiles, gen_workflows, run_agentflow
from inference import assign_step_tokens, serve_time
from timeline_constellation import ConstellationTimeline

N_SATS = (1, 2, 4, 8)
TAU = 0.3
N_WF = 50
N_STEPS = 3
N_SEEDS = 5

# (标签, serve_fn) —— 缓存与重试对所有行固定开
MODES = [
    ("① duration黑箱", None),
    ("③ TTFT/TPOT+L2缓存", serve_time),
]


def main() -> None:
    lines = [
        "# L6c v0.9c 组网 × 缓存 × 真实推理延迟三杠杆叠加",
        "",
        "- 工作流：50 个 × 3 步 × 5 种子（均值）；all-or-nothing",
        f"- 固定：τ={TAU}、步级重试开、前缀缓存开；变量：星数 N × 服务耗时口径",
        "- token 口径：input ~ U(200,2000)，output ~ U(50,500)，前缀占比按 60s/25s 耗时拆分",
        "- 常数假设：TX 50 · PREFILL 1000 · DECODE 20 tok/s（待 12 月实测校准）",
        "- 假说：v0.8c 的 85% 上限（N=8、duration 黑箱）可被 token+缓存口径突破",
        "",
        "| 星数 N | 服务耗时口径 | 成功率 | 平均延迟 | 链路占用 | 前缀命中 | 重试步 | 误收死/超时死/未完 |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for n in N_SATS:
        timeline = ConstellationTimeline(n_sats=n, horizon=86400.0)
        for mode_label, serve_fn in MODES:
            succ, lat, link, hit, retry_n = [], [], [], [], []
            f_onb, f_dead, f_unf = [], [], []
            for seed in range(N_SEEDS):
                workflows = gen_workflows(n=N_WF, n_steps=N_STEPS, seed=seed)
                profiles = gen_step_profiles(workflows, seed=seed)
                assign_step_tokens(workflows, seed)   # v0.9 token，独立 RNG 流
                m, diag = run_agentflow(
                    workflows, profiles, timeline.windows,
                    tau=TAU, use_cache=True,
                    retry_onboard=True, serve_fn=serve_fn,
                )
                succ.append(m.success_rate)
                lat.append(m.avg_latency)
                link.append(m.ground_transfers)
                hit.append(diag["prefix_hit"])
                retry_n.append(diag["retried_steps"])
                f_onb.append(diag["fail_onboard_wrong"])
                f_dead.append(diag["fail_deadline"])
                f_unf.append(diag["fail_unfinished"])
            row = (f"| {n} | {mode_label} | {stats.mean(succ):.0%} | "
                   f"{stats.mean(lat):.0f}s | {stats.mean(link):.0f} | "
                   f"{stats.mean(hit):.0f} | {stats.mean(retry_n):.0f} | "
                   f"{stats.mean(f_onb):.0f}/{stats.mean(f_dead):.0f}/{stats.mean(f_unf):.0f} |")
            lines.append(row)
            print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "inference_l6c.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
