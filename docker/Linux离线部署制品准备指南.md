# Linux 离线部署制品准备指南

本文用于 Linux 服务器无法稳定访问互联网、Windows 工作站可以联网下载的场景。流程是：**Windows 上的 Docker Linux 容器准备制品包 → 上传 Linux → 服务端全程离线安装和验收**。

目标平台：**Linux x86_64、glibc 2.28+、CPython 3.13、NVIDIA GPU**。仓库 `pyproject.toml` 与 `uv.lock` 固定 Python 3.13，Python 3.10 的 wheel 不能混入该制品包。

## 1. 哪些能用 wheel，哪些不能

`.whl` 只解决 Python 应用依赖。以下不是 wheel，需由运维通过系统离线源、`.deb`/`.rpm` 或内部镜像预先安装：

| 层级 | 必需项 | 目标机验收 |
| --- | --- | --- |
| 系统 | Linux x86_64、glibc >= 2.28、bash、tar、pkg-config、libjemalloc2 | `uname -m`、`ldd --version`、`ldconfig -p \| grep jemalloc` |
| Python | Linux CPython 3.13，含 venv、pip | `python3.13 --version` |
| GPU | NVIDIA 驱动 | `nvidia-smi` |
| 容器 | Docker Engine、Compose v2、NVIDIA Container Toolkit | `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` |
| 前端 | Linux Node.js 22+、npm | `node --version`、`npm --version` |

不要上传 Windows 的 `.venv`、`node_modules`、Python、uv 或 wheel。含原生扩展的 Windows 制品无法在 Linux 使用。

## 2. 在目标 Linux 记录规格

先在离线服务器执行并保存输出；Windows 打包时必须与此平台匹配：

```bash
mkdir -p ~/ragflow-offline-audit
{
  uname -m
  cat /etc/os-release
  ldd --version | head -n 1
  python3.13 --version
  node --version
  docker version --format '{{.Server.Version}}'
  docker compose version
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
} | tee ~/ragflow-offline-audit/target-spec.txt
```

本文仅覆盖 `x86_64`。若结果为 `aarch64`，必须单独制作 ARM64 wheel、Docker 镜像与模型服务。

## 3. Windows 联网机准备

1. Docker Desktop 切换到 **Linux containers** 模式。
2. 克隆与服务器完全相同的代码提交：

   ```powershell
   git clone https://github.com/Mikky574/ragflow.git
   cd ragflow
   git checkout <目标提交SHA>
   git status --short
   ```

3. 在仓库外创建制品目录：

   ```powershell
   $Bundle = "$HOME\ragflow-offline-bundle"
   New-Item -ItemType Directory -Force -Path $Bundle, "$Bundle\wheelhouse", "$Bundle\models", "$Bundle\docker", "$Bundle\frontend" | Out-Null
   $Repo = (Get-Location).Path
   ```

4. 下载需要代理时设置：

   ```powershell
   $env:HTTP_PROXY = 'http://127.0.0.1:7078'
   $env:HTTPS_PROXY = 'http://127.0.0.1:7078'
   $env:NO_PROXY = 'localhost,127.0.0.1,::1'
   ```

## 4. 生成 Linux Python 3.13 wheelhouse

### 4.1 从锁文件导出精确依赖

必须使用锁文件，而不是重新 `pip freeze` 或手写 requirements。以下命令在 Linux uv 容器里运行，因此解析目标是 Linux：

```powershell
$UvImage = 'ghcr.io/astral-sh/uv:latest'
docker pull $UvImage
docker run --rm `
  -v "${Repo}:/src:ro" -v "${Bundle}:/bundle" `
  -w /src $UvImage `
  export --frozen --format requirements-txt --all-extras --no-emit-project `
  -o /bundle/requirements-linux-py313.txt

Get-FileHash uv.lock -Algorithm SHA256 | Tee-Object "$Bundle\uv.lock.sha256"
git rev-parse HEAD | Set-Content "$Bundle\source-revision.txt"
```

