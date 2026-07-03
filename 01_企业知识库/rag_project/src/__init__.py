# 企业知识库 RAG 业务代码包（src/）
#
# 主要功能：离线建库（PDF 解析 → 分块 → FAISS）与在线问答（检索 → 重排 → LLM）的核心模块集合。
# 如何调用：由 main.py、app_streamlit.py、scripts/generate_subset.py 导入；一般不直接运行本包。
# 入口模块：pipeline.py（流水线编排）、config.py（配置常量）。
