# Python 源码开发 + Docker 依赖服务：执行手册

本手册面向执行部署的 AI 和开发者。目标是修改 Python OCR/PDF/分块代码后，
实际运行当前 checkout 的代码。Linux 主流程以 Ubuntu 24.04、x86_64、CPU 为基准。
Windows 使用 WSL2 执行 Python，差异见文末。不是生产部署或 GPU 调优手册。

## 0. 执行约定：先识别环境，不要跳步

1. 阅读仓库 `AGENTS.md`；修改前端时再读 `web/CLAUDE.md`。
2. 仓库是 `https://github.com/Mikky574/ragflow.git`，本手册对应 `main`。
3. 已有仓库先运行 `git status --short`。有未提交改动时保留改动，不执行 reset/clean。
4. 下文 Linux 命令均在 Bash 中执行；除明确注明 `cd web` 外，从仓库根目录执行。
5. 每一步确认成功再进行下一步。记录失败的命令及错误，不能把“进程存在”当作部署成功。
6. 已有环境先检查进程、容器和端口，复用已有服务。不要重复启动 API/worker 或另起同端口容器。
7. 不运行 `docker compose down -v`，不删除现有数据卷，不重置数据库来解决连接错误。
8. 不将用户 API Key、实际密码、`conf/local.service_conf.yaml` 提交到 Git。

## 1. 必须保持的架构

| 组件 | 运行方式 | 用途/端口 |
| --- | --- | --- |
| Python API | 宿主机 Python 虚拟环境，`api/ragflow_server.py` | 9380 |
| Python worker | 同一个虚拟环境，`rag/svr/task_executor.py` | 消费解析队列，无网页端口 |
| 前端 | `web/` 下的 Vite 开发服务器 | 9222，代理到 Python API |
| MySQL | Docker | 宿主机 3306 |
| Elasticsearch | Docker | 宿主机 1200 → 容器 9200 |
| MinIO 兼容存储 | Docker，仓库当前使用 pgsty/silo 镜像 | 9000，控制台 9001 |
| Redis 协议服务 | Docker，Valkey | 6379 |
| BGE-M3 | Docker，Hugging Face TEI CPU | 6380 → 容器 80 |
| DeepSeek | 外部 API | 只负责聊天，不替代 Embedding 或本地 OCR |

**只使用 `docker/docker-compose-base.yml` 启动上述依赖服务。**
不要启动完整 RAGFlow 应用镜像来替代 Python 源码；不要启动 Go 后端或用
`build.sh --go` 解决 Python 环境问题。修改宿主机源码不会自动改动应用镜像里的代码。

DeepDOC OCR 模型由 Python worker 在宿主机加载，和 BGE-M3 向量容器是两套独立模型。

## 2. Linux 前置条件

建议至少 16 GB 内存（同时运行全部服务建议 24 GB 以上），至少 40 GB 可用磁盘。
这是容量建议，实际消耗取决于解析并发、文档大小及模型。

先检查：

```bash
uname -m
docker version
docker compose version
uv --version
node --version
npm --version
free -h
df -h .
```

要求 Docker Engine 正常运行、Compose v2、uv，以及 Node.js 22 或 24 LTS。
若未安装，先按操作系统对应的官方安装步骤安装；不要把 Windows BAT 在 Linux 中运行。
本机验证使用了 Python 3.13、Node.js 24。以下系统依赖命令适用于 Ubuntu 24.04：

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates build-essential pkg-config \
  libgl1 libglib2.0-0 libgomp1 libjemalloc-dev libicu74 poppler-utils tmux
```

Docker 权限不足时由管理员配置当前用户权限或使用 sudo；不要 chmod 777 Docker socket。
新环境克隆；已有仓库不重复克隆：

```bash
git clone https://github.com/Mikky574/ragflow.git
cd ragflow
git branch --show-current
git remote -v
```

下文假定端口保持仓库默认值。若端口占用，应先识别所属服务，不能直接杀死未知进程。

## 3. 启动 Docker 基础服务

Elasticsearch 需要提高内核映射上限：

```bash
sudo sysctl -w vm.max_map_count=262144
```

需要跨重启持久化时，把 `vm.max_map_count=262144` 放入
`/etc/sysctl.d/99-ragflow.conf`，由管理员执行 `sudo sysctl --system`。

为开发环境限制 ES 内存，在项目根目录生成本地覆盖配置：

```bash
mkdir -p .cache/dev
cat > .cache/dev/compose.yml <<'YAML'
services:
  es01:
    environment:
      ES_JAVA_OPTS: "-Xms1g -Xmx1g"
    mem_limit: 2g
