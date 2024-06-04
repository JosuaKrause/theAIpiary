# FROM python:3.11-bookworm
FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime
RUN apt-get update \
  && apt-get -y upgrade \
  && apt-get install -y --no-install-recommends \
  git \
  libpq-dev \
  gcc \
  linux-libc-dev \
  libc6-dev \
  build-essential \
  make
WORKDIR /usr/src/app
ENV CUDA_VERSION_SHORT=cu121
# FIXME remove with 311 image *****
# RUN apt-get update \
#   && apt-get install -y software-properties-common wget \
#   && wget https://developer.download.nvidia.com/compute/cuda/12.3.1/local_installers/cuda-repo-debian12-12-3-local_12.3.1-545.23.08-1_amd64.deb \
#   && dpkg -i cuda-repo-debian12-12-3-local_12.3.1-545.23.08-1_amd64.deb \
#   && cp /var/cuda-repo-debian12-12-3-local/cuda-*-keyring.gpg /usr/share/keyrings/ \
#   && add-apt-repository contrib \
#   && apt-get update \
#   && apt-get -y install cuda-toolkit-12-3
ENV PATH="/usr/local/nvidia/bin:${PATH}"
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=all
RUN conda update -y pip setuptools wheel conda filelock \
  && conda clean --all \
  && conda install -y python=3.11 pytorch=2.3.0 \
  && conda clean --all
# *****
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
# FIXME remove with 311 image *****
ENV FORCE_CUDA=1
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-worker
# && conda clean --all \
# && pip cache purge \
# && CUDACXX=/usr/local/cuda-12/bin/nvcc CMAKE_ARGS="-DLLAMA_CUBLAS=on -DCMAKE_CUDA_ARCHITECTURES=all-major" FORCE_CMAKE=1 \
# pip install llama-cpp-python --no-cache-dir --force-reinstall --upgrade
# *****
COPY LICENSE .
COPY sh/ sh/
COPY src/swai swai/
COPY src/swai_provider swai_provider/
RUN python -m compileall .
ENV VERSION_PATH version.txt
COPY version.provider.txt ${VERSION_PATH}
ARG SMIND_GRAPHS
ARG SMIND_CONFIG
COPY "${SMIND_CONFIG}" smind-config.json
COPY "${SMIND_GRAPHS}" graphs/
ENV ENV_FILE=/swai/provider.env
HEALTHCHECK --interval=30s --timeout=30s --start-period=20s --retries=3 CMD ["/bin/bash", "-l", "-c", "python -u -m scattermind --env ${ENV_FILE} --config smind-config.json healthcheck"]
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -u -m scattermind --env ${ENV_FILE} --boot --version-file ${VERSION_PATH} --config smind-config.json worker --graph graphs/"]
