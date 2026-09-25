# 最小 RAG demo（阶段 0 周末任务）

跑通"文档 → 切分 → 向量化 → 检索 → 千问生成"完整链路。对应看板任务 **p0-t3**。

## 运行步骤

### 1. 准备环境（约 5 分钟）

```bash
cd ground/rag_demo
python3 -m venv .venv
source .venv/bin/activate          # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置 API Key（约 2 分钟）

在[阿里云百炼平台](https://bailian.console.aliyun.com/)申请 `DASHSCOPE_API_KEY`（新用户有免费额度），然后：

```bash
cp .env.example .env
# 用编辑器打开 .env，把 sk-xxx 换成你的真实 key
```

### 3. 运行

```bash
python rag_demo.py
```

首次运行会自动下载中文 embedding 模型（BAAI/bge-small-zh-v1.5，约 100MB，需联网一次），
然后向量化示例文档并保存在 `faiss_index/`（已 gitignore，不入库）。

之后进入提问循环，试试这些问题（答案都在示例文档里）：

- 星枢系统的星上侧部署在什么硬件上？
- 通信受限时谁来负责复杂规划？
- 项目的专利主点是什么？

输入 `q` 退出。**第二次启动会秒开**（直接加载已有索引，不再重复向量化）。

## 常见问题

| 现象 | 原因与解决 |
|------|-----------|
| 首次运行卡在下载模型 | 正常，bge 模型约 100MB；若网络太慢，换手机热点或次日再试 |
| `DASHSCOPE_API_KEY` 报错 | `.env` 没建或 key 没填对，检查第一步 |
| 回答"资料中未提及" | 正常——这是防幻觉设计；换个文档里有的问题 |
| pip 安装 faiss-cpu 失败 | Mac M 系列正常；如是异常，改 `faiss-cpu` 为 `faiss`，或留言给我 |

## 验收标准

能对示例文档连续问 3 个问题且回答准确、标注来源，即为跑通——到看板勾掉 p0-t3，并把这段代码 push（绿点 +1）。

## 验收记录

**2026.9.25 已跑通**（LeetCode 同款账号提交，三问全部通过）：星上侧硬件（Jetson Orin）、
复杂规划归属（地面侧，模型还辨析了"通信受限 ≠ 通信中断"）、专利主点（通信窗口感知的
星地分层推理调度方法）——答案均准确并标注资料来源。

踩坑备忘（国内网络）：pip 依赖走阿里云镜像 `-i https://mirrors.aliyun.com/pypi/simple/`；
bge 模型走 `HF_ENDPOINT=https://hf-mirror.com`；`.env` 已验证被 gitignore。