YAML
docker compose -p docker -f docker/docker-compose-base.yml \
  -f .cache/dev/compose.yml up -d es01 mysql minio redis
docker compose -p docker -f docker/docker-compose-base.yml \
  -f .cache/dev/compose.yml ps
```

始终保持同一个项目名 `-p docker`，否则可能创建另一组空数据卷。
四项服务应为 running，健康检查应逐步变为 healthy。失败时看对应日志：

```bash
docker compose -p docker -f docker/docker-compose-base.yml \
  -f .cache/dev/compose.yml logs --tail 80 es01 mysql minio redis
```

配置插值来自 `docker/.env`。修改实际部署密码后，必须同步 Python 配置。
已有 MySQL 数据卷不会因为更改 `.env` 而自动修改数据库密码。

## 4. 安装 Python 环境和 OCR 资源

```bash
uv python install 3.13
uv sync --python 3.13 --all-extras --frozen
source .venv/bin/activate
python --version
python -c 'import numpy, onnxruntime; print(numpy.__version__, onnxruntime.__version__)'
```

仓库已加入 Python 3.13 所需的 NumPy 2 约束。不要降回 NumPy 1.26 或删除锁文件。
出现依赖冲突时记录错误，不用 `--no-deps` 随意跳过安装。

以下下载的是 Python PDF/OCR 开发所需资源，不需要为本任务下载全部 Go/C++ 构建依赖：

```bash
export HF_HUB_DISABLE_XET=1
# 仅当官方 Hugging Face 无法访问时启用镜像：
# export HF_ENDPOINT=https://hf-mirror.com
export NLTK_ALLOW_PROXIED_URLOPEN=1
python - <<'PY'
from pathlib import Path
from huggingface_hub import snapshot_download
import nltk
import urllib.request

snapshot_download('InfiniFlow/deepdoc', local_dir='rag/res/deepdoc',
                  allow_patterns=['*.onnx', 'ocr.res'])
snapshot_download('InfiniFlow/text_concat_xgb_v1.0', local_dir='rag/res/deepdoc',
                  allow_patterns=['*.model'])
target = Path('ragflow_deps/nltk_data')
target.mkdir(parents=True, exist_ok=True)
for name in ('punkt', 'punkt_tab', 'wordnet'):
    if not nltk.download(name, download_dir=str(target)):
        raise RuntimeError(f'NLTK download failed: {name}')
encoding = Path('ragflow_deps/cl100k_base.tiktoken')
if not encoding.exists():
    urllib.request.urlretrieve(
        'https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken', encoding)
print('Python parsing resources downloaded')
PY
```

下载失败可修复网络后重跑。配置代理时将 `127.0.0.1,localhost` 和依赖服务地址加入
`NO_PROXY`，避免本地数据库/模型请求绕到外部代理。下载代理和 Docker 拉镜像代理分别配置。

## 5. 生成 Python 本地配置

先确保 `conf/local.service_conf.yaml` 不会进入提交：

```bash
grep -qxF '/conf/local.service_conf.yaml' .git/info/exclude || \
  printf '\n/conf/local.service_conf.yaml\n' >> .git/info/exclude
```

下面从 Compose 的实际解析结果获取密码和发布端口，不在终端打印密码。
Linux Docker 与 Python 同宿主机时地址是 `127.0.0.1`。
已有本地配置时先检查并保留，不要直接覆盖：

```bash
python - <<'PY'
import json
import subprocess
from pathlib import Path
from ruamel.yaml import YAML

target = Path('conf/local.service_conf.yaml')
if target.exists():
    raise SystemExit('Configuration exists. Inspect and update it instead of overwriting.')
services = json.loads(subprocess.check_output([
    'docker', 'compose', '-p', 'docker', '-f', 'docker/docker-compose-base.yml',
    '-f', '.cache/dev/compose.yml', 'config', '--format', 'json'
], text=True))['services']
yaml = YAML()
config = yaml.load(Path('conf/service_conf.yaml').read_text())
host = '127.0.0.1'  # Windows/WSL 部署必须改为 Windows 网关 IP，见第 11 节
def port(service, internal):
    return next(int(p['published']) for p in services[service]['ports'] if int(p['target']) == internal)