### 4.2 在 Linux 容器内下载并构建 wheel

`graspologic` 是 Git 依赖，必须安装 git 并执行 `pip wheel`，不能只用 Windows 的 `pip download`。

```powershell
$PyImage = 'python:3.13-bookworm'
docker pull $PyImage
docker run --rm `
  -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY `
  -v "${Bundle}:/bundle" -w /bundle $PyImage `
  bash -lc 'apt-get update && apt-get install -y --no-install-recommends git build-essential pkg-config && python -m pip install --upgrade pip wheel setuptools && python -m pip wheel --wheel-dir /bundle/wheelhouse -r /bundle/requirements-linux-py313.txt'
```

确认以下关键 wheel 存在：

```powershell
Get-ChildItem "$Bundle\wheelhouse\graspologic*"
Get-ChildItem "$Bundle\wheelhouse\onnxruntime_gpu*"
Get-ChildItem "$Bundle\wheelhouse\numpy*"
```

仓库不使用 PyPI 的 `graspologic==3.4.4`；它使用 InfiniFlow 固定 Git 提交构建出的 wheel，并把 NumPy 固定为 `>=2.1,<2.3`。不要把 `graspologic==3.4.4` 或 NumPy 1.x 放进 wheelhouse。

### 4.3 强制无网络安装演练

这是能否交付的判定点。演练只允许读取 `/bundle/wheelhouse`；如有下载行为，说明包不完整，必须留在 Windows 重新制作。

```powershell
docker run --rm `
  -v "${Repo}:/src:ro" -v "${Bundle}:/bundle" `
  -w /src $PyImage `
  bash -lc 'python -m venv /tmp/ragflow-venv && /tmp/ragflow-venv/bin/pip install --no-index --find-links /bundle/wheelhouse --no-deps /bundle/wheelhouse/*.whl && PYTHONPATH=/src /tmp/ragflow-venv/bin/python -c "import graspologic, numpy, onnxruntime; from graspologic.partition import hierarchical_leiden; print(graspologic.__version__); print(numpy.__version__); print(onnxruntime.get_available_providers())"'
```

CPU 容器中没有 CUDA Provider 是正常的；此步骤只验证 Linux wheel 可安装以及 GraphRAG API 可导入。CUDA 在服务器 GPU 验收。

## 5. 下载 DeepDOC、NLTK 和 BGE-M3

模型与 `ragflow_deps` 中的 Linux 原生资源不属于 wheel。先使用 wheelhouse 建立临时 Linux Python 环境，再下载：

```powershell
docker run --rm `
  -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY `
  -v "${Repo}:/src:ro" -v "${Bundle}:/bundle" `
  -w /work $PyImage `
  bash -lc 'cp -a /src/. /work-src && python -m venv /tmp/ragflow-venv && /tmp/ragflow-venv/bin/pip install --no-index --find-links /bundle/wheelhouse --no-deps /bundle/wheelhouse/*.whl && cd /work-src && PYTHONPATH=/work-src /tmp/ragflow-venv/bin/python ragflow_deps/download_deps.py && mkdir -p /bundle/models/ragflow_deps && cp -a ragflow_deps/. /bundle/models/ragflow_deps/'
```

该步骤包含：

- `InfiniFlow/deepdoc` OCR、布局、表格模型；
- `InfiniFlow/text_concat_xgb_v1.0` 文本拼接模型；
- NLTK 数据、tokenizer；
- Tika、Chrome、Linux 原生构建资源等 `ragflow_deps` 文件。

再下载 BGE-M3：

```powershell
docker run --rm `
  -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY `
  -v "${Bundle}:/bundle" -w /bundle $PyImage `
  bash -lc 'python -m venv /tmp/model-venv && /tmp/model-venv/bin/pip install huggingface-hub && /tmp/model-venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id=\"BAAI/bge-m3\", local_dir=\"/bundle/models/bge-m3\")"'
