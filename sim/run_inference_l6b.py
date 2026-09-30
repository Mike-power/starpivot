# -*- coding: utf-8 -*-
"""L6b v0.9 TTFT/TPOT 接入 Agent 多步工作流（agentflow 耦合实验）。

把 L6 的推理延迟口径下沉到 v0.8 事件驱动工作流引擎：地面步完成时刻 =
窗口时刻 + tx + compute（compute 不占带宽、阻塞就绪链的时长变长），
前缀缓存命中同时省链路秒数与 prefill 计算——在工作流级，省下的
compute 直接缩短步骤就绪链的阻塞，可能改变 all-or-nothing 的生死线。

六行对比（τ ∈ {0.3, 0.5} × 步级重试开 × 三种服务耗时口径）：
  ① duration 黑箱 + L2 缓存（= v0.8 语义，回归锚点）
  ② TTFT/TPOT 启用、缓存关
  ③ TTFT/TPOT 启用 + L2 缓存

用法：
    python run_inference_l6b.py            # 终端打印
    python run_inference_l6b.py --save     # 结果写入 benchmark/results/

口径与 run_inference_l6 完全一致：token 由 inference.assign_step_tokens
以独立 RNG 流（50_000 段）填充，常数 TX 50 / PREFILL 1000 / DECODE 20
tok/s 为工程假设，待 12 月实测校准。
"""

import statistics as stats
import sys
from pathlib import Path

from agentflow import gen_step_profiles, gen_workflows, run_agentflow
from inference import assign_step_tokens, serve_time
from timeline_tle import TleTimeline

TAUS = (0.3, 0.5)
N_WF = 50
N_STEPS = 3
N_SEEDS = 5

# (标签, serve_fn, use_cache) —— ① 与 v0.8 语义逐字节一致
MODES = [
    ("① duration黑箱+L2缓存", None, True),
    ("② TTFT/TPOT 缓存关", serve_time, False),
    ("③ TTFT/TPOT +L2缓存", serve_time, True),
]


def main() -> None:
    timeline = TleTimeline(horizon=86400.0)

    labels = [f"τ={tau} {mode[0]}" for tau in TAUS for mode in MODES]
    acc = {lb: {"succ": [], "lat": [], "link": [], "hit": [], "miss": [],
                "retry": [], "f_unf": []} for lb in labels}

    for seed in range(N_SEEDS):
        workflows = gen_workflows(n=N_WF, n_steps=N_STEPS, seed=seed)
        profiles = gen_step_profiles(workflows, seed=seed)
        assign_step_tokens(workflows, seed)   # v0.9 token，独立 RNG 流
        for tau in TAUS:
            for mode_label, serve_fn, use_cache in MODES:
                lb = f"τ={tau} {mode_label}"
                m, diag = run_agentflow(
                    workflows, profiles, timeline.windows,
                    tau=tau, use_cache=use_cache,
                    retry_onboard=True, serve_fn=serve_fn,
                )
                acc[lb]["succ"].append(m.success_rate)
                acc[lb]["lat"].append(m.avg_latency)
                acc[lb]["link"].append(m.ground_transfers)
                acc[lb]["hit"].append(diag["prefix_hit"])
                acc[lb]["miss"].append(diag["prefix_miss"])
                acc[lb]["retry"].append(diag["retried_steps"])
                acc[lb]["f_unf"].append(diag["fail_unfinished"])

    lines = [
        "# L6b v0.9 TTFT/TPOT 接入 Agent 多步工作流",
        "",
        f"- {timeline.summary()}",
        f"- 工作流：{N_WF} 个 × {N_STEPS} 步 × {N_SEEDS} 种子（取均值）；"
        "步级重试（补偿）开，all-or-nothing",
        "- token 口径：input ~ U(200,2000)，output ~ U(50,500)，前缀占比按 60s/25s 耗时拆分",
        "- 常数假设：TX 50 · PREFILL 1000 · DECODE 20 tok/s（待 12 月实测校准）",
        "- compute（TTFT+TPOT）窗口后地面计算，不占带宽但阻塞步骤就绪链",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(步) | 前缀命中/未命中 | 重试 | 未完成 |",
        "",
        "| 策略 | 成功率 | 平均延迟 | 链路占用 | 前缀命中 | 重试 | 未完成 |",
        "|---|---|---|---|---|---|---|",
    ]
    for lb in labels:
        r = {k: stats.mean(v) for k, v in acc[lb].items()}
        row = (f"| {lb} | {r['succ']:.0%} | {r['lat']:.0f}s | {r['link']:.0f} | "
               f"{r['hit']:.0f}/{r['miss']:.0f} | {r['retry']:.0f} | {r['f_unf']:.0f} |")
        lines.append(row)
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "inference_l6b.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
