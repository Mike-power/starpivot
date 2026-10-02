# -*- coding: utf-8 -*-
"""L6d v0.9d 应急重规划 × Agent 工作流：必死步星上博一把。

v0.9c 的点名：N≥4 后剩余失败全部是超时死，死因是"等窗相位"。
v0.4 的 preempt_feasible 语义（必死任务不占带宽、把槽位让出来）
在工作流引擎里早已内置（EDF 重排 + 可行性准入每窗口都生效），
所以本实验的"在线重规划"变量是 v0.9d 新机制 replan_onboard：

  每窗口服务前扫描地面队列，对"本窗口乐观服务也必超截止期"
  （等窗已必死）的就绪步，若星上立即执行还来得及 → 降级星上
  博一把。该步本因 c < τ 被路由地面；博对省链路且就绪链提前
  解锁，博错由步级补偿（retry_onboard）兜底回地面队列——
  只赌必死步，期望收益恒非负。

场景为动态环境：窗口丢失 10% / 抖动 ±300s × 5%（v0.4 gen_scenario
同参数，独立 RNG 流 60_000 段），静态/在线之差由 replan 开关承载。

矩阵：N ∈ {1,8} × replan{关,开} × 服务口径{①duration, ③TTFT/TPOT+缓存}
（τ=0.3、步级重试开、缓存开固定）。

用法：
    python run_inference_l6d.py            # 终端打印
    python run_inference_l6d.py --save     # 结果写入 benchmark/results/
"""

import random
import statistics as stats
import sys
from pathlib import Path

from agentflow import gen_step_profiles, gen_workflows, run_agentflow
from inference import assign_step_tokens, serve_time
from timeline_constellation import ConstellationTimeline

N_SATS = (1, 8)
TAU = 0.3
LOSS_RATE = 0.1
SHIFT_PROB = 0.05
N_WF = 50
N_STEPS = 3
N_SEEDS = 5

REPLANS = [("关", False), ("开", True)]
MODES = [("① duration黑箱", None), ("③ TTFT/TPOT+L2缓存", serve_time)]


class Disruption:
    """与 emergency.Disruption 同形的轻量事件（duck typing）。"""

    def __init__(self, time, kind, window_idx=-1, delta=0.0):
        self.time = time
        self.kind = kind
        self.window_idx = window_idx
        self.delta = delta


def gen_window_disruptions(windows, seed):
    """窗口扰动序列（独立 RNG 流 60_000 段，与任务/步骤/token 流隔离）。"""
    rng = random.Random(60_000 + seed)
    dis = []
    n_loss = max(1, int(len(windows) * LOSS_RATE))
    for idx in rng.sample(range(len(windows)), min(n_loss, len(windows))):
        dis.append(Disruption(time=windows[idx].start - 60.0,
                              kind="window_loss", window_idx=idx))
    for idx, w in enumerate(windows):
        if rng.random() < SHIFT_PROB:
            dis.append(Disruption(time=w.start - 120.0,
                                  kind="window_shift", window_idx=idx,
                                  delta=rng.choice((-300.0, 300.0))))
    dis.sort(key=lambda d: d.time)
    return dis


def main() -> None:
    lines = [
        "# L6d v0.9d 应急重规划 × Agent 工作流（必死步星上博一把）",
        "",
        "- 工作流：50 个 × 3 步 × 5 种子（均值）；all-or-nothing",
        f"- 固定：τ={TAU}、步级重试开、前缀缓存开；动态环境（丢窗 {LOSS_RATE:.0%}、"
        f"抖动 ±300s × {SHIFT_PROB:.0%}）",
        "- replan_onboard：每窗口前扫队列，本窗口乐观服务也必超截止期且星上"
        "来得及 → 星上博一把（博对省链路解锁就绪链，博错补偿兜底回队列）",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(步) | 重规划步(赌赢) | 重试步 | 误收死/超时死/未完",
        "",
        "| 星数 N | replan | 服务耗时口径 | 成功率 | 平均延迟 | 链路占用 | 重规划步(赌赢) | 重试步 | 误收死/超时死/未完 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for n in N_SATS:
        timeline = ConstellationTimeline(n_sats=n, horizon=86400.0)
        for replan_label, replan in REPLANS:
            for mode_label, serve_fn in MODES:
                succ, lat, link, replanned, replanned_ok, retry_n = [], [], [], [], [], []
                f_onb, f_dead, f_unf = [], [], []
                for seed in range(N_SEEDS):
                    workflows = gen_workflows(n=N_WF, n_steps=N_STEPS, seed=seed)
                    profiles = gen_step_profiles(workflows, seed=seed)
                    assign_step_tokens(workflows, seed)
                    dis = gen_window_disruptions(timeline.windows, seed)
                    m, diag = run_agentflow(
                        workflows, profiles, timeline.windows,
                        tau=TAU, use_cache=True, retry_onboard=True,
                        serve_fn=serve_fn, disruptions=dis,
                        replan_onboard=replan,
                    )
                    succ.append(m.success_rate)
                    lat.append(m.avg_latency)
                    link.append(m.ground_transfers)
                    replanned.append(diag["replanned_steps"])
                    replanned_ok.append(diag["replanned_correct"])
                    retry_n.append(diag["retried_steps"])
                    f_onb.append(diag["fail_onboard_wrong"])
                    f_dead.append(diag["fail_deadline"])
                    f_unf.append(diag["fail_unfinished"])
                row = (f"| {n} | {replan_label} | {mode_label} | "
                       f"{stats.mean(succ):.0%} | {stats.mean(lat):.0f}s | "
                       f"{stats.mean(link):.0f} | "
                       f"{stats.mean(replanned):.0f}({stats.mean(replanned_ok):.0f}) | "
                       f"{stats.mean(retry_n):.0f} | "
                       f"{stats.mean(f_onb):.0f}/{stats.mean(f_dead):.0f}/{stats.mean(f_unf):.0f} |")
                lines.append(row)
                print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "inference_l6d.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
