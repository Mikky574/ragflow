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

- Linux x86_64、glibc >= 2.27、Docker Engine 与 Docker Compose v2。当前验证在 WSL2 Linux 发行版完成；正式部署直接使用 Linux 主机，不依赖 Windows 或 Docker Desktop。glibc 2.27 可使用当前 Python GPU OCR wheel；Go native build 仍要求其专用 glibc 2.28 构建环境。
- Node.js 22、npm、Python 3.13、[uv](https://docs.astral.sh/uv/)。本仓库的 `requires-python` 与 `uv.lock` 均固定 Python 3.13；Python 3.10 不能直接运行当前开发态，必须另行维护依赖解析与锁定文件。
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

  Linux shell 直接使用上述 `export`。代理运行在同一台 Linux 主机时使用 `127.0.0.1:7078`；代理位于另一台机器时，将地址替换为该机器的可达 IP 或域名。

## 2.1 当前已验证的参考环境

下表记录本仓库当前开发机已实际跑通的版本。它是复现开发态的参考，不是把本机虚拟环境目录或本机配置文件复制到新机器的要求。

| 项目 | 当前值 | 新环境要求 |
| --- | --- | --- |
| 宿主机 | Linux x86_64（当前验证于 WSL2 Linux） | 正式部署使用 Linux 主机、Docker Engine 与 NVIDIA Container Toolkit |
| Python | `3.13.15` | 优先 Python 3.13；受平台或 NumPy wheel 限制时可改用 3.10，但必须重新执行依赖同步 |
| 虚拟环境 | `/home/mikky/.local/share/ragflow/venv` | 当前机器的固定开发 venv；新环境推荐由 `uv sync` 在仓库 `.venv` 创建 |
| Python 依赖管理 | `uv` 与仓库 `uv.lock` | 使用 `uv sync --frozen`，不要以全局 pip 替代 lock 文件 |
| GraphRAG | InfiniFlow `graspologic` Git 提交 `38e680c` | 不安装 PyPI 的 `graspologic==3.4.4`；保持 lock 文件中固定的 Git 依赖 |
| NumPy | `2.2.6` | 由 `uv.lock` 决定，不单独手工升级或降级 |
| OCR 运行时 | `onnxruntime-gpu 1.23.2` | 必须能列出 `CUDAExecutionProvider` |
| OCR Provider | TensorRT、CUDA、CPU | GPU 解析使用 CUDA；CPU Provider 保留作兜底 |
| GPU | NVIDIA GeForce RTX 4090，24 GiB，驱动 `591.86` | 单卡可跑；多卡按第 8 节扩展 OCR 与 embedding 吞吐 |
| Docker | Engine `26.1.4`，Compose `v2.27.1` | Docker Compose v2，并能将 NVIDIA GPU 暴露给容器 |
| 前端 | Node `24.13.1`，npm `11.8.0` | Node 22 或更高；依赖以 `web/package-lock.json` 为准 |

当前运行时有意使用 `DEVICE=cpu` 与 `OCR_DEVICE=gpu`：通用 PyTorch 路径保持 CPU，DeepDOC 的 ONNX det、rec、layout 和表格模型走 GPU。这样不会为了 OCR 再安装一套通用 torch。请勿把当前机器 venv、`.cache` 或 `conf/service_conf.yaml` 整体复制到新环境；它们分别是机器状态、模型缓存和本机密钥配置。

## 3. 新环境的 AI 可执行启动清单

以下顺序适用于新的 Linux x86_64 + NVIDIA GPU 主机。命令均在仓库根目录执行，除非命令中写明 `web/`。执行前，AI 应先确认 `nvidia-smi`、`docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`、`python3.13 --version` 都成功；任一项失败时先修复主机环境，不应继续安装应用依赖。

1. 克隆仓库并进入目标提交；若需要代理，先设置 `HTTP_PROXY`、`HTTPS_PROXY` 和 `NO_PROXY`（见第 2 节）。
2. 安装与锁定文件一致的 Python 依赖和 DeepDOC 模型：

   ```bash
   uv sync --frozen --python 3.13 --all-extras
   uv run python ragflow_deps/download_deps.py
   ```

3. 为 GPU OCR 安装 ONNX Runtime CUDA 依赖，并在每次启动 Python API/worker 前设置第 8 节的 `LD_LIBRARY_PATH`。用下列检查作为硬性验收：

   ```bash
   uv run python -c "import onnxruntime as ort; assert 'CUDAExecutionProvider' in ort.get_available_providers(); print(ort.get_available_providers())"
   ```

4. 安装前端依赖：

   ```bash
   cd web && npm ci && cd ..
   ```

5. 下载 BGE-M3 到 `.cache/models/bge-m3`，按第 5 节启动 MySQL、Redis、MinIO、Elasticsearch 和 BGE-M3。启动后逐项检查 `docker compose ... ps`、BGE-M3 `/health` 和数据库/ES 的宿主机映射端口。
6. 按第 7 节创建本机 `conf/service_conf.yaml`，只写本机 Docker 暴露的 `localhost` 地址和实际端口；模型地址为 BGE-M3 路由地址。密钥只留在本机文件中。
7. 在终端 A 用第 9 节启动 Python API 和 worker，在终端 B 用第 9 节启动 Vite。若 OCR 使用多卡且解析大 PDF，使用 `WS=1` 与 `OCR_PARALLEL_DEVICES=<卡数>`。
8. 最后执行第 10 节健康检查，上传一份 PDF，并同时观察 API/worker 日志和 `nvidia-smi`。OCR 日志出现 `uses GPU (device N)` 且 BGE-M3 health 正常，才算部署完成。

AI 处理故障时应保留失败命令、完整错误和上述三个验收结果；不要通过修改 `uv.lock`、提交 `service_conf.yaml` 或把容器内部 DNS 名称写进本机 Python 配置来绕过问题。

## 4. 安装 Python 与前端依赖

在仓库根目录执行：

```bash
uv sync --frozen --python 3.13 --all-extras
uv run python ragflow_deps/download_deps.py
cd web
npm ci
cd ..
```

`download_deps.py` 下载 DeepDOC 所需的两组 Hugging Face 资源：

- `InfiniFlow/deepdoc`：文字检测、识别、布局和表格结构 ONNX 模型；
- `InfiniFlow/text_concat_xgb_v1.0`：文本拼接模型。

脚本也下载 NLTK 数据、tokenizer 和构建依赖。网络受限时可设置 `HF_ENDPOINT=https://hf-mirror.com`，也可保留上面的 HTTP/HTTPS 代理。

### GraphRAG 的 graspologic 与 Python 3.13

PyPI 的 `graspologic==3.4.4` 及其上游 NumPy 1.x 约束不适用于 Python 3.13。本仓库不使用该发行版，而是在 `pyproject.toml` 固定 InfiniFlow 维护的 Git 提交 `38e680cab72bc9fb68a7992c3bcc2d53b24e42fd`；`uv.lock` 记录了对应源码，且 `[tool.uv].override-dependencies` 强制 `numpy>=2.1,<2.3`。因此必须执行 `uv sync --frozen --python 3.13 --all-extras`，不要额外执行 `pip install graspologic==3.4.4`，也不要自行把 NumPy 降回 1.x。

安装完成后可验证 GraphRAG 所需 API：

```bash
uv run python -c "import graspologic; from graspologic.partition import hierarchical_leiden; from graspologic.utils import largest_connected_component; print(graspologic.__version__)"
```

当前已验证输出版本为 `0.1.dev847+g38e680cab`，并可导入 `hierarchical_leiden` 与 `largest_connected_component`。

## 5. 下载 BGE-M3 并启动容器依赖

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

## 6. 端口冲突与分离部署

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
## 7. 将本机 Python 连接到容器

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

## 8. 启用 DeepDOC GPU OCR

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

## 9. 启动开发服务

在一个终端启动 Python API 与 worker：

```bash
source .venv/bin/activate
# 当前参考机使用外部 venv；新环境默认是 .venv。
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

## 10. 健康检查与常见问题

```bash
curl -I http://127.0.0.1:9222
curl -I http://127.0.0.1:9380
nvidia-smi
```

- `CUDAExecutionProvider` 不存在：确认使用的是 `onnxruntime-gpu`、`LD_LIBRARY_PATH` 包含 CUDA wheel 的 `lib` 目录，并检查驱动版本。
- BGE-M3 无法启动：检查 `.cache/models/bge-m3` 是否含模型文件，以及 `docker compose logs bge-m3-gpu0 bge-m3-gpu1 bge-m3-router`。
- API 连不上数据库或 ES：以 `docker compose ... port` 的结果更新 `conf/service_conf.yaml`，不要使用容器内部端口假设。
- 前端接口 404：确认 Vite 以 `API_PROXY_SCHEME=python` 启动，且 Python API 正在监听 9380。
