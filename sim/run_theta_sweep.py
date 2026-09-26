# -*- coding: utf-8 -*-
"""星上能力阈值 θ 敏感性扫描（论文 4.3 节"阈值选取建议"数据源）。

动机：主实验固定 θ=0.3（任务复杂度均匀分布下约 30% 任务星上可解）。
论文需要回答"θ 取多少、敏感性如何、系统上限由什么决定"：
  - 纯星上(θ) 曲线 = 系统成功率的天花板（星上能力是唯一杠杆时的极限）
  - 协同曲线随 θ 的增长斜率 = 链路调度在能力受限时的边际贡献
  - 纯地面+EDF 不依赖 θ，作为恒定参照系

用法：
    python run_theta_sweep.py            # 终端打印
    python run_theta_sweep.py --save     # 结果写入 benchmark/results/

说明：θ 是"任务复杂度 ≤ θ 则星上小模型可解"的硬阈值（model.Task.complexity
语义）。真实系统中它对应压缩小模型的能力边界——2026.12 AWQ/2027.1 LoRA
实测后将用真实模型替换该抽象，本扫描即为届时"换真模型"的参数对接点。
"""

import statistics as stats
import sys
from pathlib import Path

from baselines import star_only
from experiments import N_SEEDS, N_TASKS
from queueing import ground_queued, star_ground_coop_queued
from scenario import gen_tasks
from timeline_tle import TleTimeline

THETAS = (0.1, 0.3, 0.5, 0.7, 0.9)


def main() -> None:
    timeline = TleTimeline(horizon=86400.0)  # 排队路径不修改窗口，全 θ 共享安全

    # {θ: {变体: {success/latency/link 列表}}}
    acc: dict[float, dict[str, dict[str, list]]] = {
        th: {v: {"success": [], "latency": [], "link": []}
             for v in ("纯地面+EDF", "纯星上(θ)", "协同a-EDF", "协同b-EDF可行")}
        for th in THETAS
    }

    for seed in range(N_SEEDS):
        tasks = gen_tasks(n=N_TASKS, seed=seed)
        for th in THETAS:
            runs = {
                "纯地面+EDF":     ground_queued(tasks, timeline, edf=True),
                "纯星上(θ)":      star_only(tasks, onboard_capability=th),
                "协同a-EDF":      star_ground_coop_queued(tasks, timeline, onboard_capability=th, edf=True),
                "协同b-EDF可行":  star_ground_coop_queued(tasks, timeline, onboard_capability=th, edf=True, admit="feasible"),
            }
            for name, m in runs.items():
                acc[th][name]["success"].append(m.success_rate)
                acc[th][name]["latency"].append(m.avg_latency)
                acc[th][name]["link"].append(m.ground_transfers)

    def cell(th: float, name: str) -> str:
        r = {k: stats.mean(v) for k, v in acc[th][name].items()}
        return f"{r['success']:.0%}/{r['latency']:.0f}s/{r['link']:.0f}"

    lines = [
        "# 星上能力阈值 θ 敏感性扫描（TLE 真实轨道）",
        "",
        "- 卫星：ISS（NORAD 25544，CelesTrak 公开 TLE）",
        f"- {timeline.summary()}",
        f"- 任务：{N_TASKS} 个/场景 × {N_SEEDS} 种子（取均值）；复杂度均匀分布，θ=星上可解比例",
        "- 语义：窗口内串行服务，窗口时长即带宽预算；纯地面不依赖 θ（恒定参照）",
        "- 指标：成功率 | 平均延迟(s) | 链路占用(任务数)",
        "- 解读：纯星上(θ)=能力天花板；协同-θ曲线斜率=调度边际贡献；θ→0.9 时协同应逼近纯星上",
        "",
        "| θ | 纯地面+EDF | 纯星上(θ) | 协同a-EDF | 协同b-EDF可行 |",
        "|---|---|---|---|---|",
    ]
    for th in THETAS:
        row = f"| {th:.1f} | {cell(th, '纯地面+EDF')} | {cell(th, '纯星上(θ)')} | {cell(th, '协同a-EDF')} | {cell(th, '协同b-EDF可行')} |"
        lines.append(row)
        print(row)

    if "--save" in sys.argv:
        out = Path(__file__).parent.parent / "benchmark" / "results" / "theta_sweep.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
