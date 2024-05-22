FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-devel
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
RUN conda update -n base -c defaults conda \
  && conda install -y python=3.11
RUN conda install pytorch==2.3.0 torchvision torchaudio -c pytorch
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-worker
COPY LICENSE .
COPY sh/ sh/
COPY src/swai swai/
COPY src/swai_provider swai_provider/
RUN python -m compileall .
COPY version.txt .
ARG SMIND_GRAPHS
ARG SMIND_CONFIG
COPY "${SMIND_CONFIG}" smind-config.json
COPY "${SMIND_GRAPHS}" graphs/
HEALTHCHECK --interval=30s --timeout=30s --start-period=20s --retries=3 CMD ["/bin/bash", "-l", "-c", "python -u -m scattermind --config smind-config.json healthcheck"]
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD [". /swai/.env_provider && python -u -m scattermind --boot --version-file version.txt --config smind-config.json worker --graph graphs/"]
