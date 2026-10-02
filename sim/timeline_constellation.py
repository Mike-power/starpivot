# -*- coding: utf-8 -*-
"""多星组网时间线：相位偏移合成 N 星星座，单站窗口池化。

合成方法（诚实声明）：以真实 TLE 为基准，对 TLE line2 的
平近点角（M，列 43:52）施加 360°/N 的等相位偏移，得到 N 颗
同轨道面、相位均匀分布的卫星（Walker 式相位偏移的思想，
但轨道面/倾角均沿用基准星，非真实多轨道面星座）。

单站约束：同一天线不能同时跟踪两颗星，因此对所有星的过境窗口
取并集（重叠窗口合并），窗口内容量沿用单链路语义。

接口与 TleTimeline / SyntheticTimeline 鸭子类型兼容：
find(t) / commit(w, t) / windows / capacity / horizon / summary()。
"""

from datetime import datetime, timezone
from pathlib import Path

from sgp4.api import Satrec

from timeline import ContactWindow
from timeline_tle import DATA_DIR, STATION_LAT, STATION_LON, compute_windows

# 论文 v1.1 冻结锚点：全部 L 系列工作流实验的窗口几何以该 UTC 时刻为
# 仿真起点（= 北京 2026-10-02 08:23，v1.1 冻结轮 l6c/l6d 的实际运行时刻，
# 已验证逐行复现论文表格：N=8 duration 87%、0/6/0）。
# 引用论文数字时必须用此锚定复现；None 则回到"当前时刻"语义（窗口随运行日期漂移）。
FROZEN_EPOCH = "2026-10-02T00:23:00+00:00"

# 冻结窗口缓存：锚定 epoch 下生成的窗口序列被序列化到 JSON，
# 之后任何日期重跑都加载逐字节一致的窗口（成功率、计数全部复现，
# 不再受运行日期影响）。删除缓存文件即回到 epoch 重算。
FROZEN_DIR = DATA_DIR / "frozen_windows"


def _frozen_path(n_sats: int, epoch_iso: str) -> Path:
    safe = epoch_iso.replace(":", "").replace("+", "p")
    return FROZEN_DIR / f"N{n_sats}_{safe}.json"


def _save_frozen(path: Path, n_sats: int, epoch_iso: str,
                 windows: list) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "n_sats": n_sats, "epoch": epoch_iso,
        "windows": [[w.start, w.end, w.capacity] for w in windows],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _load_frozen(path: Path) -> list:
    import json
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [ContactWindow(s, e, c) for s, e, c in payload["windows"]]


class ConstellationTimeline:
    """N 星等相位星座 + 单地面站窗口并集。

    n_sats:       星数（相位偏移生成）
    station_lat/lon: 地面站坐标（默认上海站）
    min_elev_deg: 最小仰角阈值
    horizon:      仿真时长（秒）
    capacity:     单窗口链路容量（排队模型下不使用）
    """

    def __init__(
        self,
        tle_path: Path | str = DATA_DIR / "iss.tle",
        n_sats: int = 4,
        station_lat: float = STATION_LAT,
        station_lon: float = STATION_LON,
        min_elev_deg: float = 10.0,
        horizon: float = 86400.0,
        capacity: int = 4,
        epoch: "datetime | str | None" = None,
    ):
        """epoch: 锚定仿真的起始 UTC 时刻（datetime 或 ISO 字符串）。
        None = 当前时刻（默认，窗口随运行日期漂移）；
        传固定值则窗口几何冻结——论文实验数字的锚定复现入口。
        冻结缓存：epoch 非 None 时先查 sim/data/frozen_windows/，
        命中则加载逐字节一致的窗口；未命中则计算并写入缓存。"""
        self.capacity = capacity
        self.horizon = horizon
        self.n_sats = n_sats

        if epoch is None:
            self.t0 = datetime.now(timezone.utc)
        elif isinstance(epoch, str):
            self.t0 = datetime.fromisoformat(epoch)
        else:
            self.t0 = epoch

        frozen = None if epoch is None else _frozen_path(n_sats, self.t0.isoformat())
        if frozen is not None and frozen.exists():
            self.windows = _load_frozen(frozen)
            return

        text = Path(tle_path).read_text(encoding="utf-8").strip().splitlines()
        line1, line2 = text[1].strip(), text[2].strip()
        # 平近点角 M 在 line2 第 43:51 列（%8.4f 度），其后第 51 列为空格分隔符
        base_ma = float(line2[43:51])

        # 逐星生成相位偏移 TLE 并计算各自过境窗口
        all_windows: list[ContactWindow] = []
        for k in range(n_sats):
            ma = (base_ma + 360.0 * k / n_sats) % 360.0
            line2_k = line2[:43] + f"{ma:8.4f}" + line2[51:]
            sat = Satrec.twoline2rv(line1, line2_k)
            all_windows.extend(
                compute_windows(sat, self.t0, horizon,
                                station_lat, station_lon, min_elev_deg)
            )

        # 单天线并集：排序后合并重叠窗口（同一天线不能同时跟踪两颗星）
        all_windows.sort(key=lambda w: (w.start, w.end))
        merged: list[ContactWindow] = []
        for w in all_windows:
            if merged and w.start <= merged[-1].end:
                merged[-1].end = max(merged[-1].end, w.end)
            else:
                merged.append(ContactWindow(w.start, w.end, capacity))
        self.windows = merged
        if frozen is not None:
            _save_frozen(frozen, n_sats, self.t0.isoformat(), merged)

    def find(self, t: float) -> ContactWindow | None:
        for w in self.windows:
            if w.can_serve(t):
                return w
        return None

    def commit(self, w: ContactWindow, t: float) -> float:
        w.loads += 1
        return max(w.start, t)

    def summary(self) -> str:
        n = len(self.windows)
        total = sum(w.end - w.start for w in self.windows)
        return f"{self.n_sats}星星座 过境窗口 {n} 次/天，累计通信时长 {total/60:.0f} 分钟"