config['mysql'].update(host=host, port=port('mysql', 3306),
    password=services['mysql']['environment']['MYSQL_ROOT_PASSWORD'])
config['minio'].update(host=f"{host}:{port('minio', 9000)}",
    user=services['minio']['environment']['MINIO_ROOT_USER'],
    password=services['minio']['environment']['MINIO_ROOT_PASSWORD'])
config['es'].update(hosts=f"http://{host}:{port('es01', 9200)}",
    password=services['es01']['environment']['ELASTIC_PASSWORD'])
redis_command = services['redis']['command']
config['redis'].update(host=f"{host}:{port('redis', 6379)}",
    password=redis_command[redis_command.index('--requirepass') + 1])
config['user_default_llm'] = {'default_models': {}}
with target.open('w') as stream:
    yaml.dump(config, stream)
target.chmod(0o600)
print('Local service configuration created; no model credentials configured.')
PY
```

`user_default_llm` 清空占位配置，防止新账号继承不存在的默认模型；实际模型在登录后添加。
仓库配置加载器会合并 `conf/local.service_conf.yaml`。此步骤不要改动公共的默认配置文件。

## 6. 启动源码 API 和 worker

终端 A，从项目根目录执行：

```bash
bash tools/scripts/start-python-dev.sh
```

该脚本依次初始化表、执行仓库已有迁移，再启动 API 和一个 common 队列 worker。
首次连接的是已有业务数据库时，应先备份再执行迁移。
脚本在前台运行，按 Ctrl+C 会停止两个子进程。可在 `tmux` 会话中运行，以免 SSH 断开停止服务。
不要只启动 API：只有 API 时登录可能正常，但文档会一直等待解析。

自定义虚拟环境路径时：

```bash
RAGFLOW_VENV=/opt/ragflow-venv bash tools/scripts/start-python-dev.sh
```

在另一个终端检查：

```bash
curl --fail http://127.0.0.1:9380/api/v1/system/ping
curl --fail http://127.0.0.1:9380/api/v1/system/healthz
curl --fail http://127.0.0.1:9380/api/v1/language
pgrep -af 'ragflow_server.py|task_executor.py'
```

期望：ping 返回 `pong`；healthz 中 db/doc_engine/redis/storage/status 为 `ok`；
language 表示 `python`；进程中同时有 API 和 worker。实际 HTTP 返回格式以接口为准。

## 7. 启动前端，明确连接 Python

终端 B：

```bash
cd web
npm ci
```

在 `web/.env.development.local` 中设置 `API_PROXY_SCHEME=python`。
如果文件不存在可以执行下面命令；已有文件时编辑对应键，保留其他配置：

```bash
printf 'API_PROXY_SCHEME=python\n' > .env.development.local
npm run dev -- --host 127.0.0.1
```

Vite 默认代理到 `127.0.0.1:9380`，浏览器入口为 `http://127.0.0.1:9222`。
验证代理：`curl --fail http://127.0.0.1:9222/api/v1/system/ping` 应返回 `pong`。
如果前端显示 Go 版本界面，检查 `.env.development.local`，然后重启 Vite。

远程服务器推荐在你自己的电脑建立 SSH 隧道，再用浏览器打开本机 9222：

```bash
ssh -N -L 9222:127.0.0.1:9222 USER@SERVER
```

把 USER 和 SERVER 替换成真实账号和服务器地址。不要把开发服务器和无鉴权模型端口直接公开到公网。

## 8. Linux 上准备 BGE-M3 服务

继续使用第 4 步的 Python 环境，从项目根目录运行：

```bash
python - <<'PY'
from huggingface_hub import snapshot_download
from pathlib import Path
import hashlib
root = Path('.cache/models/bge-m3')
snapshot_download('BAAI/bge-m3', revision='5617a9f61b028005a4858fdac845db406aefb181',
    local_dir=str(root), allow_patterns=['*.json', 'sentencepiece.bpe.model', 'onnx/*'])
with (root / 'onnx/model.onnx_data').open('rb') as f:
    digest = hashlib.file_digest(f, 'sha256').hexdigest()
assert digest == '1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4', digest
print('BGE-M3 weights verified')
PY
docker run -d --name ragflow-bge-m3 --restart unless-stopped \
  --memory 5g --cpus 4 -e OMP_NUM_THREADS=4 \
  -p 127.0.0.1:6380:80 \
  --mount "type=bind,source=$PWD/.cache/models/bge-m3,target=/model,readonly" \
  ghcr.io/huggingface/text-embeddings-inference:cpu-1.8 \
  --model-id /model --pooling cls --max-batch-tokens 1024 \
  --max-client-batch-size 16 --max-concurrent-requests 16 --auto-truncate
docker logs --tail 30 ragflow-bge-m3
```

