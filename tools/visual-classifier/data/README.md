# 数据来源

本目录保存本地下载或由 DeepDOC 裁出的候选图片，不提交到 Git。运行下面的命令即可取得真实论文 PDF：

```bash
export HTTP_PROXY=http://127.0.0.1:7078
export HTTPS_PROXY=http://127.0.0.1:7078
uv run python scripts/download_reference_papers.py
```

`papers/` 包含 Attention、ResNet 和 PINNs 三篇公开论文。公式、公式组、模型图、实验图和表格均应在后续由 DeepDOC 裁出，并保存 `source_file`、页码、位置和 OCR 文字后导入 SQLite。

当前可选的公开辅助种子集：

- `diagrambank/`：`ghzlmc/DiagramBank` 的 ICLR 2017 接收论文子集，下载约 21 MB。`build_public_seed.py` 从中抽取 88 张论文结构/流程图，标记为 `scientific_schematic`。
- `local/`：从你的 PDF/PPT 经 DeepDOC 裁出的候选区域。它们是最终验收数据的主来源，应补齐曲线、器件、截图、表格、Logo、图标和装饰类别。

公开结构图的 `label` 是来源给出的种子标签。模型评估时必须将真实 PDF/PPT 裁图单独留作验证集，避免公开种子数据与部署场景混在一起。

ACL-Fig 适合补充曲线图、表格与自然图，但 Hugging Face 文件下载需要账户接受其访问条款；登录并取得令牌后再运行 `scripts/download_acl_fig.py`。
