# 企业知识库 RAG

面向城市规划 PDF 文档的检索增强生成（RAG）系统。支持离线建库、跨文档向量检索、重排序与带引用来源的中文问答。

## 功能概览

- **离线建库**：PDF 解析 → 按页规整 → 分块 → 多模态向量化 → FAISS 索引
- **跨文档检索**：自动遍历全部文档索引，合并 Top-K 相关片段
- **重排序**：可选 DashScope TextReRank 精排
- **结构化问答**：返回答案 + 文档名 / 页码 / 引用片段（JSON Schema）
- **Streamlit 界面**：浏览器交互问答
- **CLI**：一键建库、断点续跑、批量评测

## 技术栈

| 环节 | 技术 |
|------|------|
| PDF 解析 | Docling + EasyOCR + TableFormer |
| 页图导出 | PyMuPDF |
| 文本分块 | LangChain + tiktoken |
| 向量模型 | DashScope `qwen2.5-vl-embedding`（1024 维，文本+页图联合 embedding） |
| 向量库 | FAISS（每文档独立 `{sha1}.faiss`） |
| 重排 | DashScope `qwen3-rerank` |
| 问答 LLM | DashScope `qwen-plus` |
| Web UI | Streamlit |
| CLI | Click |

详细规格见 [`spec/SPEC.md`](spec/SPEC.md)。

## 目录结构

```
rag_project/
├── main.py                 # CLI 入口
├── app_streamlit.py        # Streamlit 问答界面
├── scripts/
│   └── generate_subset.py  # 从 PDF 生成 subset.csv
├── src/                    # 核心模块
├── data/项目知识库/         # 运行时数据根目录（CLI 工作目录）
│   ├── subset.csv          # 文档注册表
│   ├── pdf_reports/        # 原始 PDF（本地，不入 Git）
│   ├── debug_data/         # 解析/规整中间产物（本地，不入 Git）
│   └── databases/
│       ├── chunked_reports/  # 分块 JSON
│       └── vector_dbs/       # FAISS 索引（本地，不入 Git）
├── tests/                  # pytest 单元测试（phase1/2/3）
├── spec/SPEC.md            # 系统设计规格
└── requirements.txt
```

## 环境要求

- Python >= 3.10
- Windows / Linux（PDF 解析在 Windows 中文路径下会自动复制到临时 ASCII 目录）
- [阿里云 DashScope API Key](https://help.aliyun.com/zh/model-studio/)（Embedding / Rerank / LLM）
- 首次 Docling 解析需下载本地模型（体积较大，耗时较长）

## 安装

```powershell
cd 01_企业知识库/rag_project

# 创建虚拟环境（推荐）
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install -e .
```

## 配置

复制环境变量模板并填入 API Key：

```powershell
copy env.example .env
# 编辑 .env，设置 DASHSCOPE_API_KEY=sk-xxx
```

## 快速开始

### 1. 准备 PDF

将 PDF 放入 `data/项目知识库/pdf_reports/`（或放在 `data/项目知识库/` 根目录，由脚本自动迁移）。

### 2. 生成文档注册表

```powershell
cd 01_企业知识库/rag_project
python scripts/generate_subset.py
```

输出 `data/项目知识库/subset.csv`（含 doc_id、sha1、标题、区域、文档类型等）。

### 3. 一键离线建库

**须在 `data/项目知识库` 目录下执行 CLI**（`main.py` 以当前目录为数据根）：

```powershell
cd data/项目知识库
python ../../main.py build-all --skip-download
```

流程：解析 PDF → 规整 → 导出页图 → 分块 → 向量化 → 校验索引。

首次运行去掉 `--skip-download`，会先触发 Docling 模型下载：

```powershell
python ../../main.py build-all
```

### 4. 启动问答界面

```powershell
cd 01_企业知识库/rag_project
python -m streamlit run app_streamlit.py
```

浏览器访问 http://localhost:8501 。

## CLI 命令参考

在 `data/项目知识库` 目录下执行：

| 命令 | 说明 |
|------|------|
| `python ../../main.py download-models` | 下载 Docling 模型 |
| `python ../../main.py parse-pdfs` | 仅解析 PDF |
| `python ../../main.py preprocess-reports` | merge + 页图 + 分块（不建库） |
| `python ../../main.py build-index` | 从已有 chunked_reports 建 FAISS |
| `python ../../main.py process-reports` | 预处理 + 建库 |
| `python ../../main.py build-all` | 全流程建库 + 校验 |
| `python ../../main.py resume-build` | 从 merge 完成后断点续跑 |
| `python ../../main.py verify-index` | 校验索引完整性 |
| `python ../../main.py process-questions` | 批量处理 questions.json |

常用参数：

```powershell
# 并行解析（EasyOCR 占内存大，默认 max-workers=1）
python ../../main.py parse-pdfs --max-workers 1

# 跳过已下载的 Docling 模型
python ../../main.py build-all --skip-download
```

## 数据处理流水线

```
pdf_reports/*.pdf
    → subset.csv（generate_subset）
    → 01_parsed_reports（Docling 解析）
    → 02_merged_reports（按页规整）
    → 04_page_images（页级 PNG，供多模态 embedding）
    → chunked_reports（token 分块 + image_paths）
    → vector_dbs（FAISS）
    → Streamlit / process-questions（检索 + 重排 + LLM）
```

## 问答流程

```
用户问题
  → embed_query（纯文本向量）
  → 跨文档 FAISS 检索（Top-20）
  → TextReRank 重排（Top-10，可关闭）
  → Prompt + qwen-plus 生成 JSON 答案
  → 引用页码校验
```

## 测试

在 `rag_project` 根目录：

```powershell
pytest tests/ -v
pytest tests/phase1 -m phase1 -v   # 预处理
pytest tests/phase2 -m phase2 -v   # 建库
pytest tests/phase3 -m phase3 -v   # 问答
```

测试以 mock 为主，不需要真实 PDF 或 API Key（部分用例会 mock DashScope）。

## Git 与本地数据

以下内容**仅保留在本地**，已写入 `.gitignore`，不入库：

- `data/项目知识库/pdf_reports/`（原始 PDF）
- `data/项目知识库/debug_data/`（解析中间产物）
- `data/项目知识库/databases/vector_dbs/`（FAISS 索引）

仓库中保留代码、`subset.csv` 示例、测试 fixture 等。克隆后需自行放入 PDF 并重新建库。

## 常见问题

### 未配置 API Key

Streamlit 或建库时报 `DASHSCOPE_API_KEY` 相关错误：检查 `.env` 是否在 `rag_project` 根目录，且已重启终端/应用。

### 问答提示未建库

确认 `data/项目知识库/databases/vector_dbs/*.faiss` 存在。运行 `python ../../main.py verify-index` 检查。

### Git push 失败（SSL/TLS）

Windows 上 HTTPS 推送 GitHub 可能出现 `schannel: failed to receive handshake`。可尝试：

```powershell
git config --global http.sslBackend openssl
```

或配置代理 / 改用 SSH 远程地址。大文件（PDF）不应提交 Git，见上文「Git 与本地数据」。

### Docling 解析慢或内存不足

- 降低并行度：`parse-pdfs --max-workers 1`
- 使用 `--skip-download` 跳过重复模型下载

## 参考

- 设计规格：[`spec/SPEC.md`](spec/SPEC.md)
- 参考实现：`01_企业知识库/参考/RAG-cy`

## 许可证

个人/企业内部使用项目，具体许可证以仓库根目录说明为准。
