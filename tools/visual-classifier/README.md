# Visual classifier

一个独立于 DeepDOC 的图片区域分类工程。它接收 PDF、PPT 或其他文档解析后裁出的图片，结合图片本身和已有 OCR 元数据建立数据集，并输出固定类别、置信度与索引动作。

当前不修改 DeepDOC、不调用生成式大模型，也不直接写入 Elasticsearch。只有分类稳定后，才在 DeepDOC 的图片块入库前调用它。

本地 SQLite 数据库 `data/visual-classifier.sqlite3` 是候选区域、模型预测和人工标签的持久化来源；JSONL 和 CSV 只用于导入、导出和人工审核。

## 分类目标

| 类别 | `index_action` | 用途 |
| --- | --- | --- |
| `scientific_plot` | `index` | 实验曲线、柱状图、散点图 |
| `scientific_schematic` | `index` | 电路图、模型图、架构图、流程图 |
| `device_photo` | `index` | 电子器件、实验装置、实物照片 |
| `measurement_image` | `index` | 显微图、热图、仿真图、测试结果 |
| `software_screenshot` | `index` | 软件、网页、终端截图 |
| `table` | `table` | 交给表格处理路径 |
| `equation` | `index` | 公式或公式组图，保留 OCR、位置和检索能力 |
| `logo` | `skip` | 机构、品牌和会议标志 |
| `ui_icon` | `skip` | PPT 图标、按钮、箭头、项目符号 |
| `decorative` | `skip` | 背景、纹理、分隔线和页角装饰 |

类别和提示词位于 [config/classes.yaml](config/classes.yaml)。类别标识一旦进入人工标注数据，不应改名；可以添加或改进提示词。

## 模型

默认模型是 `google/siglip2-base-patch16-224`。这是 Apache-2.0 的小型 SigLIP2 零样本图像分类模型，可在单张 GPU 或 CPU 上运行；不生成图片描述。初期使用它建立基线，积累本地标注数据后再训练轻量分类头。

模型和 Hugging Face 缓存应放在工程外或 `models/`，后者已被 Git 忽略。离线部署时，在可联网机器下载模型目录后复制到 Linux，并将 `--model` 指向本地目录。

## 安装

建议单独建立环境，避免影响 RAGFlow 的 Python 依赖：

```bash
cd tools/visual-classifier
uv sync --python 3.10
uv run python -c "import torch; print(torch.cuda.is_available())"
```

GPU 环境需要安装与 CUDA 驱动匹配的 PyTorch。上面的命令必须输出 `True` 后再使用 `--device cuda:0`。

## 数据集流程

1. 将待分类的候选区域放入 `data/images/`，按来源文件分目录，例如 `data/images/paper-a/page-03-figure-01.png`。
2. 生成候选清单：

```bash
uv run python -m visual_classifier create-manifest \
  --images data/images \
  --output data/manifests/candidates.jsonl
```

3. 写入本地数据集库：

```bash
uv run python -m visual_classifier import-manifest \
  --input data/manifests/candidates.jsonl
```

后续可随时导出数据库内容：

```bash
uv run python -m visual_classifier export-dataset \
  --output data/manifests/candidates-from-db.jsonl
```

4. 用小模型生成预测：

```bash
uv run python -m visual_classifier predict \
  --input data/manifests/candidates.jsonl \
  --output data/predictions/baseline.jsonl \
  --device cuda:0

uv run python -m visual_classifier import-manifest \
  --input data/predictions/baseline.jsonl
```

5. 导出人工复核表：

```bash
uv run python -m visual_classifier export-review \
  --input data/predictions/baseline.jsonl \
  --output data/reviews/baseline.csv
```

在 CSV 的 `label` 列填写最终类别。低于默认阈值 `0.55` 的样本会标为 `review`，不会自动进入或排除检索。

6. 将填写好的 CSV 导回 JSONL，再评测：

```bash
uv run python -m visual_classifier import-review \
  --input data/predictions/baseline.jsonl \
  --review data/reviews/baseline.csv \
  --output data/predictions/labelled-baseline.jsonl

uv run python -m visual_classifier import-manifest \
  --input data/predictions/labelled-baseline.jsonl

uv run python -m visual_classifier evaluate \
  --input data/predictions/labelled-baseline.jsonl
```

## 候选区域清单契约

每行 JSONL 是一个候选区域：

```json
{
  "id": "paper-a__page-03__figure-01",
  "image_path": "/absolute/path/page-03-figure-01.png",
  "source_file": "paper-a.pdf",
  "page": 3,
  "bbox": [86.0, 212.0, 514.0, 606.0],
  "ocr_text": "Fig. 2. Gain curve\\nEfficiency [%]",
  "label": ""
}
```

`bbox` 和 `ocr_text` 在当前零样本分类阶段不参与模型推理，但必须保留；人工审计、重复图片去重和后续融合 OCR/版面特征都会使用它们。

## 与 DeepDOC 的未来接入点

待独立评测通过后，在 `deepdoc/parser/pdf_parser.py` 的 `_extract_table_figure()` 中，图片裁剪完成、`tokenize_table()` 写入图片块之前调用分类器。届时只让 `index` 类别生成普通图片块；`table` 进入表格处理；`skip` 和 `review` 只保存位置与审计记录。

不要在 DeepDOC 的原始图片对象层调用分类器。必须先由版面解析合并为候选视觉区域，否则一个 PPT 的 Logo、箭头和多个形状会变成大量独立噪声样本。

## 当前验收目标

第一轮先从你的论文和 PPT 中标注 300 张候选区域，至少覆盖每个类别 20 张。重点不是追求总准确率，而是保证：

- `equation`、`scientific_plot`、`scientific_schematic` 的召回率高；
- `logo`、`ui_icon`、`decorative` 不进入默认检索；
- 低置信度图片进入人工复核，而不是被错误删除。
