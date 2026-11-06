FROM pytorch/pytorch:2.14.1-cuda12.6-cudnn9-devel
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
  wget \
  gcc-11 \
  g++-11
WORKDIR /usr/src/app
ENV CUDA_VERSION_SHORT=cu125
# FIXME remove with 311 image *****
RUN nvcc --version
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=all
RUN conda update -y pip setuptools wheel conda \
  && conda clean --all \
  && conda install -y python=3.11 \
  && conda clean --all
# *****
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
# FIXME remove with 311 image *****
ENV FORCE_CUDA=1
ENV FORCE_BUILD_LLAMA=
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-worker \
  && conda clean --all \
  && pip cache purge
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
ENV LLAMA_CPP_LIB=/opt/conda/lib/python3.11/site-packages/llama_cpp/libllama.so
HEALTHCHECK --interval=30s --timeout=30s --start-period=20s --retries=3 CMD ["/bin/bash", "-l", "-c", "python -u -m scattermind --env ${ENV_FILE} --config smind-config.json healthcheck"]
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -u -m scattermind --env ${ENV_FILE} --boot --version-file ${VERSION_PATH} --config smind-config.json worker --graph graphs/ --max-task-retries 2"]
