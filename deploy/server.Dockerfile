FROM continuumio/miniconda3:24.1.2-0
RUN apt-get update && apt-get -y upgrade \
  && apt-get install -y --no-install-recommends \
  git \
  libpq-dev \
  gcc \
  linux-libc-dev \
  libc6-dev \
  build-essential \
  make
RUN brew install node@20
RUN corepack enable
WORKDIR /usr/src/app
RUN pip install --progress-bar off --no-cache-dir 'torch~=2.2.0' torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-api
COPY src/swai_client/package.json swai_client/package.json
RUN TS_ROOT="swai_client/" make install-ts
COPY LICENSE .
COPY sh/ sh/
COPY src/swai/ swai/
COPY src/swai_server swai_server/
COPY src/swai_client swai_client/
RUN TS_ROOT="swai_client/" make ts-build
RUN python -m compileall .
COPY version.txt .
ARG PORT=8080
ARG CONFIG_PATH
COPY "${CONFIG_PATH}" config.json
ENV HOST=0.0.0.0
ENV PORT=${PORT}
ENV CONFIG_PATH=config.json
EXPOSE ${PORT}
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -u -m swai_server --dedicated"]
