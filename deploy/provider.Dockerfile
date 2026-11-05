FROM pytorch/pytorch:2.14.1-cuda12.6-cudnn9-runtime
# FROM continuumio/miniconda3:24.1.2-0
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
ENV CUDA_VERSION_SHORT=cu125
# FIXME remove with 311 image *****
ENV PATH="/usr/local/nvidia/bin:${PATH}"
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=all
RUN conda update -y pip setuptools wheel conda filelock \
  && conda clean --all \
  && conda install -y python=3.11 \
  && conda clean --all
# *****
# RUN pip install --progress-bar off --no-cache-dir 'torch==2.3.0' torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
# FIXME remove with 311 image *****
ENV FORCE_CUDA=1
# *****
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-provider \
  && conda clean --all \
  && pip cache purge
COPY LICENSE .
COPY sh/ sh/
COPY src/swai/ swai/
COPY src/swai_provider swai_provider/
RUN python -m compileall .
ENV VERSION_PATH=version.txt
COPY version.provider.txt ${VERSION_PATH}
ARG SMIND_GRAPHS
ARG SMIND_CONFIG
COPY "${SMIND_CONFIG}" smind-config.json
COPY "${SMIND_GRAPHS}" graphs/
ENV SMIND_CFG=smind-config.json
ENV GRAPH_PATH=graphs/
ENV CONFIG_PATH=-
ENV ENV_FILE=/swai/provider.env
EXPOSE ${PORT}
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -u -m swai_provider --env ${ENV_FILE}"]
