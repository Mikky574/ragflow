# DeepDOC 候选区域接入契约

这个文件定义未来从 DeepDOC 输出到独立分类工程的数据边界；当前工程不导入 `deepdoc`，也不改 RAGFlow 运行时。

## 输入时机

PDF：`RAGFlowPdfParser._extract_table_figure()` 已将同一版面图片区域裁成单张图后。

PPT：先将一个幻灯片中的相关形状合并为视觉区域；不要把 PPT 包内每个 `media/*` 文件直接送入分类器。

## 必填字段

- `id`：稳定的候选区域 ID。
- `image_path`：裁剪图的可访问路径。
- `source_file`：原始文档文件名或 ID。
- `page`：PDF 页号或 PPT 幻灯片号。
- `bbox`：`[left, top, right, bottom]`。
- `ocr_text`：DeepDOC 已识别到的区域文字，允许为空。

## 输出字段

- `visual_type`：`config/classes.yaml` 中的稳定类别名。
- `visual_score`：最大类别分数。
- `index_action`：`index`、`table`、`skip` 或 `review`。

`review` 不能静默删除原始图片；应记录到文档审计结果中，供人工标注和下一轮训练使用。
