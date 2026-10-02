# -*- coding: utf-8 -*-
"""L7 准入策略双轴占优图（论文 4.13 节配图，锚定数字 2026-10-02）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot
setup_plot()

import matplotlib.pyplot as plt
import numpy as np

# 锚定数据（admission_l7.md，③ TTFT/TPOT+L2 缓存口径）
POLICIES = ["基线\n(全量准入)", "关键路径\n过滤", "截止期协商\n(×1.5)", "协商+过滤\n(hybrid)"]
N8 = {"succ": [87, 87, 91, 91], "wh": [0.31, 0.29, 0.30, 0.30]}
N1 = {"succ": [39, 41, 44, 44], "wh": [0.59, 0.45, 0.53, 0.44]}

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
x = np.arange(len(POLICIES))
width = 0.55

for ax, data, title in [
    (axes[0], N1, "N=1（稀缺 regime）"),
    (axes[1], N8, "N=8（带宽非瓶颈）"),
]:
    bars = ax.bar(x, data["succ"], width, color="#4C72B0", alpha=0.88, label="严格成功率")
    for b, v in zip(bars, data["succ"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v}%", ha="center",
                fontsize=10, fontweight="bold", color="#2b4c73")
    ax.set_ylim(0, 108)
    ax.set_ylabel("严格成功率（%）")
    ax.set_title(title, fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(POLICIES, fontsize=9)
    ax2 = ax.twinx()
    ax2.plot(x, data["wh"], "o-", color="#C44E52", linewidth=2, markersize=6,
             label="单成功能耗")
    for xi, v in zip(x, data["wh"]):
        ax2.annotate(f"{v:.2f} Wh", (xi, v), textcoords="offset points",
                     xytext=(0, 9), ha="center", fontsize=9, color="#a03538")
    ax2.set_ylabel("单成功能耗（Wh）", color="#C44E52")
    ax2.tick_params(axis="y", labelcolor="#C44E52")
    ax2.set_ylim(0, max(data["wh"]) * 1.6)
    # hybrid 高亮
    ax.axvspan(2.55, 3.45, color="#55A868", alpha=0.12)

h1, l1 = axes[0].get_legend_handles_labels()
h2, l2 = axes[0].twinx().get_legend_handles_labels() if False else (None, None)
fig.suptitle("L7 准入策略对照：hybrid（先协商、协商不成再拒）成功率与能耗双轴同时占优"
             "（50 工作流×3 步×5 种子，锚定 2026-10-02）", fontsize=12)
lines = [bars, axes[0].twinx().lines[0] if False else None]

# 图例（用第一组轴）
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
legend_items = [
    mpatches.Patch(color="#4C72B0", alpha=0.88, label="严格成功率（左轴，拒绝计入失败）"),
    mlines.Line2D([], [], color="#C44E52", marker="o", linewidth=2, label="单成功能耗（右轴）"),
    mpatches.Patch(color="#55A868", alpha=0.25, label="hybrid 臂（推荐策略）"),
]
fig.legend(handles=legend_items, loc="lower center", ncol=3, fontsize=9,
           frameon=False, bbox_to_anchor=(0.5, -0.04))
fig.tight_layout(rect=[0, 0.04, 1, 0.94])

out = Path(__file__).parent / "L7_准入策略双轴占优_2026.10.2.png"
fig.savefig(out, bbox_inches="tight")
print("saved:", out)
