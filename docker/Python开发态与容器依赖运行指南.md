# Python 开发态与容器依赖运行指南

本文定义本仓库的本地开发运行方式：Python API、任务执行器和前端直接运行源码；MySQL、Redis、MinIO、Elasticsearch 与 BGE-M3 推理服务使用 Docker。该方式适用于 PDF 论文解析、DeepDOC OCR 和前端设置页的日常修改。

## 1. 运行结构

| 组件 | 运行位置 | 地址或说明 |
| --- | --- | --- |
| 前端 | 本机 Vite | `http://127.0.0.1:9222`，支持 HMR |
| Python API | 本机 Python | `http://127.0.0.1:9380` |
| Python worker | 本机 Python | 解析、OCR、向量化异步任务 |
| MySQL、Redis、MinIO、Elasticsearch | Docker Compose | 持久化与检索依赖 |
| BGE-M3 | Docker Compose + GPU | `http://127.0.0.1:6380` |
| DeepDOC OCR | Python 进程 | ONNX Runtime CUDA 执行器，GPU 0 |

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

## 5. 将本机 Python 连接到容器

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

## 6. 启用 DeepDOC GPU OCR

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

启动 worker 后，日志出现 `uses GPU (device 0)` 表示 det、rec、layout 与表格模型已进入 GPU。轻量级的方向识别辅助模型仍可在 CPU 运行。

## 7. 启动开发服务

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

前端通过 Vite 将 `/api` 和 `/v1` 代理到 `127.0.0.1:9380`。修改 `web/src/` 会热更新，不需要重建镜像。

## 8. 健康检查与常见问题

```bash
curl -I http://127.0.0.1:9222
curl -I http://127.0.0.1:9380
nvidia-smi
```

- `CUDAExecutionProvider` 不存在：确认使用的是 `onnxruntime-gpu`、`LD_LIBRARY_PATH` 包含 CUDA wheel 的 `lib` 目录，并检查驱动版本。
- BGE-M3 无法启动：检查 `.cache/models/bge-m3` 是否含模型文件，以及 `docker compose logs bge-m3`。
- API 连不上数据库或 ES：以 `docker compose ... port` 的结果更新 `conf/service_conf.yaml`，不要使用容器内部端口假设。
- 前端接口 404：确认 Vite 以 `API_PROXY_SCHEME=python` 启动，且 Python API 正在监听 9380。
