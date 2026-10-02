# -*- coding: utf-8 -*-
"""图 2：过境窗口时间线示意图（含 b-EDF 排队与应急抢占可行性检查）。
窗口取自冻结锚点 N1 缓存（2026-10-02T00:23Z），任务与应急事件为示意值。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot
setup_plot()
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import json

base = Path(__file__).parent.parent / ".." / "sim" / "data" / "frozen_windows"
d = json.load(open(base / "N1_2026-10-02T002300p0000.json"))
W = [(a, b) for a, b, *_ in d["windows"]]  # [(5620,6020),(29280,29500),(35000,35400)]

fig, ax = plt.subplots(figsize=(15.5, 7.6))
X0, X1 = 0, 38000
ax.set_xlim(X0, X1); ax.set_ylim(0, 11.4); ax.axis("off")

def hhmm(s):
    return f"{int(s//3600):02d}:{int((s%3600)//60):02d}"

def lane(y, label, color="#475569"):
    ax.text(-350, y + 0.45, label, ha="right", va="center", fontsize=10.5,
            fontweight="bold", color=color)

def bar(x1, x2, y, h, fc, ec, label=None, fs=9, bold=False, ls="-"):
    ax.add_patch(FancyBboxPatch((x1, y), x2 - x1, h, boxstyle="round,pad=0.05,rounding_size=0.15",
                                fc=fc, ec=ec, lw=1.5, linestyle=ls))
    if label:
        ax.text((x1 + x2) / 2, y + h / 2, label, ha="center", va="center",
                fontsize=fs, fontweight="bold" if bold else "normal", color="#1e293b")

def arrow(x1, y1, x2, y2, color, lw=1.8, ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15,
                                 color=color, lw=lw, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}"))

# ── 时间轴 ─────────────────────────────────────────
for t in range(0, 38001, 5000):
    ax.plot([t, t], [0.55, 0.85], color="#94a3b8", lw=1)
    ax.text(t, 0.1, hhmm(t), ha="center", fontsize=9, color="#64748b")
ax.annotate("", xy=(38000, 0.7), xytext=(0, 0.7), arrowprops=dict(arrowstyle="-|>", color="#94a3b8", lw=1.2))

# ── Lane 1：过境窗口 ─────────────────────────────
lane(10, "过境窗口")
for i, (a, b) in enumerate(W, 1):
    bar(a, b, 10, 0.9, "#dcfce7", "#16a34a")
    ax.text((a + b) / 2, 10.45, f"W{i}", ha="center", va="center", fontsize=10, fontweight="bold", color="#15803d")
    ax.annotate(f"{hhmm(a)}–{hhmm(b)}", xy=(b, 10.9), xytext=(b + 420, 11.15), fontsize=8.5, color="#15803d")
ax.plot([0, 38000], [10, 10], color="#cbd5e1", lw=0)  # 占位

# ── Lane 2：任务到达 + b-EDF 队列 ─────────────────
lane(8, "任务到达\n与 b-EDF 队列", "#2563eb")
for t, name, dl in [(1000, "T1", 20000), (1500, "T2", 34000), (2000, "T3", 40000)]:
    ax.plot([t], [8.0], marker="v", ms=10, color="#2563eb")
ax.text(6200, 7.75, "T1 / T2 / T3 依次到达（00:17–00:33）　"
        "截止期：T1 05:33，T2 09:26，T3 11:06", fontsize=8.5, color="#1e40af")
ax.text(9500, 8.5, "b-EDF 队列（按截止期排序）：T1 → T2 → T3，窗口到达时队首优先上送", fontsize=9.5, color="#1e40af")

# ── Lane 3：窗口内上送传输 ───────────────────────
lane(6, "窗口内\n上送传输", "#2563eb")
bar(5620, 5800, 6, 0.85, "#dbeafe", "#2563eb", "T1 上送")
bar(29280, 29400, 6, 0.85, "#dbeafe", "#2563eb", "T2 上送")
bar(35000, 35150, 6, 0.85, "#dbeafe", "#2563eb", "T3 上送")

# ── Lane 4：应急事件与抢占 ───────────────────────
lane(3.2, "应急任务 E\n（deadline 1800 s）", "#dc2626")
E_ARR, E_DL = 27800, 29600
ax.plot([E_ARR], [3.2], marker="v", ms=12, color="#dc2626")
ax.text(E_ARR - 150, 2.6, f"E 到达 {hhmm(E_ARR)}", ha="right", fontsize=8.5, color="#991b1b")
arrow(E_ARR, 3.6, E_DL, 3.6, "#dc2626", lw=1.6, ls="--")
ax.text((E_ARR + E_DL) / 2, 3.85, "截止期", ha="center", fontsize=8.5, color="#991b1b")
bar(29280, 29430, 3.2, 0.85, "#fee2e2", "#dc2626", "E 抢占 W2 队首", bold=True)

# T2 被抢占 → 改排检查
arrow(29340, 6.0, 35000, 4.2, "#d97706", lw=1.6, ls="--", rad=-0.25)
ax.text(31800, 5.6, "T2 被挤出 W2", fontsize=8.5, color="#b45309")

# ── Lane 5：可行性检查结论 ───────────────────────
lane(1.2, "抢占前可行性检查\n（preempt_feasible）", "#9333ea")
bar(500, 15000, 1.2, 1.5, "#f3e8ff", "#9333ea")
ax.text(1500, 1.95, "检查：T2 剩余传输能否改排后续窗口？\n"
                    "→ T2 截止期 09:26（34000 s）早于 W3 开始 09:43（35000 s），改排不可行\n"
                    "→ 拒绝抢占，E 回退为正常排队（4.5 节 / 表 5 语义）",
        fontsize=9, va="center", color="#6b21a8")

ax.set_title("图 2  过境窗口时间线示意：b-EDF 排队上送与应急抢占的可行性检查"
             "（窗口取冻结锚点 N1，2026-10-02；任务与应急事件为示意值）",
             fontsize=14, fontweight="bold", pad=14)

out = Path(__file__).parent / "图2_过境窗口时间线示意_2026.10.2.png"
fig.savefig(out, bbox_inches="tight", dpi=150)
print("saved:", out)
