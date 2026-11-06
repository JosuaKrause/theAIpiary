#!/usr/bin/env bash
#
# Copyright (C) 2024 Josua Krause
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
if [ ${MAJOR} -eq 3 ] && [ ${MINOR} -lt 12 ] || [ ${MAJOR} -lt 3 ]; then
    echo "${PYTHON} version must at least be 3.12" >&2
    exit 1
fi

# see https://github.com/abetlen/llama-cpp-python?tab=readme-ov-file#installation-configuration

! read -r -d '' PY_TORCH_VERIFY <<'EOF'
import sys
import torch

def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    # a CUDA build of torch (also without a visible GPU, e.g., during
    # docker build); cudnn.enabled is True for CPU-only builds as well
    if torch.version.cuda is not None:
        return torch.device("cuda")
    return torch.device("cpu")

options = []
device_name = f"{get_device()}"
if device_name == "mps":
    options.append("-DGGML_METAL=on")
elif device_name == "cuda":
    options.append("-DGGML_CUDA=on")
elif device_name == "cpu":
    options.append("-DGGML_BLAS=ON")
    options.append("-DGGML_BLAS_VENDOR=OpenBLAS")
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
    LLAMA_CMAKE_ARGS="-DGGML_CUDA=on"
elif [ ! -z "${FORCE_CPU}" ]; then
    LLAMA_CMAKE_ARGS=
fi

LLAMA_CPP_PY_VERSION="0.3.19"
if grep -q "METAL" <<< "${LLAMA_CMAKE_ARGS}"; then
    ${PYTHON} -m pip install "llama-cpp-python==${LLAMA_CPP_PY_VERSION}" --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/metal"
elif grep -q "CUDA" <<< "${LLAMA_CMAKE_ARGS}"; then
    CUDA_VERSION_SHORT="${CUDA_VERSION_SHORT:-cu124}"
    if [ ! -z "${FORCE_BUILD_LLAMA}" ]; then
        CUDACXX=nvcc CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=all-major" FORCE_CMAKE=1 \
            ${PYTHON} -m pip install "llama-cpp-python==${LLAMA_CPP_PY_VERSION}" --no-cache-dir --force-reinstall --upgrade
    else
        ${PYTHON} -m pip install "llama-cpp-python==${LLAMA_CPP_PY_VERSION}" --prefer-binary --no-cache-dir --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/${CUDA_VERSION_SHORT}"
        # ${PYTHON} -m pip install "llama-cpp-python==${LLAMA_CPP_PY_VERSION}" --prefer-binary --no-cache-dir --extra-index-url "https://jllllll.github.io/llama-cpp-python-cuBLAS-wheels/AVX2/${CUDA_VERSION_SHORT}"
    fi
else
    CMAKE_ARGS="${LLAMA_CMAKE_ARGS}" ${PYTHON} -m pip install --progress-bar off "llama-cpp-python==${LLAMA_CPP_PY_VERSION}"
fi
