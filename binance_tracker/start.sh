#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# 构建内置的 Vue 实时 K 线页面
if [[ ! -f "$ROOT_DIR/realtime_chart/dist/index.html" ]]; then
    echo "正在构建实时 K 线页面..."
    "$ROOT_DIR/realtime_chart/build.sh"
fi

# 检查 aiohttp 是否已安装，未安装时才安装整个项目
if ! python -c "import aiohttp" &>/dev/null; then
    echo "检测到缺少依赖，正在自动安装 pyproject.toml ..."
    python -m pip install -e . --quiet
else
    echo "依赖已满足，跳过安装"
fi

# 启动应用
exec python -m binance_tracker.main --network-mode domain "$@"