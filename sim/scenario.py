# -*- coding: utf-8 -*-
"""场景生成器：生成一批随机但可复现的任务。"""

import random

from model import Task


def gen_tasks(
    n: int = 100,
    seed: int = 42,
    horizon: float = 86400.0,
    prefix_cfg: dict | None = None,
) -> list[Task]:
    """生成 n 个任务。

    - created_at 均匀分布在仿真周期内
    - duration 30~300 秒（星上/地面处理时间相同，v0.1 简化）
    - complexity 均匀 0~1（决定星上可解性）
    - deadline 模拟紧急度：10% 紧急任务只容忍 1 小时，其余容忍 6 小时
    - prefix_cfg（L2 可选）：{"prefix": 秒, "delta": (min, max)} —— 为每个任务
      生成共享系统提示前缀（prefix_id 全 0，全体共享）与任务增量传输耗时。
      不传则保持 v0.3-v0.7 的 duration 即传输耗时语义。
    """
    rng = random.Random(seed)
    tasks = []
    for i in range(n):
        created = rng.uniform(0, horizon)
        duration = rng.uniform(30, 300)
        complexity = rng.uniform(0, 1)
        patience = 3600 if rng.random() < 0.1 else 21600
        kw = {}
        if prefix_cfg:
            dmin, dmax = prefix_cfg["delta"]
            kw = dict(prefix_id=0,
                      tx_prefix=prefix_cfg["prefix"],
                      tx_delta=rng.uniform(dmin, dmax))
        tasks.append(Task(
            task_id=i,
            created_at=created,
            duration=duration,
            complexity=complexity,
            deadline=created + patience,
            **kw,
        ))
    return tasks
