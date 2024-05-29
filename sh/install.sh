#!/usr/bin/env bash
#
# Copyright (c) 2024 Josua Krause - All Rights Reserved
#
# THE CONTENTS OF THIS PROJECT ARE PROPRIETARY AND CONFIDENTIAL.
# UNAUTHORIZED COPYING, TRANSFERRING OR REPRODUCTION OF THE CONTENTS OF
# THIS PROJECT, VIA ANY MEDIUM IS STRICTLY PROHIBITED.
#
# The receipt or possession of the source code and/or any parts thereof does
# not convey or imply any right to use them for any purpose other than the
# purpose for which they were provided to you.
#
# The software is provided "AS IS", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose and non infringement. In no event shall the
# authors or copyright holders be liable for any claim, damages or other
# liability, whether in an action of contract, tort or otherwise, arising from,
# out of or in connection with the software or the use or other dealings in the
# software.
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the software.
#
set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}" )/../" &> /dev/null

PYTHON="${PYTHON:-python}"
which ${PYTHON} > /dev/null
if [ $? -ne 0 ]; then
    PYTHON=python
fi

MAJOR=$(${PYTHON} -c 'import sys; print(sys.version_info.major)')
MINOR=$(${PYTHON} -c 'import sys; print(sys.version_info.minor)')
echo "${PYTHON} v${MAJOR}.${MINOR}"
if [ ${MAJOR} -eq 3 ] && [ ${MINOR} -lt 11 ] || [ ${MAJOR} -lt 3 ]; then
    echo "${PYTHON} version must at least be 3.11" >&2
    exit 1
fi

# see https://github.com/abetlen/llama-cpp-python?tab=readme-ov-file#installation-configuration

! read -r -d '' PY_TORCH_VERIFY <<'EOF'
import sys
import torch

def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    # if torch.cuda.is_available():
    if torch.backends.cudnn.enabled:
        return torch.device("cuda")
    return torch.device("cpu")

options = []
device_name = f"{get_device()}"
if device_name == "mps":
    options.append("-DLLAMA_METAL=on")
elif device_name == "cuda":
    options.append("-DLLAMA_CUDA=on")
elif device_name == "cpu":
    options.append("-DLLAMA_BLAS=ON")
    options.append("-DLLAMA_BLAS_VENDOR=OpenBLAS")
sys.stdout.write(" ".join(options))
sys.stdout.flush()
EOF

PYTORCH=
if ${PYTHON} -c 'import torch;assert torch.__version__.startswith("2.")' &>/dev/null 2>&1; then
    PYTORCH=$(${PYTHON} -c 'import torch;print(torch.__version__)')
else
    if [ ! $CI = "true" ] && command -v conda &>/dev/null 2>&1; then
        conda install -y pytorch torchvision torchaudio -c pytorch
    else
        ${PYTHON} -m pip install --progress-bar off torch torchvision torchaudio
    fi
fi
${PYTHON} -c 'import torch;print(torch.__version__)'

${PYTHON} -m pip install --progress-bar off "pip>=24.0"
if [ -z "${MODE}" ]; then
    REQUIREMENTS_PATH="${REQUIREMENTS_PATH:-requirements.txt}"
    ${PYTHON} -m pip install --progress-bar off --upgrade -r "${REQUIREMENTS_PATH}"
    ${PYTHON} -m pip install --progress-bar off --upgrade -r "requirements.dev.txt"

    source deploy/devmode.conf
    if [ ! -z "${DEVMODE}" ]; then
        echo "library dev mode active"

        QUICK_SERVER_PATH="../quick_server"
        REDIPY_PATH="../redipy"
        SMIND_PATH="../scattermind"
        ${PYTHON} -m pip uninstall -y quick-server redipy scattermind
        QUICK_SERVER_URL="git+https://github.com/JosuaKrause/quick_server.git"
        REDIPY_URL="git+https://github.com/JosuaKrause/redipy.git"
        SMIND_URL="git+https://github.com/JosuaKrause/scattermind.git"
        if [ -d "${QUICK_SERVER_PATH}" ]; then
            ${PYTHON} -m pip install --upgrade -e "${QUICK_SERVER_PATH}"
        else
            ${PYTHON} -m pip install --upgrade "${QUICK_SERVER_URL}@${QUICK_SERVER_BRANCH}"
        fi
        if [ -d "${REDIPY_PATH}" ]; then
            ${PYTHON} -m pip install --upgrade -e "${REDIPY_PATH}"
        else
            ${PYTHON} -m pip install --upgrade "${REDIPY_URL}@${REDIPY_BRANCH}"
        fi
        if [ -d "${SMIND_PATH}" ]; then
            ${PYTHON} -m pip install --upgrade -e "${SMIND_PATH}"
        else
            ${PYTHON} -m pip install --upgrade "${SMIND_URL}@${SMIND_BRANCH}"
        fi
    fi
elif [ "${MODE}" = "provider" ]; then
    REQUIREMENTS_PATH="${REQUIREMENTS_PATH:-requirements.provider.txt}"
    ${PYTHON} -m pip install --progress-bar off --no-cache-dir --upgrade -r "${REQUIREMENTS_PATH}"
elif [ "${MODE}" = "server" ]; then
    REQUIREMENTS_PATH="${REQUIREMENTS_PATH:-requirements.server.txt}"
    ${PYTHON} -m pip install --progress-bar off --no-cache-dir --upgrade -r "${REQUIREMENTS_PATH}"
elif [ "${MODE}" = "worker" ]; then
    REQUIREMENTS_PATH="${REQUIREMENTS_PATH:-requirements.worker.txt}"
    ${PYTHON} -m pip install --progress-bar off --no-cache-dir --upgrade -r "${REQUIREMENTS_PATH}"
else
    echo "invalid mode ${MODE}" >&2
    exit 2
fi

LLAMA_CMAKE_ARGS=$(${PYTHON} -c "${PY_TORCH_VERIFY}")
if [ ! -z "${FORCE_CUDA}" ]; then
    LLAMA_CMAKE_ARGS="-DLLAMA_CUDA=on"
fi

if grep -q "METAL" <<< "${LLAMA_CMAKE_ARGS}"; then
    ${PYTHON} -m pip install llama-cpp-python==0.2.68 --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/metal"
elif grep -q "CUDA" <<< "${LLAMA_CMAKE_ARGS}"; then
    CUDA_VERSION_SHORT="${CUDA_VERSION_SHORT:-cu121}"
    ${PYTHON} -m pip install llama-cpp-python==0.2.68 --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/${CUDA_VERSION_SHORT}"
else
    CMAKE_ARGS="${LLAMA_CMAKE_ARGS}" ${PYTHON} -m pip install --progress-bar off llama-cpp-python==0.2.68
fi
