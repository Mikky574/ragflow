# Python 开发态与容器依赖运行指南

本文定义本仓库的本地开发运行方式：Python API、任务执行器和前端直接运行源码；MySQL、Redis、MinIO、Elasticsearch 与 BGE-M3 推理服务使用 Docker。该方式适用于 PDF 论文解析、DeepDOC OCR 和前端设置页的日常修改。

## 1. 运行结构

| 组件 | 运行位置 | 地址或说明 |
| --- | --- | --- |
| 前端 | 本机 Vite | `http://127.0.0.1:9222`，支持 HMR |
| Python API | 本机 Python | `http://127.0.0.1:9380` |
| Python worker | 本机 Python | 解析、OCR、向量化异步任务 |
| MySQL、Redis、MinIO、Elasticsearch | Docker Compose | 持久化与检索依赖 |
| BGE-M3 | 每张 GPU 一个 TEI 容器 + Nginx | `http://127.0.0.1:6380` |
| DeepDOC OCR | Python worker | ONNX Runtime 按页分发到多张 GPU |

`docker/docker-compose-python-dev.yml` 只声明 BGE-M3，不包含前端、Python API 或 worker。

## 2. 前置条件

- Docker Desktop（Windows 下启用 WSL2 backend）与 Docker Compose v2。
- Node.js 22、npm、Python 3.13、[uv](https://docs.astral.sh/uv/)。Python 3.13 使用本仓库的 NumPy 2.x 约束；若本机依赖无法安装，可使用 Python 3.10 创建隔离环境。
- 使用 GPU 时安装 NVIDIA 驱动；以下命令必须能看到 GPU：

  ```bash
  nvidia-smi
  docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
  ```

- 如需代理，统一使用：

  ```bash
  export HTTP_PROXY=http://127.0.0.1:7078
  export HTTPS_PROXY=http://127.0.0.1:7078
  export NO_PROXY=localhost,127.0.0.1,::1
  ```

  PowerShell 等价写法为 `$env:HTTP_PROXY='http://127.0.0.1:7078'`、`$env:HTTPS_PROXY='http://127.0.0.1:7078'`。WSL 必须能够访问该地址；若 WSL 未启用 mirrored networking，请改为 Windows 主机在 WSL 中可达的 IP。

## 3. 安装 Python 与前端依赖

在仓库根目录执行：

```bash
uv sync --python 3.13 --all-extras
uv run python ragflow_deps/download_deps.py
cd web
npm ci
cd ..
```

`download_deps.py` 下载 DeepDOC 所需的两组 Hugging Face 资源：

- `InfiniFlow/deepdoc`：文字检测、识别、布局和表格结构 ONNX 模型；
- `InfiniFlow/text_concat_xgb_v1.0`：文本拼接模型。

脚本也下载 NLTK 数据、tokenizer 和构建依赖。网络受限时可设置 `HF_ENDPOINT=https://hf-mirror.com`，也可保留上面的 HTTP/HTTPS 代理。

## 4. 下载 BGE-M3 并启动容器依赖

BGE-M3 来源为 Hugging Face 的 `BAAI/bge-m3`。先下载到本地挂载目录：

```bash
uv run python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='BAAI/bge-m3', local_dir='.cache/models/bge-m3')"
```

然后启动基础依赖和 GPU BGE-M3 服务：

```bash
docker compose \
  -f docker/docker-compose-base.yml \
  -f docker/docker-compose-python-dev.yml \
  --profile elasticsearch \
  --profile mysql \
  up -d
```

检查服务：

```bash
docker compose -f docker/docker-compose-base.yml -f docker/docker-compose-python-dev.yml ps
curl http://127.0.0.1:6380/health
```

模型服务启动后，在 RAGFlow 的模型配置中添加 embedding 模型：模型名 `BAAI/bge-m3`，服务地址 `http://127.0.0.1:6380`。BGE-M3 的向量维度是 1024。

### BGE-M3 多卡数据并行

`docker-compose-python-dev.yml` 默认使用两张卡：`bge-m3-gpu0` 与 `bge-m3-gpu1` 各加载一份 BGE-M3，`bge-m3-router` 在 `6380` 提供唯一入口并按连接数转发请求。这样扩展的是吞吐量，不是将一个 BGE-M3 模型切分到多张卡；BGE-M3 单卡可容纳，副本方式能避免单个请求的跨卡通信开销。

```bash
curl http://127.0.0.1:6380/health
nvidia-smi
```

应看到两张 GPU 均有一个 TEI 进程。三张或更多 GPU 时，复制 `bge-m3-gpu1` 服务为 `bge-m3-gpu2`、`bge-m3-gpu3`，把 `device_ids` 改为对应卡号，并在 `docker/nginx/bge-m3-router.conf` 的 `upstream bge_m3_pool` 中添加对应服务。默认 embedding 地址为 `http://127.0.0.1:6380`；改端口或跨主机部署时，按下一节更新该地址。

## 5. 端口冲突与分离部署

所有宿主机端口都可以改，容器内端口保持不变。以下是一个前端、API、BGE-M3 都避开默认端口的示例：

| 服务 | 默认宿主机端口 | 自定义示例 | 配置位置 |
| --- | --- | --- | --- |
| 前端 Vite | 9222 | 9223 | 启动时的 `PORT` |
| Python API | 9380 | 19380 | `conf/service_conf.yaml` 的 `ragflow.http_port` |
| BGE-M3 路由 | 6380 | 16380 | `BGE_M3_PORT` |
| Elasticsearch | 1200 | 11200 | `docker/.env` 的 `ES_PORT` |
| MySQL | 由 `EXPOSE_MYSQL_PORT` 决定 | 13306 | `docker/.env` 的 `EXPOSE_MYSQL_PORT` |
| MinIO / Redis | 9000 / 6379 | 19000 / 16379 | `docker/.env` 的 `MINIO_PORT` / `REDIS_PORT` |

例如把 BGE-M3 放到本机 `16380`：

```bash
export BGE_M3_PORT=16380
docker compose -f docker/docker-compose-base.yml -f docker/docker-compose-python-dev.yml up -d bge-m3-gpu0 bge-m3-gpu1 bge-m3-router
curl http://127.0.0.1:16380/health
```

然后把 `conf/service_conf.yaml` 中 embedding 的 `base_url` 改为 `http://127.0.0.1:16380`。若是在页面中添加模型，也填写这个地址；不要填写 TEI 容器名或容器内部端口。

Python API 改到 `19380` 时，更新 `conf/service_conf.yaml`：

```yaml
ragflow:
  host: 0.0.0.0
  http_port: 19380
```

前端必须同时知道新的 API 端口：

```bash
cd web
PORT=9223 PYTHON_API_PORT=19380 npm run dev
```

Vite 会监听 `9223`，并将 `/api`、`/v1` 转发至 `127.0.0.1:19380`。因此浏览器只访问 `http://127.0.0.1:9223`，不需要在前端代码中写死 API 地址。

### BGE-M3 部署在另一台机器

若 BGE-M3 与 RAGFlow 不在同一台机器，模型服务器的 Compose 启动前设置公开绑定地址，并用防火墙限制只允许 RAGFlow 主机访问：

```bash
export BGE_M3_BIND_ADDRESS=0.0.0.0
export BGE_M3_PORT=16380
docker compose -f docker/docker-compose-base.yml -f docker/docker-compose-python-dev.yml up -d bge-m3-gpu0 bge-m3-gpu1 bge-m3-router
```

RAGFlow 主机的 `conf/service_conf.yaml` 或模型配置页面填写 `http://<BGE-M3服务器IP>:16380`。模型服务地址变更后，需要重启 Python API 和 worker；只改前端端口只需重启 Vite。
## 6. 将本机 Python 连接到容器

本机 Python 不能使用 Docker 内部 DNS 名称（如 `mysql`、`es01`）。编辑 `conf/service_conf.yaml`，将其指向 Docker 暴露到本机的端口。端口必须以实际 Compose 输出为准：

```bash
docker compose -f docker/docker-compose-base.yml -f docker/docker-compose-python-dev.yml port mysql 3306
docker compose -f docker/docker-compose-base.yml -f docker/docker-compose-python-dev.yml port es01 9200
docker compose -f docker/docker-compose-base.yml -f docker/docker-compose-python-dev.yml port minio 9000
docker compose -f docker/docker-compose-base.yml -f docker/docker-compose-python-dev.yml port redis 6379
```

典型配置如下；端口与上面的命令输出不同就替换为实际值：

```yaml
mysql:
  host: 'localhost'
  port: 3306
minio:
  host: 'localhost:9000'
es:
  hosts: 'http://localhost:1200'
redis:
  host: 'localhost:6379'
user_default_llm:
  default_models:
    embedding_model:
      name: 'BAAI/bge-m3'
      base_url: 'http://localhost:6380'
```

不要提交包含密码、密钥或本机端口差异的 `conf/service_conf.yaml`。将该文件保留为本机配置即可。

## 7. 启用 DeepDOC GPU OCR

DeepDOC 的 Python 路径使用 ONNX Runtime。保持 `DEVICE=cpu`，只设置 `OCR_DEVICE=gpu`，这样不会因通用 PyTorch 路径而额外安装大型 torch 包：

```bash
export DEVICE=cpu
export OCR_DEVICE=gpu
```

在 CUDA 12 环境中安装 ONNX Runtime GPU 及其 CUDA 动态库：

```bash
uv pip install --python .venv/bin/python \
  onnxruntime-gpu nvidia-cublas-cu12 nvidia-cudnn-cu12 \
  nvidia-curand-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-nvrtc-cu12 \
  nvidia-cufft-cu12 nvidia-cusolver-cu12 nvidia-cusparse-cu12 nvidia-nvjitlink-cu12
```

将这些 wheel 内的库加入加载路径：

```bash
export LD_LIBRARY_PATH="$(python - <<'PY'
import site
from pathlib import Path
root = Path(site.getsitepackages()[0]) / 'nvidia'
print(':'.join(str(root / name / 'lib') for name in ('cublas', 'cudnn', 'curand', 'cuda_runtime', 'cuda_nvrtc', 'cufft', 'cusolver', 'cusparse', 'nvjitlink')))
PY
):${LD_LIBRARY_PATH:-}"
python -c "import onnxruntime as ort; assert 'CUDAExecutionProvider' in ort.get_available_providers(); print(ort.get_available_providers())"
```

启动 worker 后，日志出现 `uses GPU (device 0)` 表示 det、rec、layout 与表格模型已进入 GPU。

### DeepDOC 多卡并行

设置 `OCR_PARALLEL_DEVICES` 为用于 OCR 的卡数。例如两张卡：

```bash
export DEVICE=cpu
export OCR_DEVICE=gpu
export OCR_PARALLEL_DEVICES=2
export OCR_GPU_MEM_LIMIT_MB=2048
```

单个 worker 会为每张卡建立一套 det/rec 会话，并把同一 PDF 的页面按 `页号 % OCR_PARALLEL_DEVICES` 分配。此模式适合大 PDF，启动时使用 `WS=1`：

```bash
WS=1 bash docker/launch_backend_service.sh
```

若主要并行多个独立文档，改用每卡一个 worker：每个进程设置不同的 `CUDA_VISIBLE_DEVICES`，且都设置 `OCR_PARALLEL_DEVICES=1`。不要同时设置 `WS>1` 和 `OCR_PARALLEL_DEVICES>1`，否则每个 worker 都会在全部 GPU 加载模型，显存会重复占用。

```bash
CUDA_VISIBLE_DEVICES=0 OCR_DEVICE=gpu OCR_PARALLEL_DEVICES=1 python rag/svr/task_executor.py -i ocr_gpu0 -t common
CUDA_VISIBLE_DEVICES=1 OCR_DEVICE=gpu OCR_PARALLEL_DEVICES=1 python rag/svr/task_executor.py -i ocr_gpu1 -t common
```

`nvidia-smi` 应显示每张参与 OCR 的卡均有 Python worker，日志中会出现 `uses GPU (device 0)` 和 `uses GPU (device 1)`。方向识别辅助模型仍可在 CPU 运行。

## 8. 启动开发服务

在一个终端启动 Python API 与 worker：

```bash
source .venv/bin/activate
export PYTHONPATH="$PWD"
export API_PROXY_SCHEME=python
export DOC_ENGINE=elasticsearch
export DB_TYPE=mysql
bash docker/launch_backend_service.sh
```

在第二个终端启动前端：

```bash
cd web
npm run dev -- --port 9222
```

前端通过 Vite 将 `/api` 和 `/v1` 代理到 `PYTHON_API_PORT`（默认 `127.0.0.1:9380`）。修改 `web/src/` 会热更新，不需要重建镜像。

## 9. 健康检查与常见问题

```bash
curl -I http://127.0.0.1:9222
curl -I http://127.0.0.1:9380
nvidia-smi
```

- `CUDAExecutionProvider` 不存在：确认使用的是 `onnxruntime-gpu`、`LD_LIBRARY_PATH` 包含 CUDA wheel 的 `lib` 目录，并检查驱动版本。
- BGE-M3 无法启动：检查 `.cache/models/bge-m3` 是否含模型文件，以及 `docker compose logs bge-m3-gpu0 bge-m3-gpu1 bge-m3-router`。
- API 连不上数据库或 ES：以 `docker compose ... port` 的结果更新 `conf/service_conf.yaml`，不要使用容器内部端口假设。
- 前端接口 404：确认 Vite 以 `API_PROXY_SCHEME=python` 启动，且 Python API 正在监听 9380。
