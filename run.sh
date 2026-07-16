#!/usr/bin/env bash
# Location-independent launcher for development and Raspberry Pi deployments.
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# An explicitly configured interpreter wins. Otherwise prefer a project virtual
# environment and finally fall back to the first Python 3 on PATH.
if [[ -n "${SDG_PYTHON:-}" ]]; then
    PYTHON_BIN="${SDG_PYTHON}"
elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
elif [[ -x "${ROOT_DIR}/venv/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/venv/bin/python"
else
    PYTHON_BIN="$(command -v python3 || true)"
fi

if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
    echo "Error: Python 3 was not found. Set SDG_PYTHON or create .venv." >&2
    exit 127
fi

export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" -m pi.main "$@"
