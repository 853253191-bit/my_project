"""
企业知识库 RAG Streamlit 问答 Web 界面（app_streamlit.py）

主要功能：
- 提供浏览器问答界面：输入问题、调节 Top-K 与重排开关、展示答案与引用来源
- 读取 data/项目知识库 下已建好的 FAISS 向量库，调用 DashScope 完成检索与生成

如何调用（须在 rag_project 根目录，且用 streamlit run，不可 python 直接运行）：
  cd 01_企业知识库/rag_project
  python -m streamlit run app_streamlit.py
  # 浏览器打开 http://localhost:8501

前置条件：
- 已配置环境变量 DASHSCOPE_API_KEY（可在 .env 中设置）
- 已完成离线建库（databases/vector_dbs/*.faiss 存在）
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.config import NOT_FOUND_ANSWER, enterprise_config
from src.pipeline import Pipeline

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data" / "项目知识库"


@st.cache_resource
def get_pipeline() -> Pipeline:
    return Pipeline(root_path=DATA_ROOT, run_config=enterprise_config())


def check_api_key() -> bool:
    return bool(os.getenv("DASHSCOPE_API_KEY"))


def check_index_status(pipeline: Pipeline) -> tuple[int, int]:
    return pipeline.count_indexed_documents()


st.set_page_config(page_title="企业知识库 RAG", layout="wide")

st.markdown(
    """
<div style='background: linear-gradient(90deg, #1a5276 0%, #2e86c1 100%);
padding: 20px 0; border-radius: 12px; text-align: center;'>
<h2 style='color: white; margin: 0;'>企业知识库 RAG 问答系统</h2>
<div style='color: #ecf0f1; font-size: 15px; margin-top: 8px;'>
qwen2.5-vl-embedding + bge-reranker + 通义千问 | 跨文档检索 | 规划文档知识库
</div>
</div>
""",
    unsafe_allow_html=True,
)

pipeline = get_pipeline()
indexed, total = check_index_status(pipeline)

with st.sidebar:
    st.header("查询设置")
    user_question = st.text_area(
        "输入问题",
        placeholder="例如：D06 单元控规调整涉及哪些用地性质变更？",
        height=100,
    )
    top_k = st.slider("Top-K 检索", 5, 20, pipeline.run_config.top_n_retrieval)
    use_rerank = st.checkbox(
        "启用 bge-reranker 重排",
        value=pipeline.run_config.use_reranking,
    )
    submit_btn = st.button("提问", use_container_width=True, disabled=not user_question.strip())

    st.divider()
    st.subheader("知识库状态")
    if total == 0:
        st.warning("未找到 subset.csv，请先运行 generate_subset.py")
    elif indexed == 0:
        st.error("向量库未建立")
        st.code(
            "cd data/项目知识库\n"
            "python ../../main.py process-reports",
            language="powershell",
        )
    elif indexed < total:
        st.warning(f"已索引 {indexed}/{total} 份文档")
    else:
        st.success(f"已索引 {indexed}/{total} 份文档")

    if not check_api_key():
        st.error("未配置 DASHSCOPE_API_KEY")

if not check_api_key():
    st.error("未配置 DASHSCOPE_API_KEY，请在 .env 中设置后重启应用。")
elif indexed == 0:
    st.info("请先完成离线建库，再使用问答功能。命令见左侧知识库状态。")
elif submit_btn and user_question.strip():
    pipeline.run_config.top_n_retrieval = top_k
    pipeline.run_config.use_reranking = use_rerank
    with st.spinner("正在检索并生成答案..."):
        try:
            answer = pipeline.answer_single_question(user_question.strip())
            final_answer = answer.get("final_answer", "")
            references = answer.get("references", [])

            st.markdown("## 最终答案")
            if final_answer == NOT_FOUND_ANSWER:
                st.warning(final_answer)
            else:
                st.markdown(
                    f"<div style='background:#f0f7fb;padding:16px;border-radius:8px;"
                    f"font-size:17px;line-height:1.6;'>{final_answer}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("## 引用来源")
            if references:
                st.table([
                    {
                        "文档": ref.get("doc_title", ""),
                        "doc_id": ref.get("doc_id", ""),
                        "页码": ref.get("page", ""),
                        "摘要": ref.get("excerpt", ""),
                    }
                    for ref in references
                ])
            else:
                st.write("无引用")

            with st.expander("推理过程"):
                st.markdown("**逐步分析**")
                st.info(answer.get("step_by_step_analysis", "-"))
                st.markdown("**推理摘要**")
                st.success(answer.get("reasoning_summary", "-"))

            debug = answer.get("retrieval_debug", [])
            if debug:
                with st.expander("检索片段（Debug）"):
                    for i, chunk in enumerate(debug, 1):
                        score = chunk.get("rerank_score", chunk.get("score", ""))
                        score_text = f" (score={score:.3f})" if isinstance(score, (int, float)) else ""
                        st.markdown(
                            f"**[{i}] {chunk.get('doc_title')} "
                            f"第{chunk.get('page')}页**{score_text}"
                        )
                        st.text(chunk.get("text", "")[:500])
        except RuntimeError as e:
            if "API" in str(e) or "限流" in str(e):
                st.error("API 调用频率超限，请稍后重试")
            else:
                st.error(f"生成答案时出错: {e}")
        except Exception as e:
            st.error(f"生成答案时出错: {e}")
else:
    st.info("请在左侧输入问题并点击「提问」")
