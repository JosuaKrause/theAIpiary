FROM continuumio/miniconda3:24.1.2-0
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
RUN pip install --progress-bar off --no-cache-dir 'torch==2.3.0' torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-provider
COPY LICENSE .
COPY sh/ sh/
COPY src/swai/ swai/
COPY src/swai_provider swai_provider/
RUN python -m compileall .
COPY version.txt .
ARG SMIND_GRAPHS
ARG SMIND_CONFIG
COPY "${SMIND_CONFIG}" smind-config.json
COPY "${SMIND_GRAPHS}" graphs/
ENV SMIND_CFG=smind-config.json
ENV GRAPH_PATH=graphs/
ENV CONFIG_PATH=-
ENV VERSION_PATH=version.txt
EXPOSE ${PORT}
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD [". /swai/provider.env && python -u -m swai_provider --dedicated"]
