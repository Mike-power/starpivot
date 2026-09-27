# -*- coding: utf-8 -*-
"""生成论文图 7：星座 scaling 双轴曲线（N-成功率 + N-带宽扩容）。

数据来源：benchmark/results/constellation_l4.md（2026.9.27 实验）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot

import matplotlib.pyplot as plt

setup_plot()

N = [1, 2, 4, 8]
succ = [33, 39, 48, 63]           # %
bandwidth = [18, 36, 76, 152]     # 分钟/天
star_only_ceiling = 26            # 纯星上天花板参照

fig, ax1 = plt.subplots(figsize=(7.2, 4.2))

# 左轴：成功率
l1 = ax1.plot(N, succ, "o-", color="#1f77b4", lw=2, ms=7,
              label="协同b成功率（左轴）")
l_ceiling = ax1.axhline(star_only_ceiling, ls="--", color="#d62728", lw=1.5,
                        label="纯星上天花板 26%（参照）")
ax1.set_xlabel("星座星数 N（相位偏移合成，同轨道面）")
ax1.set_ylabel("任务成功率（%）", color="#1f77b4")
ax1.set_ylim(0, 80)
ax1.tick_params(axis="y", labelcolor="#1f77b4")
ax1.set_xticks(N)

for x, y in zip(N, succ):
    off = (0, 8) if x < 8 else (-14, 10)
    ax1.annotate(f"{y}%", (x, y), textcoords="offset points",
                 xytext=off, ha="center", fontsize=9, color="#1f77b4")

# 右轴：链路带宽
ax2 = ax1.twinx()
l2 = ax2.plot(N, bandwidth, "s--", color="#2ca02c", lw=2, ms=7,
              label="窗口带宽（右轴）")
ax2.set_ylabel("过境窗口累计时长（分钟/天）", color="#2ca02c")
ax2.set_ylim(0, 200)
ax2.tick_params(axis="y", labelcolor="#2ca02c")

for x, y in zip(N, bandwidth):
    off = (12, -3) if x < 8 else (-16, -12)
    ax2.annotate(f"{y}", (x, y), textcoords="offset points",
                 xytext=off, ha="left", fontsize=9, color="#2ca02c")

lines = l1 + l2 + [l_ceiling]
ax1.legend(lines, [l.get_label() for l in lines], loc="upper left", fontsize=9)
ax1.set_title("星座规模 scaling：成功率单调未饱和，带宽扩容收益递减\n"
              "（TLE 相位偏移合成星座，单站窗口并集，100 任务 × 5 种子）",
              fontsize=11)

fig.tight_layout()
out = Path(__file__).parent.parent / "docs" / "figures" / "fig7_constellation_scaling.png"
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, bbox_inches="tight", dpi=150)
print(f"已保存：{out}")