`docker run` 只用于首次创建。容器已存在时先 `docker inspect ragflow-bge-m3`，
核对挂载路径和端口，使用 `docker start ragflow-bge-m3`；不要反复创建重名容器。
日志出现 Ready 后验证：

```bash
curl --fail http://127.0.0.1:6380/health
python - <<'PY'
import requests
r = requests.post('http://127.0.0.1:6380/embed',
    json={'inputs': ['高效率功率放大器', 'High efficiency power amplifier']}, timeout=60)
r.raise_for_status()
v = r.json()
assert len(v) == 2 and all(len(row) == 1024 for row in v)
print('BGE-M3 embedding check passed: 2 x 1024')
PY
```

登录 RAGFlow，在模型设置中添加：提供商 `HuggingFace`，实例 `local-bge-m3`，
模型名 `BAAI/bge-m3`，类型 `embedding`，Base URL `http://127.0.0.1:6380`，
API Key 留空，最大 tokens 为 `1024`。设为默认 Embedding。
Base URL 不追加 `/embed` 或 `/v1`。这里 Python 在宿主机运行，所以无需使用 Docker 内部主机名。

CPU 输入上限为 1024 tokens，长文本会截断；知识库建议 512 tokens 分块。
启动脚本已设 `EMBEDDING_BATCH_SIZE=4`。不要仅将输入上限改到 8192：首次预热可能耗尽内存。
DeepSeek 的 Base URL、模型名称和 API Key 由用户在模型设置中另外配置，不能编造。

## 9. 文献解析验收与改代码后的操作

1. 创建测试知识库，选择 BGE-M3；解析器用通用，布局识别用 DeepDOC，英文论文选择 English。
2. 上传一篇短 PDF，点击解析。等待完成后打开分片查看原文高亮。
3. 检查跨页、双栏和图表周围的顺序。当前修复的目标是先读完左栏再读右栏，
   即使右栏正文在页面上更靠上。
4. 搜索正文中的一句话，确认检索返回对应分片。聊天验收还需配置有效的聊天模型。

修改 `deepdoc/`、`rag/app/` 或 Python API 后：

```bash
# 在终端 A 按 Ctrl+C，确认旧 API 和 worker 均退出，再执行：
bash tools/scripts/start-python-dev.sh
```

**Python worker 没有自动热重载。重启后还要在网页重新解析原文档，旧分片不会自动更新。**
只修改前端组件通常由 Vite 热更新；修改 Vite 环境变量需要重启前端。
仅修改模型设置通常不需要重启后端，但更换已有知识库的向量模型需重新生成向量。
不要在旧 worker 仍运行时再启动一个新 worker，否则任务可能被旧代码抢走。

阅读顺序回归测试：

```bash
export PYTHONPATH="$PWD"
export NLTK_DATA="$PWD/ragflow_deps/nltk_data"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
.venv/bin/python -m pytest --confcutdir=test/unit_test/deepdoc/parser \
  test/unit_test/deepdoc/parser/test_pdf_reading_order.py -q -o filterwarnings=ignore
```

此命令使用已下载的 NLTK 数据，跳过会主动联网下载的父目录 conftest。
`filterwarnings=ignore` 用于开发环境第三方依赖弃用警告，不代表忽略测试断言。

## 10. 按症状排查，不要直接重装

