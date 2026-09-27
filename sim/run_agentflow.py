# -*- coding: utf-8 -*-
"""v0.8 Agent 多步工作流实验：TLE 真实轨道 + 事件驱动调度。

问题：多步工作流（步骤串行依赖 + all-or-nothing 交付）在稀缺链路下的
成功率/延迟/前缀复用规律。

对比维度：
  - τ ∈ {0.3, 0.5, 0.7}（置信度路由阈值）
  - 前缀缓存开/关（跨 workflow 共享同一系统前缀：一次前缀，全天复用）
  - 硬阈值 θ=0.3 对照（逐步硬判定，无置信度语义）

用法：
    python run_agentflow.py            # 终端打印
    python run_agentflow.py --save     # 结果写入 benchmark/results/
"""

import statistics as stats
import sys
from pathlib import Path

from agentflow import gen_step_profiles, gen_workflows, run_agentflow
from confidence import correctness_prob
from timeline_tle import TleTimeline

TAU = (0.3, 0.5, 0.7)
N_WF = 50
N_STEPS = 3
N_SEEDS = 5


def main() -> None:
    timeline = TleTimeline(horizon=86400.0)

    # 每行: (标签, tau 或 None, use_cache)
    variants = [
        ("置信度路由 τ=0.3（缓存开）", 0.3, True),
        ("置信度路由 τ=0.5（缓存开）", 0.5, True),
        ("置信度路由 τ=0.7（缓存开）", 0.7, True),
        ("置信度路由 τ=0.5（缓存关）", 0.5, False),
        ("硬阈值 θ=0.3（缓存开）", None, True),
    ]

    acc = {label: {"succ": [], "lat": [], "link": [], "hit": [], "miss": [],
                   "f_onboard": [], "f_deadline": [], "f_unfinished": []}
           for label, _, _ in variants}

    for seed in range(N_SEEDS):
        workflows = gen_workflows(n=N_WF, n_steps=N_STEPS, seed=seed)
        profiles = gen_step_profiles(workflows, seed=seed)
        for label, tau, use_cache in variants:
            if tau is None:
                # 硬阈值对照：把置信度换成"复杂度是否 ≤ θ"的 0/1 判定
                hard = {}
                for sid, prof in profiles.items():
                    x = next(s.complexity for wf in workflows
                             for s in wf.steps if s.step_id == sid)
                    c = 1.0 if x <= 0.3 else 0.0
                    hard[sid] = type(prof)(correct=prof.correct, confidence=c)
                m, diag = run_agentflow(workflows, hard, timeline.windows,
                                        tau=0.5, use_cache=use_cache)
            else:
                m, diag = run_agentflow(workflows, profiles, timeline.windows,
                                        tau=tau, use_cache=use_cache)
            acc[label]["succ"].append(m.success_rate)
            acc[label]["lat"].append(m.avg_latency)
            acc[label]["link"].append(m.ground_transfers)
            acc[label]["hit"].append(diag["prefix_hit"])
            acc[label]["miss"].append(diag["prefix_miss"])
            acc[label]["f_onboard"].append(diag["fail_onboard_wrong"])
            acc[label]["f_deadline"].append(diag["fail_deadline"])
            acc[label]["f_unfinished"].append(diag["fail_unfinished"])

    lines = [
        "# v0.8 Agent 多步工作流（TLE 真实轨道，事件驱动调度）",
        "",
        f"- {timeline.summary()}",
        f"- 工作流：{N_WF} 个/种子 × {N_STEPS} 步 × {N_SEEDS} 种子（取均值）；"
        "任一步答错或超时 → 整个工作流失败（all-or-nothing）",
        "- 前缀语义：全部工作流共享同一智能体应用前缀（60s），"
        "缓存命中后每步只付增量（25s）",
        "- 指标：工作流成功率 | 平均延迟(s) | 链路占用(步数) | 前缀命中/未命中 | "
        "失败归因(误收/超时/未完成)",
        "",
        "| 策略 | 成功率 | 平均延迟 | 链路占用 | 前缀命中 | 失败归因(误收/超时/未完成) |",
        "|---|---|---|---|---|---|",
    ]
    for label, _, _ in variants:
        r = {k: stats.mean(v) for k, v in acc[label].items()}
        row = (f"| {label} | {r['succ']:.0%} | {r['lat']:.0f}s | {r['link']:.0f} | "
               f"{r['hit']:.0f}/{r['miss']:.0f} | "
               f"{r['f_onboard']:.0f}/{r['f_deadline']:.0f}/{r['f_unfinished']:.0f} |")
        lines.append(row)
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "agentflow_v0.8.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
