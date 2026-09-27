# 人工标注目录

`candidates/` 是 DeepDOC 自动裁出的候选图片区。人工确认后，将图片**复制**到下列一个目录；文件名保持不变，便于与 `candidates/manifest.jsonl` 的 `id` 对应。

| 目录 | 放入条件 |
| --- | --- |
| `scientific_plot/` | 曲线图、散点图、柱状图、统计图 |
| `scientific_schematic/` | 模型结构图、算法流程图、电路图 |
| `device_photo/` | 器件、装置、实物照片 |
| `measurement_image/` | 显微图、热图、仿真结果、测试图 |
| `software_screenshot/` | 软件、网页、终端截图 |
| `table/` | 表格或表格截图 |
| `equation/` | 单公式或公式组；不含纯正文中的行内公式 |
| `logo/` | 品牌、机构、会议标志 |
| `ui_icon/` | 图标、按钮、箭头、项目符号 |
| `decorative/` | 背景、分隔线、无信息装饰 |
| `review/` | 暂时无法确定类别或裁图质量差 |

不要重命名或删除 `candidates/` 下的原始文件。其 JSONL 清单会保留 OCR、页码与坐标；人工标注文件应按同一文件名复制到本目录。
