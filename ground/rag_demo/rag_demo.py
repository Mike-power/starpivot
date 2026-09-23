# -*- coding: utf-8 -*-
"""
最小 RAG demo —— 星枢 ground/rag_demo
链路：加载文档 → 切分 → 本地 embedding 向量化 → FAISS 检索 → 千问生成

运行前：
    pip install -r requirements.txt
    cp .env.example .env   # 填入 DASHSCOPE_API_KEY

首次运行会向量化 data/sample_doc.txt 并保存到 faiss_index/；
之后启动直接加载索引，秒开。
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()  # 读取 .env 里的 DASHSCOPE_API_KEY

if not os.environ.get("DASHSCOPE_API_KEY"):
    sys.exit("未找到 DASHSCOPE_API_KEY，请先 cp .env.example .env 并填入 key")

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_doc.txt")
INDEX_DIR = os.path.join(os.path.dirname(__file__), "faiss_index")

# ---------------------------------------------------------------------------
# 1. Embedding：本地中文模型，零 API 成本
#    首次运行自动下载（约 100MB）；BGE 模型对中文检索友好
# ---------------------------------------------------------------------------
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    encode_kwargs={"normalize_embeddings": True},
)

# ---------------------------------------------------------------------------
# 2. 向量库：有索引就直接加载；没有就 加载 → 切分 → 向量化 → 保存
# ---------------------------------------------------------------------------
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

if os.path.isdir(INDEX_DIR):
    vector_store = FAISS.load_local(
        INDEX_DIR, embeddings, allow_dangerous_deserialization=True
    )
    print("已加载本地索引 faiss_index/（跳过向量化）")
else:
    docs = TextLoader(DATA_PATH, encoding="utf-8").load()
    # 中文文档：块 500 字、重叠 100 字（经验值，详见学习指南 2.2 节）
    splits = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=100
    ).split_documents(docs)
    print(f"文档切分为 {len(splits)} 块，开始向量化（首次需下载模型，请耐心等待）...")
    vector_store = FAISS.from_documents(splits, embeddings)
    vector_store.save_local(INDEX_DIR)
    print(f"向量化完成，索引已保存到 faiss_index/")

retriever = vector_store.as_retriever(search_kwargs={"k": 3})

# ---------------------------------------------------------------------------
# 3. 大模型：千问（阿里云百炼，OpenAI 兼容接口）
# ---------------------------------------------------------------------------
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="qwen-plus",
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0,
)

# ---------------------------------------------------------------------------
# 4. RAG 链：检索 → 填模板 → 生成 → 解析
# ---------------------------------------------------------------------------
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

prompt = ChatPromptTemplate.from_template(
    "你是资料问答助手。请严格根据下面的资料回答问题。\n"
    '如果资料中没有答案，请直接说"资料中未提及"，不要编造。\n\n'
    "资料：\n{context}\n\n问题：{question}"
)


def format_docs(docs):
    """把检索到的块拼成一段上下文，并标注来源。"""
    parts = []
    for i, d in enumerate(docs, start=1):
        parts.append(f"[资料{i}] {d.page_content}")
    return "\n\n".join(parts)


rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# ---------------------------------------------------------------------------
# 5. 提问循环
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n星枢 RAG demo 已就绪。试试：星上侧部署在什么硬件上？ / 专利主点是什么？")
    print("输入 q 退出。\n")
    while True:
        question = input("提问：").strip()
        if question.lower() == "q":
            break
        if not question:
            continue
        print(f"\n回答：{rag_chain.invoke(question)}\n")
