FROM pytorch/pytorch:2.14.1-cuda12.6-cudnn9-runtime
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
# llama-cpp-python has no cu125/cu126 wheels for Python 3.12; the CUDA 12.4 ones
# work on the 12.6 base image (same major CUDA version)
ENV CUDA_VERSION_SHORT=cu124
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=all
# the base image ships Ubuntu's python 3.12 (PEP 668 marked as externally managed)
ENV PIP_BREAK_SYSTEM_PACKAGES=1
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
ENV FORCE_CUDA=1
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-provider \
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
