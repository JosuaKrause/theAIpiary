# Debian trixie with Python 3.11, the version the server runs on (the pinned
# numpy 1.26 has no wheels past 3.12)
FROM python:3.11-slim-trixie
RUN apt-get update \
  && apt-get -y upgrade \
  && apt-get install -y --no-install-recommends \
  git \
  libpq-dev \
  gcc \
  linux-libc-dev \
  libc6-dev \
  build-essential \
  make \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /usr/src/app
RUN pip install --progress-bar off --no-cache-dir 'torch==2.3.0' torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
ENV FORCE_CPU=1
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-server \
  && pip cache purge
COPY LICENSE .
COPY sh/ sh/
COPY src/swai/ swai/
COPY src/swai_server swai_server/
COPY buildtmp_server/build build/
ENV UI_PATH=build/
RUN python -m compileall .
ENV VERSION_PATH=version.txt
COPY version.server.txt ${VERSION_PATH}
ARG PORT=8080
ARG CONFIG_PATH
COPY "${CONFIG_PATH}" config.json
ENV HOST=0.0.0.0
ENV PORT=${PORT}
ENV CONFIG_PATH=config.json
ENV HISTORY_PATH=/swai
ENV ENV_FILE=/swai/server.env
EXPOSE ${PORT}
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -u -m swai_server --dedicated --env ${ENV_FILE}"]
