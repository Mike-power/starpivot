# -*- coding: utf-8 -*-
"""L6 v0.9 TTFT/TPOT 真实推理延迟耦合实验。

问题：v0.3-v0.8 把"传输耗时 = 任务时长"当黑箱，地面推理瞬间完成。
真实 LLM serving 中地面处理 = 链路传输 + TTFT（prefill）+ TPOT
（decode），而 L2 前缀缓存命中不只省链路秒数，还省 prefill 计算
——本实验量化这个被漏算的另一半红利。

三行对比（同一批任务、同一 TLE 时间线、同一种子，只换服务耗时口径）：
  ① duration 黑箱基线（v0.3-v0.8 语义，回归锚点）
  ② TTFT/TPOT 启用、无前缀缓存（cache=None）
  ③ TTFT/TPOT 启用 + L2 前缀缓存（cache={}）

用法：
    python run_inference_l6.py            # 终端打印
    python run_inference_l6.py --save     # 结果写入 benchmark/results/

token 口径：input_tokens ~ U(200,2000)、output_tokens ~ U(50,500)，
由 inference.assign_tokens 用独立随机流填充（不碰 gen_tasks 的 RNG 流，
保护 v0.3-v0.8 全部基线可复现）；前缀 token 占比按 tx_prefix/tx_delta
链路耗时占比拆分（假设值，README 声明）。吞吐常数 TX/PREFILL/DECODE
为工程假设，待 12 月实测校准。
"""

import statistics as stats
import sys
from pathlib import Path

from inference import assign_tokens, serve_time
from queueing import star_ground_coop_queued
from scenario import gen_tasks
from timeline_tle import TleTimeline

ONBOARD_CAP = 0.3
N_TASKS = 100
N_SEEDS = 5
PREFIX_CFG = {"prefix": 60.0, "delta": (10.0, 40.0)}  # 与 run_prefix_l2 同口径

VARIANTS = {
    "① duration 黑箱基线": dict(serve_fn=None, cache=None),
    "② TTFT/TPOT 无缓存": dict(serve_fn=serve_time, cache=None),
    "③ TTFT/TPOT + L2前缀缓存": dict(serve_fn=serve_time, cache="fresh"),
}


def main() -> None:
    timeline = TleTimeline(horizon=86400.0)

    acc: dict[str, dict[str, list]] = {
        s: {"success": [], "latency": [], "link": []} for s in VARIANTS
    }
    for seed in range(N_SEEDS):
        tasks = gen_tasks(n=N_TASKS, seed=seed, prefix_cfg=PREFIX_CFG)
        assign_tokens(tasks, seed)  # input/output_tokens，独立 RNG 流
        for name, cfg in VARIANTS.items():
            cache = {} if cfg["cache"] == "fresh" else None
            m = star_ground_coop_queued(
                tasks, timeline, ONBOARD_CAP,
                edf=True, admit="feasible",
                serve_fn=cfg["serve_fn"], cache=cache,
            )
            acc[name]["success"].append(m.success_rate)
            acc[name]["latency"].append(m.avg_latency)
            acc[name]["link"].append(m.ground_transfers)

    lines = [
        "# L6 v0.9 TTFT/TPOT 真实推理延迟耦合",
        "",
        f"- {timeline.summary()}",
        f"- 任务：{N_TASKS} 个 × {N_SEEDS} 种子（取均值）/ 星上能力阈值 {ONBOARD_CAP}",
        "- 策略统一：星地协同 b（EDF + 可行性准入）",
        "- token 口径：input ~ U(200,2000)，output ~ U(50,500)，前缀占比按链路耗时拆分",
        "- 常数假设：TX 50 tok/s · PREFILL 1000 tok/s · DECODE 20 tok/s（待 12 月实测校准）",
        "- compute（TTFT+TPOT）在窗口后地面计算，不占窗口带宽，计入完成时刻",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(任务数)",
        "",
        "| 服务耗时口径 | 成功率 | 平均延迟 | 链路占用 |",
        "|---|---|---|---|",
    ]
    for name in VARIANTS:
        r = {k: stats.mean(v) for k, v in acc[name].items()}
        row = f"| {name} | {r['success']:.0%} | {r['latency']:.0f}s | {r['link']:.0f} |"
        lines.append(row)
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "inference_l6.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
