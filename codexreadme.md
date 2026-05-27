固化基线
先把当前 RAG 项目跑稳：确认 start_all.sh、MiMo、ingest、stream chat、非流式 chat、监控都可复现。补齐 rag-api 测试环境，确保 scripts/ci_smoke.sh 能一键跑通。

定义 Agent 数据模型
新增概念，不急着改业务逻辑：agent_runs、agent_steps、agent_tool_calls。每次用户提问对应一个 run，每次模型决策/工具调用/观察结果对应 step。这样后续可观测性先立住。

抽象工具层
先把现有能力包装成工具：
knowledge_search 调 search_in_documents；
get_document_detail 查文档；
list_ready_documents 查知识库；
create_citation_summary 复用 citations。
每个工具都要有 name、description、JSON schema、timeout、权限级别、结果截断策略。

改 LLM service 支持 tool calling
在 service.py (line 148) 增加可选 tools/tool_choice，解析 message.tool_calls。保留现在普通 RAG 调用，新增 agent 调用，避免一次性重写。

新建 Agent Orchestrator
不替换现有 run_chat_for_message，先加并行路径：
AgentOrchestrator.run() 执行 plan -> tool_call -> observation -> final_answer。
初始限制 max_steps=3，只开放只读工具，避免失控。

把 RAG 变成 Agent 的默认工具
第一版 agent 不要做复杂多工具，先让模型能自主决定是否调用 knowledge_search。也就是从“每次必检索”升级为“模型判断需要检索时检索”。

扩展 SSE 事件协议
现有 delta/done/error 保留，新增：
agent_step、tool_call、tool_result、final。
前端先简单显示“正在检索知识库 / 已获得 N 条结果 / 正在生成答案”。

前端增加 Agent Trace 面板
在现有 Reference/Pipeline 面板旁边加“执行步骤”：
第几步、调用工具、输入摘要、输出摘要、耗时、状态。先做只读展示，不做复杂编辑。

加记忆层
短期记忆复用最近 messages；中期把 sessions.summary 用起来，做会话摘要；长期再加 user memory/profile。不要一开始做长期记忆，容易引入脏数据和权限问题。

增加安全边界
   工具按等级分：只读、写入、外部网络、危险操作。第一阶段只开放只读工具。所有工具调用都记录入库，失败也记录，便于回放和审计。

做评测集
   建一个 agent_eval 小集合：普通 RAG 问答、需要多步检索的问题、不需要检索的问题、检索不到的问题、工具失败场景。Agent 改造后不能只看能不能回答，要看是否少调用工具、是否引用正确、是否可追踪。



## 1day
清理之前到老代码，没有用的全部删除掉