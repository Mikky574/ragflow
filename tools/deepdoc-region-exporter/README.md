# DeepDOC 图片块采集器

独立的数据采集工程：只从目录中的 PDF 裁出 DeepDOC 识别到的 `figure`、`table`、`equation` 区域，生成图片和 JSONL 元数据。它不做向量化、不执行图片分类，也不修改 RAGFlow/DeepDOC 的线上解析路径。

## 目录

- `source_papers/`：输入 PDF；可运行 `download_papers.py` 下载 15 篇公开论文。
- `source_presentations/`：输入 PPTX；可运行 `download_presentations.py` 下载 6 份公开演示文件。
- `candidates/`：自动裁图及 `manifest.jsonl`，每条记录有来源文件、页码、坐标、DeepDOC 版面类型和邻近 OCR 文本。
- `target_data/`：人工标注目标目录。将确认后的候选图片移动到对应类别目录。

所有 PDF、候选图片和人工标注图片均被 Git 忽略；目录结构、脚本和标注规则会提交。

## 下载论文

```bash
cd tools/deepdoc-region-exporter
export HTTP_PROXY=http://127.0.0.1:7078
export HTTPS_PROXY=http://127.0.0.1:7078
uv run python download_papers.py
```

脚本下载 15 篇 arXiv 论文，包含模型图、流程图、实验图、表格和公式密度较高的 PINNs/Neural ODE 论文。下载后会生成 `source_papers/SOURCES.json`，记录来源和 SHA-256。

## 下载演示文件

```bash
cd tools/deepdoc-region-exporter
export HTTP_PROXY=http://127.0.0.1:7078
export HTTPS_PROXY=http://127.0.0.1:7078
uv run python download_presentations.py
```

文件保存到 `source_presentations/`，来源和校验值记录在 `SOURCES.json`。当前采集器只提取 PDF；PPTX 保留为下一阶段的演示文稿裁图原始数据，不会被 `extract_regions.py` 误处理。

## 提取候选图片区

在仓库根目录完成 DeepDOC 模型和 Python 环境部署后执行：

```bash
cd /path/to/ragflow
export PYTHONPATH="$PWD"
export CUDA_VISIBLE_DEVICES=0
export NLTK_DATA="$HOME/nltk_data"

# 首次执行时准备 DeepDOC 分词资源；使用代理时需要显式允许 NLTK 走代理。
NLTK_ALLOW_PROXIED_URLOPEN=1 python -m nltk.downloader -d "$NLTK_DATA" punkt_tab wordnet omw-1.4

uv run python tools/deepdoc-region-exporter/extract_regions.py \
  --input tools/deepdoc-region-exporter/source_papers \
  --output tools/deepdoc-region-exporter/candidates \
  --types figure table equation
```

`CUDA_VISIBLE_DEVICES` 应指向你的 DeepDOC GPU；工具不设置该变量，以免覆盖你的多卡部署。默认 `--zoomin 3`，可提高到 `4` 以保留更细的公式笔画，但速度和显存占用会提高。

如只处理自己的某个目录：

```bash
uv run python tools/deepdoc-region-exporter/extract_regions.py \
  --input /data/my-papers \
  --output tools/deepdoc-region-exporter/candidates
```

## 人工标注

查看 `candidates/manifest.jsonl` 和 `candidates/<论文名>/` 下的图片。将确认图片复制到 [target_data/README.md](target_data/README.md) 中对应目录。`layout_type` 是 DeepDOC 的候选类型，不是最终标签：例如模型图、曲线图常都来自 `figure`，必须人工区分；`equation` 也必须剔除误检的复杂图片。

`target_data/` 的结果才是训练分类模型的实际数据集。建议每个类别先积累至少 100 张真实 PDF/PPT 裁图，并单独留下未参与训练的论文作为验证集。