```

服务器端不再运行 `snapshot_download`，只复制制品里的模型目录。

## 6. 导出 Docker 镜像

先从 Compose 自动生成镜像列表，再完整拉取和导出，避免手写版本号遗漏：

```powershell
docker compose -f docker/docker-compose-base.yml -f docker/docker-compose-python-dev.yml `
  --profile elasticsearch --profile mysql config --images |
  Sort-Object -Unique | Set-Content "$Bundle\docker\images.txt"

Get-Content "$Bundle\docker\images.txt" | ForEach-Object { docker pull $_ }
$Images = Get-Content "$Bundle\docker\images.txt"
docker save --output "$Bundle\docker\ragflow-images.tar" $Images
```

导出后在 Windows 验证：

```powershell
docker load --input "$Bundle\docker\ragflow-images.tar"
```

当前清单通常包含 MySQL、Elasticsearch、Valkey、MinIO、Nginx、TEI BGE-M3 镜像；以这次生成的 `images.txt` 为唯一准则。

## 7. 制作 Linux 前端依赖包

Windows 的 `web/node_modules` 不能上传；`esbuild` 等含平台二进制。必须在 Linux Node 容器中执行 `npm ci`：

```powershell
$NodeImage = 'node:22-bookworm'
docker pull $NodeImage
docker run --rm `
  -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY `
  -v "${Repo}:/src:ro" -v "${Bundle}:/bundle" `
  $NodeImage bash -lc 'mkdir -p /work && cp /src/web/package.json /src/web/package-lock.json /work/ && cd /work && npm ci && tar -C /work -czf /bundle/frontend/node_modules-linux-x64.tar.gz node_modules && cp package.json package-lock.json /bundle/frontend/'
```

## 8. 生成校验清单并传输

源代码与制品必须属于同一提交。生成源码归档、SHA-256 校验表和传输压缩包：

```powershell
git archive --format=tar.gz --output "$Bundle\ragflow-source.tar.gz" HEAD
Get-ChildItem $Bundle -Recurse -File |
  Get-FileHash -Algorithm SHA256 |
  ForEach-Object { "{0}  {1}" -f $_.Hash, $_.Path.Substring($Bundle.Length + 1) } |
  Set-Content "$Bundle\SHA256SUMS"
