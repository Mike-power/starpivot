# -*- coding: utf-8 -*-
"""图 1：星地协同分层推理系统架构图（含置信度路由决策流）。论文 v1.2 口径。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot
setup_plot()
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(16, 9.2))
ax.set_xlim(0, 100); ax.set_ylim(0, 58); ax.axis("off")

C_SAT = "#dbeafe"; C_SAT_E = "#2563eb"   # 星上 蓝
C_GND = "#fef3c7"; C_GND_E = "#d97706"   # 地面 琥珀
C_LNK = "#fee2e2"; C_LNK_E = "#dc2626"   # 链路 红
C_OK = "#dcfce7"; C_OK_E = "#16a34a"     # 本地成功 绿
C_DEC = "#f3e8ff"; C_DEC_E = "#9333ea"   # 决策 紫
C_WF = "#f1f5f9"; C_WF_E = "#475569"     # 工作流 灰

def box(x, y, w, h, text, fc, ec, fs=10.5, lw=1.4, bold=False, r=0.9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.18,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", linespacing=1.45)

def arrow(x1, y1, x2, y2, color="#334155", lw=1.8, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                                 color=color, lw=lw, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}"))

ax.text(50, 56.6, "图 1  星地协同分层推理系统架构与置信度路由决策流",
        ha="center", fontsize=15, fontweight="bold")

# ── 顶部：多步智能体工作流 ─────────────────────────
box(24, 51, 52, 3.6, "多步智能体工作流（3 步就绪链：观测规划 → 数据筛选 → 应急重规划）",
    C_WF, C_WF_E, fs=11, bold=True)
ax.text(79.5, 52.8, "步级补偿 · 前缀缓存 · 截止期协商/准入过滤", fontsize=9, color="#475569", va="center")

# ── 星上侧 ─────────────────────────────────────────
box(2, 28, 34, 20, "", C_SAT, C_SAT_E, lw=2)
ax.text(19, 46.2, "星上侧（LEO，Jetson Orin 等效平台）", ha="center", fontsize=11.5, fontweight="bold", color="#1e40af")
box(4.5, 41, 29, 4.2, "LoRA 蒸馏小模型（1.5–7B）\nAWQ 量化 + 投机解码（4.8 节回填实测）", "#ffffff", C_SAT_E, fs=9.5)
box(4.5, 35.2, 29, 4.6, "输出置信度自评 σ(x)\n（复杂度 → 达标概率，概率契约 4.1 节）", "#ffffff", C_SAT_E, fs=9.5)
box(4.5, 29.8, 13.6, 4.2, "σ ≥ τ\n本地提交\n（星上即时）", C_OK, C_OK_E, fs=9.5, bold=True)
box(19.9, 29.8, 13.6, 4.2, "σ < τ\n排队上送\n（窗口队列 b-EDF）", "#ffffff", C_SAT_E, fs=9.5, bold=True)

# ── 地面侧 ─────────────────────────────────────────
box(64, 28, 34, 20, "", C_GND, C_GND_E, lw=2)
ax.text(81, 46.2, "地面侧（地面站 + vLLM 服务）", ha="center", fontsize=11.5, fontweight="bold", color="#92400e")
box(66.5, 41, 29, 4.2, "32B 大模型 + 前缀缓存复用\n工具调用投机执行（就绪链加速）", "#ffffff", C_GND_E, fs=9.5)
box(66.5, 35.2, 29, 4.6, "复杂规划与兜底（困难任务）\n结果回传星上，合并进工作流状态", "#ffffff", C_GND_E, fs=9.5)
box(66.5, 29.8, 29, 4.2, "TTFT / TPOT 分段延迟模型（4.11 节）", "#ffffff", C_GND_E, fs=9.5)

# ── 链路 ──────────────────────────────────────────
box(38.5, 30.5, 23, 15, "", C_LNK, C_LNK_E, lw=2)
ax.text(50, 43.6, "星地链路（过境窗口）", ha="center", fontsize=11, fontweight="bold", color="#991b1b")
box(40, 38.6, 20, 3.6, "TLE 实时解算窗口（SGP4，单站 3–4 次/天）", "#ffffff", C_LNK_E, fs=9)
box(40, 34.4, 20, 3.2, "窗口队列调度 b-EDF + 应急抢占重规划", "#ffffff", C_LNK_E, fs=9)
box(40, 30.9, 20, 2.8, "带宽受限 · 延迟注入模拟", "#ffffff", C_LNK_E, fs=9)

# ── 决策流 ─────────────────────────────────────────
box(38.5, 21.5, 23, 6.5, "置信度路由（本文核心）\n硬阈值 θ 分级 → 连续 τ 帕累托最优\n（能力-链路替代，3.3 / 4.6 节）", C_DEC, C_DEC_E, fs=9.8, bold=True)

# ── 底部结果带 ─────────────────────────────────────
box(14, 14.5, 72, 4.2, "结果合并：本地提交 ∪ 地面回传 → 工作流推进下一步；误收重试 / 步级补偿兜底（4.10 节）",
    "#ffffff", "#334155", fs=10.5, bold=True)

# ── 箭头 ──────────────────────────────────────────
arrow(50, 51, 50, 47.5, lw=2)                       # 工作流 → 链路区上方（分解到两侧由下方箭头表达）
arrow(50, 47.5, 19, 47.5, lw=1.6, rad=0.25)         # 到星上
arrow(50, 47.5, 81, 47.5, lw=1.6, rad=-0.25)        # 到地面
arrow(33.5, 37.5, 40, 37.5, color=C_SAT_E, lw=2)    # 星上 → 链路（σ<τ 上送）
ax.text(36.5, 38.3, "上送", fontsize=8.5, color=C_SAT_E, ha="center")
arrow(60, 37.5, 66.5, 37.5, color=C_GND_E, lw=2)    # 链路 → 地面
ax.text(63.5, 38.3, "排队\n到达", fontsize=8, color=C_GND_E, ha="center")
arrow(50, 30.5, 50, 28.2, color=C_DEC_E, lw=2)      # 链路 → 决策
arrow(50, 21.5, 50, 18.9, color=C_DEC_E, lw=2)      # 决策 → 结果
arrow(26.8, 29.8, 26.8, 19.2, color=C_OK_E, lw=1.8) # 本地提交 → 结果带
arrow(73, 29.8, 66, 19.2, color=C_GND_E, lw=1.8, rad=-0.12)  # 地面回传 → 结果带

# ── 标注 ──────────────────────────────────────────
ax.text(50, 11.2, "口径：100 任务/场景 × 5 种子，TLE 真实轨道（锚定 2026-10-02）；链路稀缺 regime 下单站日窗口 17–20 min",
        ha="center", fontsize=9, color="#64748b")
ax.text(50, 8.6, "开源仿真评测：sim/（星座场景 + 排队调度）· benchmark/（三基线 × 四维度指标）",
        ha="center", fontsize=9, color="#64748b")

out = Path(__file__).parent / "图1_星地协同分层推理系统架构_2026.10.2.png"
fig.savefig(out, bbox_inches="tight", dpi=150)
print("saved:", out)
