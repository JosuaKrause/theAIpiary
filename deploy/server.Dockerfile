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
WORKDIR /usr/src/app
RUN pip install --progress-bar off --no-cache-dir 'torch~=2.2.0' torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-api
COPY LICENSE .
COPY sh/ sh/
COPY src/swai/ swai/
COPY src/swai_server swai_server/
COPY buildtmp_server/build build/
ENV UI_PATH=build/
RUN python -m compileall .
COPY version.txt .
ARG PORT=8080
ARG CONFIG_PATH
COPY "${CONFIG_PATH}" config.json
ENV HOST=0.0.0.0
ENV PORT=${PORT}
ENV CONFIG_PATH=config.json
ENV HISTORY_PATH=/swai
EXPOSE ${PORT}
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -u -m swai_server --dedicated"]
