# 数据来源

本目录保存本地下载或由 DeepDOC 裁出的候选图片，不提交到 Git。运行下面的命令即可取得第一批公开数据：

```bash
export HTTP_PROXY=http://127.0.0.1:7078
export HTTPS_PROXY=http://127.0.0.1:7078
uv run python scripts/download_public_seeds.py
uv run python scripts/build_public_seed.py
uv run python -m visual_classifier import-manifest \
  --input data/manifests/public-seed.jsonl
```

当前公开种子集：

- `equation-handwritten/`：`Azu/Handwritten-Mathematical-Expression-Convert-LaTeX`，下载约 25 MB，含 6,051 张手写公式图。`build_public_seed.py` 从中抽取 300 张、标记为 `equation`。它只用于学习“公式区域”的轮廓和符号密度，不能代替 PDF 中的印刷公式验证。
- `diagrambank/`：`ghzlmc/DiagramBank` 的 ICLR 2017 接收论文子集，下载约 21 MB。`build_public_seed.py` 从中抽取 88 张论文结构/流程图，标记为 `scientific_schematic`。
- `local/`：从你的 PDF/PPT 经 DeepDOC 裁出的候选区域。它们是最终验收数据的主来源，应补齐曲线、器件、截图、表格、Logo、图标和装饰类别。

公开数据的 `label` 是已知来源给出的种子标签。模型评估时必须将真实 PDF/PPT 裁图单独留作验证集，避免公开种子数据与部署场景混在一起。

ACL-Fig 适合补充曲线图、表格与自然图，但 Hugging Face 文件下载需要账户接受其访问条款；登录并取得令牌后再运行 `scripts/download_acl_fig.py`。
