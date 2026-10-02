# -*- coding: utf-8 -*-
"""L7 v0.10 准入控制实验：创建时关键路径过滤 × 截止期协商。

v0.9d 的结论：调度侧杠杆穷尽，剩余超时死是"关键路径 × 截止期"的
结构性矛盾；下一个更便宜的杠杆在 admission 侧或 deadline 侧。
本实验把两个候选杠杆一起测：

矩阵：N ∈ {1,8} × 准入策略 {off, reject, relax(γ=1.5)} × 服务口径
{①duration黑箱, ③TTFT/TPOT+L2缓存}（τ=0.3、步级重试开、缓存开固定，
50 工作流 × 3 步 × 5 种子均值）。

指标（诚实口径）：
- 严格成功率 = 成功数 / 生成总数（被拒绝者计入失败，不准 inflate）；
- 接纳内成功率 = 成功数 / 准入数（机制有效性的上限视角）；
- 拒绝数、链路占用、单成功能耗（Wh）——机制的主战场。

预期：reject 在 N=1（稀缺 regime）通过缓解争用小有成功收益、能耗
收益显著；N=8（带宽非瓶颈）主要是能耗杠杆。relax 对照需求侧。

用法：
    python run_admission_l7.py            # 终端打印
    python run_admission_l7.py --save     # 结果写入 benchmark/results/
"""

import statistics as stats
import sys
from pathlib import Path

from admission import admit_workflows
from agentflow import gen_step_profiles, gen_workflows, run_agentflow
from inference import assign_step_tokens, serve_time
from timeline_constellation import ConstellationTimeline, FROZEN_EPOCH

TAU = 0.3
N_WF = 50
N_STEPS = 3
N_SEEDS = 5
GAMMA = 1.5

N_SATS = (1, 8)
POLICIES = [
    ("off",    "基线（全量准入）"),
    ("reject", "关键路径过滤"),
    ("relax",  f"截止期协商(×{GAMMA})"),
    ("hybrid", f"协商+过滤(×{GAMMA})"),
]
MODES = [
    ("① duration黑箱", None),
    ("③ TTFT/TPOT+L2缓存", serve_time),
]


def main() -> None:
    lines = [
        "# L7 v0.10 准入控制：创建时关键路径过滤 × 截止期协商",
        "",
        f"- 工作流：{N_WF} 个 × {N_STEPS} 步 × {N_SEEDS} 种子（均值）；all-or-nothing",
        f"- 固定：τ={TAU}、步级重试开、前缀缓存开；变量：N × 准入策略 × 服务口径",
        f"- 严格成功率 = 成功/生成总数（拒绝计入失败）；能耗 = (星上+链路)/3600/成功数",
        "- 估计口径：乐观关键路径（无争用），见 admission.py docstring",
        "",
        "| 星数 | 准入策略 | 服务口径 | 严格成功率 | 接纳内成功率 | 拒绝数 | 链路占用 | 单成功能耗 | 误收死/超时死/未完 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for n in N_SATS:
        timeline = ConstellationTimeline(n_sats=n, horizon=86400.0, epoch=FROZEN_EPOCH)
        win_starts = sorted(w.start for w in timeline.windows)
        for pol, pol_label in POLICIES:
            for mode_label, serve_fn in MODES:
                strict, inner, rej, link, wh = [], [], [], [], []
                f_onb, f_dead, f_unf = [], [], []
                for seed in range(N_SEEDS):
                    workflows = gen_workflows(n=N_WF, n_steps=N_STEPS, seed=seed)
                    profiles = gen_step_profiles(workflows, seed=seed)
                    assign_step_tokens(workflows, seed)
                    accepted, rejected = admit_workflows(
                        workflows, win_starts, TAU,
                        policy=pol, gamma=GAMMA, serve_fn=serve_fn,
                    )
                    m, diag = run_agentflow(
                        accepted, profiles, timeline.windows,
                        tau=TAU, use_cache=True,
                        retry_onboard=True, serve_fn=serve_fn,
                    )
                    total = m.total + rejected          # 生成总数
                    strict.append(m.succeeded / total if total else 0.0)
                    inner.append(m.success_rate)
                    rej.append(rejected)
                    link.append(m.ground_transfers)
                    f_onb.append(diag["fail_onboard_wrong"])
                    f_dead.append(diag["fail_deadline"])
                    f_unf.append(diag["fail_unfinished"])
                    if m.succeeded:
                        wh.append((m.energy_onboard_j + m.energy_link_j)
                                  / 3600.0 / m.succeeded)
                    else:
                        wh.append(float("nan"))
                row = (f"| {n} | {pol_label} | {mode_label} | "
                       f"{stats.mean(strict):.0%} | {stats.mean(inner):.0%} | "
                       f"{stats.mean(rej):.1f} | {stats.mean(link):.0f} | "
                       f"{stats.mean(wh):.2f} | "
                       f"{stats.mean(f_onb):.0f}/{stats.mean(f_dead):.0f}/{stats.mean(f_unf):.0f} |")
                lines.append(row)
                print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "admission_l7.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