| 现象 | 检查与处理 |
| --- | --- |
| 登录正常，解析一直排队 | 检查 worker 进程、Redis 连接和 `logs/task_executor_common_local_0.log` |
| healthz 超时或失败 | 先看 Docker 四项依赖状态、API 日志，核对端口/密码/地址 |
| MySQL access denied | 对照现有数据卷的实际密码；改 `.env` 不会修改已初始化密码 |
| OCR 模型找不到 | 检查 `rag/res/deepdoc`、工作目录与模型下载是否完成 |
| NLTK LookupError | 检查 worker 的 `NLTK_DATA` 是否指向实际下载目录 |
| tiktoken 首次调用卡住 | 检查 `ragflow_deps/cl100k_base.tiktoken` 和下载网络 |
| BGE 连接拒绝 | 看模型容器日志是否 Ready，再核对 Python 到容器发布端口的地址 |
| BGE 重启或 OOM | 检查 `docker stats --no-stream`，保持 1024-token 上限，减少并发 |
| 改排序后页面仍旧错 | 确认 worker 已重启并重新解析文档，排除读到旧分片 |
| 改代码完全无效 | 用 `ps` 确认源码路径，检查是否实际访问了另一个 RAGFlow 容器或 Go 服务 |
| 前端连接失败 | 分别检查 9380 的 ping 和通过 9222 代理的 ping |

调试命令：

```bash
tail -n 80 logs/ragflow_server.log
tail -n 80 logs/task_executor_common_local_0.log
docker stats --no-stream
ss -lntp | grep -E ':(9380|9222|6380|1200|3306|9000|6379)\b'
```

任务结束时向用户汇报：仓库与分支、源码绝对路径、虚拟环境、容器名和端口、
API/worker/前端启动命令、健康检查结果，以及是否已重新解析文档。
某项未验证必须明确说明，不得把离线测试通过说成线上入库成功。

## 11. Windows + WSL2 差异

1. Windows 安装 Docker Desktop，启动 Linux 容器；Python 放在 Ubuntu 24.04 WSL2 中。
2. 源码可放 Windows 目录并从 WSL `/mnt/c/...` 访问。路径有中文或空格时加引号。
3. Python 虚拟环境放 WSL Linux 文件系统中，避免 `.venv` 位于 `/mnt/c` 的性能和链接问题：

   ```bash
   export UV_PROJECT_ENVIRONMENT=/opt/ragflow-venv
   uv sync --python 3.13 --all-extras --frozen
   source /opt/ragflow-venv/bin/activate
   ```

   `/opt` 不可写时改用 `$HOME/.venvs/ragflow`，启动时将同一路径传给 `RAGFLOW_VENV`。
4. Docker Desktop 中启用该 WSL 发行版的 Docker Integration，确认 WSL 内 `docker info` 成功，
   才运行第 3、5 节的 Docker 命令。不要在同一 WSL 里额外安装并运行第二个 Docker daemon。
5. Windows PowerShell 设置 Docker 虚拟机参数：

   ```powershell
   wsl -d docker-desktop -u root --exec sysctl -w vm.max_map_count=262144
   ```

6. NAT 网络下，Python 在 WSL 中连接 Windows 发布端口可能需要 Windows 网关地址：

   ```bash
   ip route show default
   ```

   使用输出中 `via` 后面的 IP 替换第 5 节的 `host`，同时替换 RAGFlow 模型配置里的 BGE Base URL。
   不要把其他电脑的 `172.x.x.x` 地址抄过来。重启 WSL 后如地址改变，两处都要更新。
   镜像网络等其他模式以实际连通测试为准。
7. Windows 下载/启动 BGE 用 `tools/scripts/setup-bge-m3.bat`，详细参数见
   [BGE-M3 安装说明](../tools/scripts/setup-bge-m3.md)。不要再同时执行第 8 节的 Linux `docker run`。
8. WSL 后端启动：

   ```bash
   RAGFLOW_VENV=/opt/ragflow-venv bash tools/scripts/start-python-dev.sh
   ```

9. 前端可以在 Windows 项目 `web` 目录运行 `npm.cmd ci` 和
   `npm.cmd run dev -- --host 127.0.0.1`；先确认 Windows 可以访问 `http://127.0.0.1:9380`。
   `.env.development.local` 仍须设置 `API_PROXY_SCHEME=python`。
10. Windows 代理监听 `127.0.0.1` 不代表 WSL NAT 内也能访问该代理；下载失败时先验证代理地址，
    不要反复更换 Python 依赖版本。Windows BGE BAT 的 `-Proxy` 是 Windows 侧代理地址。

本手册不依赖旧电脑的 `.cache/dev/backend.sh`、个人账号 ID 或未提交的本地配置。
新环境必须使用这里的版本化脚本与当前环境的真实地址。
