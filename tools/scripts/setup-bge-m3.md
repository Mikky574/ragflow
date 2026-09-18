# Windows 安装 BGE-M3 向量服务

先安装并启动 **Docker Desktop**（Linux 容器模式）。需要 Windows 自带的
`curl.exe`，不需要 Python、CUDA 或 API Key。建议整机至少 16 GB 内存，
Docker 可用内存至少 8 GB；同时运行 RAGFlow 和其他依赖时需要留出更多空间。

将 `setup-bge-m3.bat` 和 `setup-bge-m3.ps1` 放在同一个目录，双击 BAT 即可。
也可以在项目根目录运行：

```bat
tools\scripts\setup-bge-m3.bat
```

脚本会下载指定版本的官方 BAAI/bge-m3 ONNX 文件（约 2.3 GB）、校验权重，
启动 CPU 推理容器，并检查返回的向量是否为 1024 维。模型默认保存到
`%LOCALAPPDATA%\RAGFlow\models\bge-m3`。支持断点续传，重复运行会复用已下载文件。
首次还需下载推理镜像，请另外留出 Docker 磁盘空间。

可选参数：

```bat
rem 下载走代理；Docker 镜像拉取的代理需在 Docker Desktop 中另行设置
tools\scripts\setup-bge-m3.bat -Proxy http://127.0.0.1:7078

rem 使用镜像下载站，并指定模型存放目录
tools\scripts\setup-bge-m3.bat -Endpoint https://hf-mirror.com -ModelDir D:\AI\bge-m3

rem 只下载模型，不检查或启动 Docker
tools\scripts\setup-bge-m3.bat -DownloadOnly

rem 6380 已被其他服务占用时，换端口
tools\scripts\setup-bge-m3.bat -Port 6381
```

RAGFlow 中添加模型：

| 配置项 | 值 |
| --- | --- |
| 提供商 | HuggingFace |
| 实例名称 | local-bge-m3 |
| 模型名称 | BAAI/bge-m3 |
| 模型类型 | embedding |
| API Key | 留空 |
| 最大 tokens | 1024 |
| Windows 后端 Base URL | `http://127.0.0.1:6380` |
| Docker 后端 Base URL | `http://host.docker.internal:6380` |
| WSL 后端 Base URL | `http://<Windows 网关 IP>:6380`，在 WSL 用 `ip route show default` 查询 |

Base URL 不要添加 `/v1` 或 `/embed`。保存后设为默认 Embedding，在知识库中选择该模型。
脚本不会登录账号、修改已有知识库或重建索引。

默认输入上限为 **1024 tokens**，超过上限会截断，建议知识库分块为 512 tokens。
本机已验证长输入预热可能耗尽内存，因此默认不使用模型的 8192-token 上限。
`-MaxTokens` 可调整上限，但需同步调整 RAGFlow 配置，并准备更多内存。
Python 后端建议启动前设置 `EMBEDDING_BATCH_SIZE=4`，减少 CPU 批处理超时。

容器项目名称为 `ragflow-bge-m3`，使用 `unless-stopped` 重启策略。
Docker Desktop 需处于运行状态。维护命令（PowerShell）：

```powershell
docker compose -p ragflow-bge-m3 -f "$env:LOCALAPPDATA\RAGFlow\bge-m3-service\compose.json" logs --tail 50
docker compose -p ragflow-bge-m3 -f "$env:LOCALAPPDATA\RAGFlow\bge-m3-service\compose.json" stop
docker compose -p ragflow-bge-m3 -f "$env:LOCALAPPDATA\RAGFlow\bge-m3-service\compose.json" up -d
```

服务将端口发布到主机网络接口，以供 WSL/Docker 后端访问；它未配置鉴权，
请勿通过路由器转发到公网。连接失败时检查 Windows 防火墙。