Compress-Archive -Path "$Bundle\*" -DestinationPath "$HOME\ragflow-offline-bundle.zip" -Force
```

模型与 Docker tar 文件较大。文件服务器有限制时可以分卷，但要保留原始校验表：

```powershell
7z a -v4g "$HOME\ragflow-offline-bundle.7z" "$Bundle\*"
```

上传方式可选 U 盘、内网文件服务器或 `scp`。目标目录假定为 `/opt/ragflow-offline-bundle`，源代码目录为 `/opt/ragflow`。

## 9. Linux 离线安装

### 9.1 验证传输

```bash
cd /opt/ragflow-offline-bundle
sha256sum -c SHA256SUMS
cat source-revision.txt
```

解压对应版本的 `ragflow-source.tar.gz` 到 `/opt/ragflow`。如果使用 Git 仓库，`git rev-parse HEAD` 必须与 `source-revision.txt` 一致。

### 9.2 从 wheelhouse 安装 Python 依赖

```bash
cd /opt/ragflow
python3.13 -m venv .venv
.venv/bin/pip install --no-index --find-links /opt/ragflow-offline-bundle/wheelhouse --no-deps /opt/ragflow-offline-bundle/wheelhouse/*.whl
PYTHONPATH="$PWD" .venv/bin/python - <<'PY'
import graspologic, numpy, onnxruntime
from graspologic.partition import hierarchical_leiden
from graspologic.utils import largest_connected_component
print('graspologic:', graspologic.__version__)
print('numpy:', numpy.__version__)
print('providers:', onnxruntime.get_available_providers())
PY
```

离线安装时若出现访问 PyPI、Gitee 或 Hugging Face 的行为，立刻停止。说明 wheelhouse 缺少依赖，必须回 Windows 重新打包，不能临时给服务器开公网。

### 9.3 恢复模型与前端依赖

```bash
cd /opt/ragflow
rm -rf ragflow_deps/huggingface.co ragflow_deps/nltk_data
cp -a /opt/ragflow-offline-bundle/models/ragflow_deps/. ragflow_deps/
mkdir -p .cache/models
cp -a /opt/ragflow-offline-bundle/models/bge-m3 .cache/models/
tar -C web -xzf /opt/ragflow-offline-bundle/frontend/node_modules-linux-x64.tar.gz
```

### 9.4 导入镜像并启动容器依赖

```bash
docker load --input /opt/ragflow-offline-bundle/docker/ragflow-images.tar
cd /opt/ragflow
BGE_M3_PORT=6380 docker compose \
  -f docker/docker-compose-base.yml \
  -f docker/docker-compose-python-dev.yml \
  --profile elasticsearch --profile mysql up -d
```

默认 BGE-M3 Compose 使用两张 GPU。单卡机器必须先改成单卡 TEI 服务和单后端 Nginx upstream，不能直接启动包含 `device_ids: ["1"]` 的双卡默认配置。

### 9.5 私有配置、启动和 GPU 验收

创建本机私有 `conf/service_conf.yaml`，填 Docker 对宿主机暴露的 MySQL、Redis、MinIO、Elasticsearch 端口，以及 BGE-M3 地址。不要把这个文件、密码或密钥提交 Git。启动 Python 服务：

```bash
cd /opt/ragflow
source .venv/bin/activate
export PYTHONPATH="$PWD"
export API_PROXY_SCHEME=python
export DOC_ENGINE=elasticsearch
export DB_TYPE=mysql
export DEVICE=cpu
export OCR_DEVICE=gpu
export OCR_PARALLEL_DEVICES=1
bash docker/launch_backend_service.sh
```

在第二个终端启动前端：

```bash
cd /opt/ragflow/web
npm run dev -- --host 0.0.0.0 --port 9222
```

验收：

```bash
curl http://127.0.0.1:6380/health
curl -I http://127.0.0.1:9380
nvidia-smi
```

Python worker 日志应出现 `uses GPU (device 0)`。`onnxruntime.get_available_providers()` 必须包含 `CUDAExecutionProvider`；若只有 CPU Provider，检查 NVIDIA 驱动和 [Python 开发态与容器依赖运行指南](Python开发态与容器依赖运行指南.md) 中的 CUDA wheel 动态库路径。

## 10. 失败排查

| 现象 | 原因 | 正确处理 |
| --- | --- | --- |
| Linux 提示 wheel 不支持 | 下载了 Windows wheel，或架构不一致 | 在 Windows 的 Linux Docker 容器重新执行 `pip wheel` |
| 安装时访问 Gitee | graspologic Git 依赖未打成 wheel | 重新制作 wheelhouse，并确认有 graspologic wheel |
| 安装时访问 PyPI | wheelhouse 不完整或漏了 `--no-index` | Windows 上重做无网络演练后再上传 |
| graspologic 与 NumPy 1.x 冲突 | 混入 PyPI `graspologic==3.4.4` | 使用仓库锁定的 InfiniFlow Git fork 和 NumPy 2.x |
| 无 CUDA Provider | 驱动、CUDA 动态库或 GPU wheel 不匹配 | 先确认 `nvidia-smi`，再按开发态指南设置库路径 |
| 前端找不到 esbuild | 上传了 Windows node_modules | 用 Linux Node 容器重新 `npm ci` 并打包 |
| Compose 拉镜像 | 未导入镜像 tar 或标签不同 | 对比 `images.txt`，重新 `docker load` |

每次 `uv.lock`、`package-lock.json`、Compose 镜像标签或模型版本变更后，都必须重新制作离线包。`source-revision.txt`、`SHA256SUMS` 与无网络安装演练是制品交付的验收标准。
