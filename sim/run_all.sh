#!/usr/bin/env bash
# 一键复现论文全部实验（对应 sim/REPRODUCE.md 映射表）。
# 用法：bash sim/run_all.sh            全量（约 10 分钟）
#       bash sim/run_all.sh 4.11.4    只跑单节（论文章节号）
#
# 注意：TLE 窗口随实际日期变化，重跑数字可能与论文表格有 ±数点漂移
# （论文表格为冻结记录，见 docs/论文冻结版-2026.10.2/）。
# 运行前自动把已有 benchmark/results/ 快照到 benchmark/results-archive-<日期>/。
set -euo pipefail

cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
OUT=../benchmark/results
ONLY="${1:-}"
mkdir -p "$OUT"

# 快照已冻结的实验结果，防止被本次运行覆盖
if [ -z "$ONLY" ] && [ -d "$OUT" ] && [ -n "$(ls -A "$OUT" 2>/dev/null)" ]; then
  SNAP=../benchmark/results-archive-$(date +%Y%m%d-%H%M%S)
  cp -R "$OUT" "$SNAP"
  echo "已快照既有结果至 benchmark/$(basename "$SNAP")/"
fi

run() {  # run <章节号> <说明> <脚本...>
  local sec="$1"; shift
  local desc="$1"; shift
  if [ $# -eq 0 ]; then echo "[$sec] 跳过：$desc（4.8 实测待 2026.12 硬件）"; return; fi
  case "$sec" in
    "$ONLY"|*"$ONLY"*) ;;
    *) [ -n "$ONLY" ] && return ;;
  esac
  echo "[$sec] $desc"
  "$PY" "$@"
}

# TLE 缓存：存在则离线复现，缺失则需联网拉取（CelesTrak）
if [ ! -s data/iss.tle ]; then
  echo "[0] 获取 ISS TLE（需联网，缓存至 data/iss.tle）"
  "$PY" run_tle.py > /dev/null
fi

run 4.1  "实验设置：ISS TLE 窗口时间线"            run_tle.py
run 4.2  "主实验：真实过境排队感知调度"            run_tle_queued.py --save
run 4.3  "参数扫描：受限程度×协同优势（合成）"     experiments.py --save
run 4.3b "仰角阈值稳健性"                          run_tle_elev_sweep.py
run 4.4  "能力阈值敏感性"                          run_theta_sweep.py
run 4.5  "应急重规划（TLE）"                       run_tle_emergency.py
run 4.5b "应急重规划（合成场景消融）"              run_emergency.py
run 4.6  "置信度路由消融"                          run_confidence_sweep.py
run 4.7  "能耗效率帕累托"                          run_energy_compare.py
run 4.8  "星上压缩加速实测"
run 4.9  "多星组网 scaling"                        run_constellation_l4.py
run 4.10 "工作流：单星交付语义翻转"                run_agentflow.py
run 4.10b "工作流：组网超可加"                     run_agentflow_constellation.py
run 4.11.1 "延迟建模：单任务缓存红利"              run_inference_l6.py
run 4.11.1b "前缀缓存专项"                         run_prefix_l2.py
run 4.11.2 "工作流 delta-only 传输"                run_inference_l6b.py
run 4.11.3 "三杠杆叠加与 87% 上限"                 run_inference_l6c.py
run 4.11.4 "在线重规划负结果"                      run_inference_l6d.py
run L7   "准入控制：过滤×协商×组合"                run_admission_l7.py

echo "完成。结果在 benchmark/results/，映射表见 sim/REPRODUCE.md"
