# -*- coding: utf-8 -*-
"""v0.8c 补偿 × 组网联合实验：多步工作流 × 星座规模 scaling。

动机（v0.8b 发现）：步级补偿在单星 TLE 极稀缺 regime 下"药对药房空"——
误收死亡被成功转移为超时死亡，但链路预算封死了救援空间。
假说：组网（L4）扩窗口与补偿（v0.8b）是正交组合——窗口 ×8.4 后，
重试步能获得第二次窗口机会，成功率应首次随 N 显著爬升。

矩阵：N ∈ {1,2,4,8} × τ ∈ {0.3,0.5} × 重试{关,开}，50 工作流 × 3 步 × 5 种子。

用法：
    python run_agentflow_constellation.py            # 终端打印
    python run_agentflow_constellation.py --save     # 结果写入 benchmark/results/
"""

import statistics as stats
import sys
from pathlib import Path

from agentflow import gen_step_profiles, gen_workflows, run_agentflow
from timeline_constellation import ConstellationTimeline

N_SATS = (1, 2, 4, 8)
TAUS = (0.3, 0.5)
N_WF = 50
N_STEPS = 3
N_SEEDS = 5


def main() -> None:
    # 每行: (tau, retry_onboard)
    variants = [(0.3, False), (0.3, True), (0.5, False), (0.5, True)]

    lines = [
        "# v0.8c 补偿 × 组网联合实验（多步工作流 × 星座 scaling）",
        "",
        "- 工作流：50 个 × 3 步 × 5 种子（均值）；all-or-nothing；前缀缓存开",
        "- 补偿语义：星上误收 → 降级送地面兜底（占链路换存活）",
        "- 假说：组网窗口扩容给重试步第二次机会，补偿 × 组网撬动成功率",
        "",
        "| 星数 N | τ | 重试 | 成功率 | 平均延迟 | 链路占用 | 重试步 | 误收死/超时死/未完 |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for n in N_SATS:
        timeline = ConstellationTimeline(n_sats=n, horizon=86400.0)
        for tau, retry in variants:
            succ, lat, link, retry_n = [], [], [], []
            f_onb, f_dead, f_unf = [], [], []
            for seed in range(N_SEEDS):
                workflows = gen_workflows(n=N_WF, n_steps=N_STEPS, seed=seed)
                profiles = gen_step_profiles(workflows, seed=seed)
                m, diag = run_agentflow(
                    workflows, profiles, timeline.windows,
                    tau=tau, retry_onboard=retry,
                )
                succ.append(m.success_rate)
                lat.append(m.avg_latency)
                link.append(m.ground_transfers)
                retry_n.append(diag["retried_steps"])
                f_onb.append(diag["fail_onboard_wrong"])
                f_dead.append(diag["fail_deadline"])
                f_unf.append(diag["fail_unfinished"])
            row = (f"| {n} | {tau} | {'开' if retry else '关'} | "
                   f"{stats.mean(succ):.0%} | {stats.mean(lat):.0f}s | "
                   f"{stats.mean(link):.0f} | {stats.mean(retry_n):.0f} | "
                   f"{stats.mean(f_onb):.0f}/{stats.mean(f_dead):.0f}/{stats.mean(f_unf):.0f} |")
            lines.append(row)
            print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "agentflow_constellation.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
