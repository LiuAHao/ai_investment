## RAG 实现说明（当前项目）

本文档用于说明当前项目内 RAG 的实际实现、数据流程与调用方式。

---

## 1. 目录结构
RAG 相关目录位于 src/rag，核心结构如下：

- data/raw：原始知识材料（.md/.txt）
- data/clean：清洗后的文本
- data/chunks：切分后的知识块（chunks.jsonl）
- index/chroma：Chroma 向量库持久化目录
- config：RAG 配置文件
- scripts：构建与检索脚本

---

## 2. 核心配置
配置文件：src/rag/config/rag_config.json

关键字段说明：
- data：输入与输出目录
- chunking：切分参数（最大/最小长度、重叠）
- embedding：嵌入模型名称
- chroma：向量库配置（持久化目录、集合名）
- hybrid：混合检索参数（向量/关键词召回规模、RRF 融合参数）
- rerank：重排模型及返回数量
- fallback：兜底阈值（最低命中数量、最低置信度）

---

## 3. 数据处理流程
流程分为 4 步：

1) 原始文档收集
- 将资料放入 data/raw，支持 .md 与 .txt

2) 清洗与切分
- 使用脚本 scripts/prepare_chunks.py
- 规则：按 Markdown 标题切分，长度 200-800 字为主
- 输出：data/chunks/chunks.jsonl

3) 向量化入库（Chroma）
- 使用脚本 scripts/build_chroma_index.py
- 通过 SentenceTransformer 生成向量
- 持久化存储至 index/chroma

4) 检索与重排
- 使用 scripts/query_chroma.py 进行检索验证
- 生产调用由 query_investment_knowledge 统一封装

---

## 4. 检索逻辑（混合检索）
当前检索为“向量 + 关键词”混合策略：

1) 向量召回
- 将用户问题转为向量
- Chroma 返回 top_k 个最相近知识块

2) 关键词召回
- 对 query 进行简单分词与频次统计
- 在 chunks.jsonl 中进行关键词匹配

3) 结果融合
- 使用 RRF（Reciprocal Rank Fusion）融合向量与关键词结果
- 输出融合后的 top_k

4) 重排（可选）
- 如配置启用，使用 CrossEncoder 对候选结果重排

---

## 5. 兜底机制
如果检索结果不足或得分过低，则触发兜底：
- 返回 fallback=true
- message 提示“知识库覆盖不足”
- Agent 不应编造内容

---

## 6. 工具函数封装
知识库统一入口：
- src/rag/knowledge_tool.py
- 对外暴露 query_investment_knowledge

返回结构包含：
- query：用户问题
- results：知识块列表
- citations：引用信息（title + source）
- fallback：是否兜底
- message：兜底提示

---

## 7. Agent 调用接入
主控 Agent 已注册工具：
- query_investment_knowledge

由 DecisionAgent 在工具选择阶段调用，结果参与最终总结。

---

## 8. 使用步骤（最短路径）
1) 将知识材料放入 data/raw
2) 运行 prepare_chunks.py 生成 chunks
3) 运行 build_chroma_index.py 构建向量索引
4) 在 Agent 中自动调用 query_investment_knowledge

---

## 9. 已引入依赖
- chromadb
- sentence-transformers

---

## 10. 约束与注意事项
- 知识内容需合法合规，建议保留来源
- 低置信度时必须触发兜底
- 知识库仅用于辅助分析，不直接输出买卖指令

