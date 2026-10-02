# 论文实验复现映射（REPRODUCE）

> 本文档是论文《基于输出置信度的星地动态分层推理方法》实验章的**复现契约**：
> 每个论文小节 → 生成它的脚本 → 落盘的结果文件 → 该节的招牌数字。
> 一键复现：`bash sim/run_all.sh`（按论文章节顺序执行全部实验，约 10 分钟内，
> 结果写入 `benchmark/results/`，该目录被 gitignore，属本地产物）。
>
> 环境：Python ≥ 3.10，依赖见 `sim/requirements.txt`（sgp4 必需；其余为标准库级）。
> 首次运行需联网从 CelesTrak 拉取 TLE（缓存在 `sim/data/iss.tle`），之后可离线复现。
> 所有实验固定随机种子，多次运行结果逐字节一致（回归已验证，见 README v0.9d 节）。

## 映射总表

| 论文章节 | 内容 | 脚本 | 结果文件 | 招牌数字 |
|---|---|---|---|---|
| 4.1 | 实验设置（ISS TLE 轨道） | `run_tle.py`（生成窗口时间线） | `sim/data/iss.tle`、`benchmark/results/tle_iss.md` | 3–4 次过境/天、17–20 min 累计窗口 |
| 4.2 | 主实验：真实过境排队感知调度 | `run_tle_queued.py --save` | `benchmark/results/tle_iss_queued.md` | 纯地面 2–3%，协同 33% vs 30% |
| 4.3 | 参数扫描：受限程度 × 协同优势 | `experiments.py --save`（合成场景双因素 × 5 种子） | `benchmark/results/sweep_v0.3.md` | 可行性检查收益 5 min 窗口下 +19 点 |
| 4.3 补充 | 仰角阈值稳健性（TLE） | `run_tle_elev_sweep.py` | `benchmark/results/tle_elev_sweep.md` | 0°/5°/10° → 7/5/3 次过境/天 |
| 4.4 | 能力阈值敏感性（天花板线性律） | `run_theta_sweep.py` | `benchmark/results/theta_sweep.md` | 天花板斜率 ≈ 100%/% |
| 4.5 | 应急重规划：抢占 × 可行性检查 | `run_tle_emergency.py`（TLE 场景）/ `run_emergency.py`（合成场景） | `benchmark/results/tle_emergency.md`、`emergency_v0.4.md` | 应急成功率 +12 点（38%→50%） |
| 4.6 | 置信度路由消融：τ 三目标权衡 | `run_confidence_sweep.py` | `benchmark/results/confidence_sweep.md` | τ=0.3 稀缺 regime 全胜、τ=0.7 多负 |
| 4.7 | 能耗效率：帕累托点 | `run_energy_compare.py` | `benchmark/results/energy_compare.md` | 0.93 Wh（τ=0.5）、纯地面 15%、纯星上 37–40% |
| 4.8 | 星上压缩加速实测 | ⏳ 待 2026.12 Jetson Orin 实测回填 | — | — |
| 4.9 | 多星组网 scaling | `run_constellation_l4.py` | `benchmark/results/constellation_l4.md` | N=1→8：33%→63%，未饱和 |
| 4.10 | 多步 Agent 工作流（交付语义翻转 / 超可加） | `run_agentflow.py`（单星）/ `run_agentflow_constellation.py`（组网） | `benchmark/results/agentflow_v0.8.md`、`agentflow_constellation.md` | 补偿 × 组网 +67 点（>+2+39）、N=8 处 85% |
| 4.11.1 | 单任务延迟建模（缓存红利翻倍） | `run_inference_l6.py` | `benchmark/results/inference_l6.md` | 省链路秒数 + 省 prefill 的双红利 |
| 4.11.1 补充 | 前缀缓存专项（L2） | `run_prefix_l2.py` | `benchmark/results/prefix_l2.md` | 缓存命中步近 4 倍便宜 |
| 4.11.2 | 工作流层 delta-only 传输 | `run_inference_l6b.py` | `benchmark/results/inference_l6b.md` | 工作流成功率 22%→54% |
| 4.11.3 | 三杠杆叠加与 87% 上限归因 | `run_inference_l6c.py` | `benchmark/results/inference_l6c.md` | 稀缺 regime +23/24 点；N≥4 收敛 87% |
| 4.11.4 | 在线重规划边界（干净负结果） | `run_inference_l6d.py` | `benchmark/results/inference_l6d.md` | 赌赢率 1/14 ≈ 7%，调度侧杠杆穷尽 |
| 图 3–6 | 主文插图 | `make_figs_3_6.py` | 仓库根 `figures/`（如存在） | — |
| 图 7 | 星座 scaling 插图 | `make_fig7_constellation.py` | 仓库根 `figures/`（如存在） | — |

## 复现顺序与依赖

```bash
bash sim/run_all.sh        # 全量：14 个实验脚本，按论文章节顺序
```

依赖关系：仅 4.1 的 TLE 获取依赖网络（缓存后离线可跑）；其余脚本相互独立，
可任意单跑（如 `cd sim && python run_inference_l6d.py`）。`make_figs_*.py`
读取 `benchmark/results/` 产物，需在对应实验跑完后执行。

⚠️ **日期漂移**：TLE 窗口随实际日期变化，重跑 4.2/4.5/4.11 等基于真实轨道的
实验，成功率可能与论文表格有 ±数点漂移（窗口几何逐日不同，属真实世界因素，
README v0.9 节已讨论）。论文表格数字以冻结轮（2026.10.2）为准；
`run_all.sh` 全量运行前会自动把既有 `benchmark/results/` 快照到
`benchmark/results-archive-<时间戳>/`，冻结记录不会丢失。

## 数字锚点速查（与摘要/结论一致）

| 锚点 | 值 | 出处小节 |
|---|---|---|
| 纯地面成功率 | 2–5%（4.2 场景 2–3%） | 4.2 |
| 分层协同（单星） | 33% | 4.2 |
| 星座 N=8（单任务） | 63% | 4.9 |
| 工作流 补偿×组网（N=8） | 85%（超可加：+67 > +2+39） | 4.10 |
| 工作流延迟建模 | 22%→54% | 4.11.2 |
| 三杠杆叠加上限 | 87%（N≥4 收敛） | 4.11.3 |
| 单成功能耗 | 0.93 Wh（纯地面 15%、纯星上 37–40%） | 4.7 |
| 重规划赌赢率 | 1/14 ≈ 7%（负结果） | 4.11.4 |
| 窗口物理量 | 3–4 次过境/天、17–20 min | 4.1 |

## 已知边界（与论文 4.12 建模边界声明对应）

- 全部仿真基于合成任务流 + 真实 TLE 窗口，不含在轨实测（4.8 补）；
- 链路二值化（窗口内可用/窗外不可用），无雨衰与速率自适应；
- 工程常数（50 token/s 传输、1000/20 token/s prefill/decode、15 W/10 W 功耗）
  为假设值，2026.12 起以 Jetson Orin 实测逐条校准。
