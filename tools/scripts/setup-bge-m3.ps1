# Windows PowerShell 5.1+. No Python installation required.
[CmdletBinding()]
param(
    [string]$ModelDir = (Join-Path $env:LOCALAPPDATA 'RAGFlow\models\bge-m3'),
    [ValidateRange(1, 65535)][int]$Port = 6380,
    [ValidateRange(128, 8192)][int]$MaxTokens = 1024,
    [string]$Proxy = '',
    [string]$Endpoint = 'https://huggingface.co',
    [switch]$DownloadOnly,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
if ($Help) {
    Write-Host @'
setup-bge-m3.bat [-ModelDir PATH] [-Port 6380] [-MaxTokens 1024]
                 [-Proxy http://127.0.0.1:7078] [-Endpoint https://hf-mirror.com]
                 [-DownloadOnly]

Requires Windows curl.exe; service startup requires running Docker Desktop
in Linux-container mode. Downloads pinned BAAI/bge-m3 ONNX weights (~2.3 GB).
Default model directory: %LOCALAPPDATA%\RAGFlow\models\bge-m3
Set BGE_NO_PAUSE=1 when invoking the BAT from automation.
The download proxy does not configure Docker's image-pull proxy.
'@
    exit 0
}

try {
    $curl = (Get-Command curl.exe -ErrorAction Stop).Source
    if (-not $DownloadOnly) {
        $dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
        $docker = if ($dockerCommand) { $dockerCommand.Source } else {
            @(
                (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'),
                (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe')
            ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        }
        if (-not $docker) { throw 'Install and start Docker Desktop with Linux containers, then run this script again.' }
        $osType = & $docker info --format '{{.OSType}}'
        if ($LASTEXITCODE -ne 0 -or $osType -ne 'linux') { throw 'Docker Desktop is not ready in Linux-container mode.' }
        & $docker compose version
        if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 is required (included with Docker Desktop).' }
    }

    $ModelDir = [IO.Path]::GetFullPath($ModelDir)
    New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
    $revision = '5617a9f61b028005a4858fdac845db406aefb181'
    $dataHash = '1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4'
    $files = @(
        'config.json', 'config_sentence_transformers.json', 'modules.json',
        'sentence_bert_config.json', 'sentencepiece.bpe.model',
        'special_tokens_map.json', 'tokenizer.json', 'tokenizer_config.json',
        '1_Pooling/config.json', 'onnx/config.json', 'onnx/Constant_7_attr__value',
        'onnx/model.onnx', 'onnx/sentencepiece.bpe.model',
        'onnx/special_tokens_map.json', 'onnx/tokenizer.json',
        'onnx/tokenizer_config.json', 'onnx/model.onnx_data'
    )
    Write-Host "Model directory: $ModelDir"
    Write-Host 'Allow at least 4 GB free disk space. Interrupted downloads resume on the next run.'
    foreach ($file in $files) {
        $target = Join-Path $ModelDir $file
        if ((Test-Path -LiteralPath $target) -and (Get-Item -LiteralPath $target).Length -gt 0) {
            Write-Host "Already downloaded: $file"
            continue
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        $partial = "$target.part"
        $url = "$($Endpoint.TrimEnd('/'))/BAAI/bge-m3/resolve/$revision/$file"
        $curlArgs = @('--fail', '--location', '--retry', '3', '--retry-delay', '2',
            '--connect-timeout', '20', '--speed-time', '90', '--speed-limit', '1024',
            '--continue-at', '-', '--output', $partial)
        if ($Proxy) { $curlArgs += @('--proxy', $Proxy) }
        Write-Host "Downloading: $file"
        & $curl @curlArgs $url
        if ($LASTEXITCODE -ne 0) { throw "Download failed: $file. Rerun to resume; use -Proxy or -Endpoint if needed." }
        if ((Get-Item -LiteralPath $partial).Length -eq 0) { throw "Empty download: $file" }
        Move-Item -LiteralPath $partial -Destination $target -Force
    }
    Write-Host 'Verifying model weight SHA256...'
    $data = Join-Path $ModelDir 'onnx/model.onnx_data'
    if ((Get-Item -LiteralPath $data).Length -ne 2266820608 -or
        (Get-FileHash -LiteralPath $data -Algorithm SHA256).Hash.ToLowerInvariant() -ne $dataHash) {
        throw "Weight verification failed. Move the invalid file out of the model directory and rerun: $data"
    }
    foreach ($file in $files | Where-Object { $_ -like '*.json' }) {
        Get-Content -LiteralPath (Join-Path $ModelDir $file) -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null
    }
    Write-Host 'Model download and verification completed.'
    if ($DownloadOnly) { exit 0 }

    $image = 'ghcr.io/huggingface/text-embeddings-inference:cpu-1.8'
    $localImage = & $docker image ls --filter "reference=$image" --format '{{.ID}}'
    if ($LASTEXITCODE -ne 0) { throw 'Could not query Docker images.' }
    if (-not $localImage) {
        & $docker pull $image
        if ($LASTEXITCODE -ne 0) { throw 'Image pull failed. Configure Docker Desktop proxy/network settings and rerun.' }
    }
    # Keep this standalone service separate from the RAGFlow application stack.
    $serviceDir = Join-Path $env:LOCALAPPDATA 'RAGFlow\bge-m3-service'
    New-Item -ItemType Directory -Force -Path $serviceDir | Out-Null
    $composeFile = Join-Path $serviceDir 'compose.json'
    $config = @{ services = @{ 'bge-m3' = @{
        image = $image
        command = @('--model-id', '/model', '--pooling', 'cls', '--max-batch-tokens', "$MaxTokens",
            '--max-client-batch-size', '16', '--max-concurrent-requests', '16', '--auto-truncate')
        environment = @{ OMP_NUM_THREADS = '4' }
        volumes = @(@{ type = 'bind'; source = $ModelDir; target = '/model'; read_only = $true })
        ports = @("${Port}:80")
        mem_limit = '5g'
        cpus = 4
        restart = 'unless-stopped'
    } } }
    [IO.File]::WriteAllText($composeFile, ($config | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    & $docker compose -p ragflow-bge-m3 -f $composeFile up -d
    if ($LASTEXITCODE -ne 0) { throw "Service startup failed. Check available memory and whether port $Port is already in use." }

    Write-Host 'Waiting for model loading and warmup (up to 3 minutes)...'
    $baseUrl = "http://127.0.0.1:$Port"
    $ready = $false
    $deadline = (Get-Date).AddMinutes(3)
    do {
        & $curl --noproxy '*' --silent --fail --max-time 2 "$baseUrl/health" *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    if (-not $ready) {
        & $docker compose -p ragflow-bge-m3 -f $composeFile logs --tail 30
        throw 'Model did not become ready. Check the logs above and Docker memory allocation.'
    }
    $vectors = Invoke-RestMethod -Uri "$baseUrl/embed" -Method Post -ContentType 'application/json' `
        -Body '{"inputs":["A high efficiency power amplifier.","A document retrieval test."]}' -TimeoutSec 60
    if ($vectors.Count -ne 2 -or $vectors[0].Count -ne 1024 -or $vectors[1].Count -ne 1024) {
        throw 'Embedding smoke check failed: expected two 1024-dimensional vectors.'
    }
    Write-Host @"

BGE-M3 is ready. Embedding smoke check passed (2 x 1024).
RAGFlow provider: HuggingFace
Instance name: local-bge-m3
Model name: BAAI/bge-m3
Model type: embedding
API key: leave empty
Max tokens: $MaxTokens (longer inputs are truncated)
Base URL, Windows backend: $baseUrl
Base URL, Docker backend: http://host.docker.internal:$Port
For a WSL backend, replace 127.0.0.1 with the Windows gateway from: ip route show default
Recommended chunk size: 512 tokens; CPU embedding batch size: 4.
Compose file: $composeFile
Models are local; registration in your RAGFlow account is still required.
"@
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
