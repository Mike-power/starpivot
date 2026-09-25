# -*- coding: utf-8 -*-
"""真实轨道时间线：从公开 TLE 数据计算卫星对地面站的过境窗口。

数据来源：CelesTrak（https://celestrak.org），公开免费，无需注册。
默认使用国际空间站（ISS, NORAD 25544）的 TLE，可替换为任意公开 TLE。

实现说明：只用 sgp4（纯 Python）做轨道传播，自行完成
TEME→ECEF 坐标转换（GMST 近似公式）与仰角计算。
不依赖 de421.bsp 等大型历表文件，国内网络可离线复现。
精度说明：忽略章动/极移，窗口边界误差 < 1 分钟，对 10° 仰角
阈值、分钟级调度的仿真无影响。

与合成时间线（timeline.py）接口一致：find(t) / commit(w, t)。
"""

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sgp4.api import Satrec, jday

from timeline import ContactWindow

DATA_DIR = Path(__file__).parent / "data"

# 上海地面站坐标（公开常识，非敏感信息）
STATION_LAT = 31.2304
STATION_LON = 121.4737
EARTH_R_KM = 6371.0


def _gmst_deg(jd: float, fr: float) -> float:
    """近似格林尼治平恒星时（度），误差 < 1 秒，足够分钟级过境检测。"""
    d = (jd - 2451545.0) + fr
    return (280.46061837 + 360.98564736629 * d) % 360.0


class TleTimeline:
    """基于 TLE 的过境窗口时间线。

    min_elev_deg: 最小仰角，低于此角度的过境视为不可用（默认 10°）
    capacity:     单窗口链路容量（与合成时间线同语义）
    """

    def __init__(
        self,
        tle_path: Path | str = DATA_DIR / "iss.tle",
        station_lat: float = STATION_LAT,
        station_lon: float = STATION_LON,
        min_elev_deg: float = 10.0,
        horizon: float = 86400.0,
        capacity: int = 4,
    ):
        self.capacity = capacity
        self.horizon = horizon

        text = Path(tle_path).read_text(encoding="utf-8").strip().splitlines()
        line1, line2 = text[1].strip(), text[2].strip()
        sat = Satrec.twoline2rv(line1, line2)

        self.t0 = datetime.now(timezone.utc)

        # 测站地心坐标与"天顶"单位向量（球面地球近似）
        phi, lam = math.radians(station_lat), math.radians(station_lon)
        sta = (
            EARTH_R_KM * math.cos(phi) * math.cos(lam),
            EARTH_R_KM * math.cos(phi) * math.sin(lam),
            EARTH_R_KM * math.sin(phi),
        )
        up = (math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi))

        # 每 20 秒采样仰角，检测连续高于阈值的区段作为过境窗口
        step = 20.0
        elevations: list[float] = []
        for i in range(int(horizon / step) + 1):
            t = self.t0 + timedelta(seconds=i * step)
            jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute,
                          t.second + t.microsecond / 1e6)
            err, r, _ = sat.sgp4(jd, fr)
            if err != 0:
                elevations.append(float("-inf"))
                continue
            # TEME → 近似 ECEF：绕 Z 轴旋转 -GMST
            theta = math.radians(_gmst_deg(jd, fr))
            sat_ecef = (
                r[0] * math.cos(theta) + r[1] * math.sin(theta),
                -r[0] * math.sin(theta) + r[1] * math.cos(theta),
                r[2],
            )
            d = tuple(sat_ecef[k] - sta[k] for k in range(3))
            dist = math.sqrt(sum(c * c for c in d))
            sin_elev = sum(d[k] * up[k] for k in range(3)) / dist
            elevations.append(math.degrees(math.asin(max(-1.0, min(1.0, sin_elev)))))

        self.windows: list[ContactWindow] = []
        seg_start = None
        for i, elev in enumerate(elevations):
            t_s = i * step
            if elev >= min_elev_deg and seg_start is None:
                seg_start = t_s
            elif elev < min_elev_deg and seg_start is not None:
                self.windows.append(ContactWindow(seg_start, t_s, capacity))
                seg_start = None
        if seg_start is not None:  # 仿真截断了最后一个窗口
            self.windows.append(ContactWindow(seg_start, horizon, capacity))

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
        return f"TLE 过境窗口 {n} 次/天，累计通信时长 {total/60:.0f} 分钟"
