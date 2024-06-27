FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-devel
# FROM nvidia/cuda:12.1.1-devel-ubuntu22.04
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
ENV CUDA_VERSION_SHORT=cu121
# ENV PATH="/root/miniconda3/bin:${PATH}"
# ARG PATH="/root/miniconda3/bin:${PATH}"
# RUN wget -nv \
#   https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
#   && mkdir /root/.conda \
#   && bash Miniconda3-latest-Linux-x86_64.sh -b \
#   && rm -f Miniconda3-latest-Linux-x86_64.sh
# RUN conda --version
# FIXME remove with 311 image *****
# RUN apt-get update \
#   && apt-get install -y software-properties-common wget \
#   && wget -nv https://developer.download.nvidia.com/compute/cuda/12.1.0/local_installers/cuda_12.1.0_530.30.02_linux.run \
#   && /bin/bash cuda_12.1.0_530.30.02_linux.run
# ENV PATH="/usr/local/nvidia/bin:${PATH}"
RUN nvcc --version
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=all
RUN conda update -y pip setuptools wheel conda \
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
