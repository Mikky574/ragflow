#!/usr/bin/env bash
# Run the API and ingestion worker from this checkout; dependencies run in Docker.
set -euo pipefail
cd "$(dirname "$0")/../.."
venv="${RAGFLOW_VENV:-$PWD/.venv}"
if [[ ! -x "$venv/bin/python" ]]; then
    echo "Missing Python environment: $venv. See docs/python-docker-development.zh.md" >&2
    exit 1
fi
if [[ ! -f conf/local.service_conf.yaml ]]; then
    echo "Missing conf/local.service_conf.yaml. Follow the development guide first." >&2
    exit 1
fi
export PATH="$venv/bin:$PATH"
export PYTHONPATH="$PWD"
export DEVICE=cpu
export DOC_ENGINE=elasticsearch
export DB_TYPE=mysql
export API_PROXY_SCHEME=python
export NLTK_DATA="${NLTK_DATA:-$PWD/ragflow_deps/nltk_data}"
export DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-2}"
export EMBEDDING_BATCH_SIZE="${EMBEDDING_BATCH_SIZE:-4}"
python -c 'from api.db.db_models import init_database_tables; init_database_tables()'
PY=python bash tools/scripts/run_migrations.sh --config conf/local.service_conf.yaml
pids=()
cleanup() {
    for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
    wait || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
python api/ragflow_server.py &
pids+=("$!")
python rag/svr/task_executor.py -i local_0 -t common &
pids+=("$!")
wait -n "${pids[@]}"
