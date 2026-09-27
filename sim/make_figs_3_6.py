# -*- coding: utf-8 -*-
"""生成论文图 3-6（数据来源：benchmark/results/ 各实验 md，2026.9 实验）。

- 图 3：参数扫描热力图（过境周期 × 窗口时长 → 协同b 成功率）
- 图 4：θ-成功率曲线（天花板线性 + 协同恒超天花板）
- 图 5：τ-成功率-误收率权衡曲线（多目标帕累托，k=10 / k=5 双子图）
- 图 6：能耗对比柱状图（单成功能耗）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot

import matplotlib.pyplot as plt
import numpy as np

setup_plot()
OUT = Path(__file__).parent.parent / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------- 图 3：参数扫描热力图（sweep_v0.3 协同b-EDF可行） ----------
periods = ["1h", "1.5h", "2h"]
durations = ["5min", "10min", "15min"]
# 行=周期，列=窗口时长；% 成功率
coop_b = np.array([
    [61, 91, 96],
    [49, 72, 90],
    [45, 63, 79],
])
ground = np.array([
    [11, 61, 93],
    [5, 21, 66],
    [3, 11, 26],
])

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, data, title in (
    (axes[0], ground, "纯地面+EDF"),
    (axes[1], coop_b, "星地协同b（EDF+可行性）"),
):
    im = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=100)
    ax.set_xticks(range(3), durations)
    ax.set_yticks(range(3), periods)
    ax.set_xlabel("过境窗口时长")
    ax.set_ylabel("过境周期")
    ax.set_title(title, fontsize=11)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{data[i, j]}%", ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="black" if 30 < data[i, j] < 75 else "white")
cax = fig.add_axes([0.92, 0.18, 0.02, 0.6])
fig.colorbar(im, cax=cax, label="任务成功率（%）")
fig.suptitle("图 3  链路受限扫描（100 任务 × 5 种子）：越受限，协同优势越大",
             fontsize=12)
fig.subplots_adjust(left=0.08, right=0.90, top=0.85, bottom=0.12, wspace=0.35)
fig.savefig(OUT / "fig3_param_heatmap.png", dpi=150)
plt.close(fig)
print("fig3 saved")

# ---------------- 图 4：θ-成功率曲线（theta_sweep） ------------------------
theta = [0.1, 0.3, 0.5, 0.7, 0.9]
star_only = [8, 26, 46, 64, 88]
coop_a = [11, 30, 50, 68, 91]
coop_b = [13, 32, 52, 70, 91]
ground_edf = [2] * 5

fig, ax = plt.subplots(figsize=(7, 4.2))
ax.plot(theta, star_only, "o--", color="#7f7f7f", lw=2, label="纯星上(θ)＝能力天花板")
ax.plot(theta, coop_a, "s-", color="#1f77b4", lw=2, label="协同a-EDF")
ax.plot(theta, coop_b, "o-", color="#d62728", lw=2, label="协同b-EDF可行")
ax.plot(theta, ground_edf, ":", color="#2ca02c", lw=2, label="纯地面+EDF（恒 2%）")
for x, y in zip(theta, star_only):
    ax.annotate(f"{y}%", (x, y), textcoords="offset points",
                xytext=(0, -14), ha="center", fontsize=9, color="#7f7f7f")
for x, y in zip(theta, coop_b):
    ax.annotate(f"{y}%", (x, y), textcoords="offset points",
                xytext=(0, 9), ha="center", fontsize=9, color="#d62728")
ax.set_xlabel("星上能力阈值 θ（星上可解任务比例）")
ax.set_ylabel("任务成功率（%）")
ax.set_ylim(0, 100)
ax.set_title("图 4  能力阈值敏感性（TLE 真实轨道）：协同恒超天花板 +3~6 点\n"
             "θ≥0.9 时协同逼近纯星上——能力-链路替代关系", fontsize=11)
ax.legend(fontsize=9, loc="upper left")
fig.tight_layout()
fig.savefig(OUT / "fig4_theta_curve.png", bbox_inches="tight", dpi=150)
plt.close(fig)
print("fig4 saved")

# ---------------- 图 5：τ-成功率-误收率权衡（confidence_sweep） ------------
# 数据：(误收/100, 成功率%)，τ = 0.3 → 0.7 三点一线
curves = {
    ("k=10", "校准"): [(12.8, 30), (6.6, 27), (3.0, 22)],
    ("k=10", "过度自信"): [(22.8, 33), (10.6, 30), (5.6, 26)],
    ("k=10", "不自信"): [(7.8, 28), (3.4, 23), (1.6, 14)],
    ("k=5", "校准"): [(20.4, 30), (10.4, 23), (3.4, 13)],
    ("k=5", "过度自信"): [(36.4, 34), (17.6, 28), (7.8, 21)],
    ("k=5", "不自信"): [(12.6, 26), (4.0, 16), (0.2, 8)],
}
taus = ["τ=0.3", "τ=0.5", "τ=0.7"]
colors = {"校准": "#1f77b4", "过度自信": "#d62728", "不自信": "#7f7f7f"}
markers = {"k=10": "o", "k=5": "s"}

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
for ax, k in zip(axes, ("k=10", "k=5")):
    for (kk, cal), pts in curves.items():
        if kk != k:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, marker=markers[k], color=colors[cal], lw=1.8,
                label=cal)
        off = {"校准": (7, -13), "过度自信": (7, 6), "不自信": (-10, 8)}[cal]
        for (x, y), tau in zip(pts, taus):
            ax.annotate(tau, (x, y), textcoords="offset points",
                        xytext=off, fontsize=8, color=colors[cal],
                        ha="left" if off[0] > 0 else "right")
    ax.set_xlabel("误收率（置信度≥τ 但答案错，个/100 任务）")
    ax.set_title(f"能力边界 {k}", fontsize=11)
    ax.set_xlim(0, 40)
    ax.set_ylim(0, 40)
    ax.legend(fontsize=9)
axes[0].set_ylabel("任务成功率（%）")
fig.suptitle("图 5  置信度路由的 τ 权衡：成功率-误收率多目标帕累托\n"
             "（TLE 真实轨道，硬阈值基线 26-27%；链路稀缺下低τ胜率更高）",
             fontsize=12)
fig.tight_layout()
fig.savefig(OUT / "fig5_tau_pareto.png", bbox_inches="tight", dpi=150)
plt.close(fig)
print("fig5 saved")

# ---------------- 图 6：能耗对比柱状图（energy_compare） -------------------
schemes = ["纯地面\nEDF可行", "纯星上\n(θ=0.3)", "硬阈值\nθ=0.3",
           "置信度路由\nτ=0.5", "置信度路由\nτ=0.3"]
per_success = [6.35, 2.53, 0.94, 0.93, 1.00]
succ = [5, 27, 26, 27, 30]

fig, ax = plt.subplots(figsize=(7.2, 4.2))
bars = ax.bar(schemes, per_success,
              color=["#2ca02c", "#7f7f7f", "#1f77b4", "#1f77b4", "#d62728"])
for b, s in zip(bars, succ):
    ax.annotate(f"{b.get_height():.2f} Wh",
                (b.get_x() + b.get_width() / 2, b.get_height()),
                textcoords="offset points", xytext=(0, 4),
                ha="center", fontsize=10, fontweight="bold")
    ax.annotate(f"成功率 {s}%",
                (b.get_x() + b.get_width() / 2, 0.15),
                ha="center", fontsize=8.5, color="white")
ax.set_ylabel("单成功能耗（Wh / 个成功任务）")
ax.set_ylim(0, 7.5)
ax.set_title("图 6  能耗效率对比（TLE 真实轨道，θ=0.3，k=10，校准良好）\n"
             "分层方案单成功能耗仅为纯星上 37-40%、纯地面 15%",
             fontsize=11)
fig.tight_layout()
fig.savefig(OUT / "fig6_energy_bars.png", bbox_inches="tight", dpi=150)
plt.close(fig)
print("fig6 saved")
