# -*- coding: utf-8 -*-
"""L2 前缀增量传输实验（创新度杠杆 L2 的实验证据）。

Agent 工作流的上行 payload = 共享系统提示前缀 + 任务增量。地面 vLLM
前缀缓存命中后，后续任务只传增量——窗口内能塞下更多任务，链路秒数下降。

本实验对比两场景 × 两策略 × 开关共 8 格：
  场景：TLE 真实轨道 / 合成稀缺链路（1.5h 周期 × 5min 窗口）
  策略：纯地面+EDF可行 / 协同b-EDF可行（θ=0.3）
  开关：cache=None（基线，传输=duration）vs cache={}（前缀增量，见 _tx_time）

口径：prefix=60s（Agent 系统提示量级假设），delta=10~40s（任务增量）；
链路秒数从链路能耗反推（e_link_j / TX_W）；cache dict 兼作统计载体
（miss = len(cache)，hit = sum(v-1)）。

用法：
    python run_prefix_l2.py            # 终端打印
    python run_prefix_l2.py --save     # 结果写入 benchmark/results/
"""

import statistics as stats
import sys
from pathlib import Path

from energy import TX_W
from experiments import N_SEEDS, N_TASKS
from queueing import ground_queued, star_ground_coop_queued
from scenario import gen_tasks
from timeline import SyntheticTimeline
from timeline_tle import TleTimeline

ONBOARD_CAP = 0.3
PREFIX_CFG = {"prefix": 60.0, "delta": (10.0, 40.0)}


def run_cell(timeline, tasks, coop: bool, use_cache: bool):
    """返回 (Metrics, hits, misses, link_seconds)。"""
    cache = {} if use_cache else None
    if coop:
        m = star_ground_coop_queued(tasks, timeline, onboard_capability=ONBOARD_CAP,
                                    edf=True, admit="feasible", cache=cache)
    else:
        m = ground_queued(tasks, timeline, edf=True, admit="feasible", cache=cache)
    hits = sum(v - 1 for v in cache.values()) if cache else 0
    misses = len(cache) if cache else 0
    link_s = m.energy_link_j / TX_W
    return m, hits, misses, link_s


def main() -> None:
    tle = TleTimeline(horizon=86400.0)
    syn = SyntheticTimeline(period=5400.0, duration=300.0, capacity=999)  # 容量在排队模型下不使用
    scenarios = [("TLE 真实轨道", tle), ("合成稀缺 1.5h×5min", syn)]

    lines = [
        "# L2 前缀增量传输实验",
        "",
        f"- 任务：{N_TASKS} 个/场景 × {N_SEEDS} 种子；前缀 60s（共享系统提示）+ 增量 10-40s",
        "- 开关对比：基线（传输=duration）vs 前缀感知（首任务付全量前缀，后续命中缓存只付增量）",
        "- 指标：成功率 | 平均延迟(s) | 链路任务数 | 链路秒数 | 缓存命中/未命中",
        "",
        "| 场景 | 策略 | 开关 | 成功率 | 平均延迟 | 链路任务 | 链路秒 | 命中/未命中 |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for sname, timeline in scenarios:
        for coop in (False, True):
            for use_cache in (False, True):
                acc = {"success": [], "latency": [], "link": [], "sec": [], "hits": [], "miss": []}
                for seed in range(N_SEEDS):
                    tasks = gen_tasks(n=N_TASKS, seed=seed, prefix_cfg=PREFIX_CFG)
                    m, hits, misses, link_s = run_cell(timeline, tasks, coop, use_cache)
                    acc["success"].append(m.success_rate)
                    acc["latency"].append(m.avg_latency)
                    acc["link"].append(m.ground_transfers)
                    acc["sec"].append(link_s)
                    acc["hits"].append(hits)
                    acc["miss"].append(misses)
                strat = "协同b-EDF可行" if coop else "纯地面+EDF可行"
                switch = "前缀感知" if use_cache else "基线"
                lat = stats.mean(acc["latency"])
                lat_s = f"{lat:.0f}" if lat != float("inf") else "inf"
                row = (f"| {sname} | {strat} | {switch} | {stats.mean(acc['success']):.0%} "
                       f"| {lat_s} | {stats.mean(acc['link']):.1f} | {stats.mean(acc['sec']):.0f} "
                       f"| {stats.mean(acc['hits']):.0f}/{stats.mean(acc['miss']):.0f} |")
                lines.append(row)
                print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "prefix_l2.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
