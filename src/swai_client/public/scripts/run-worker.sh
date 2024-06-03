#!/usr/bin/env bash

HAS_CUDA=1
if ! command -v nvidia-smi &> /dev/null; then
    HAS_CUDA=
fi

HAS_DOCKER=1
if ! command -v docker &> /dev/null; then
    HAS_DOCKER=
fi

if [ -z "${HAS_CUDA}" ] || [ -z "${HAS_DOCKER}" ]; then
    if [ -z "${HAS_CUDA}" ]; then
        echo "could not find cuda. please make sure it is installed on the system!"
    fi
    if [ -z "${HAS_DOCKER}" ]; then
        echo "could not find docker. please make sure it is installed on the system!"
    fi
    exit 1
fi

BASE=aipiary
mkdir -p "${BASE}"
cd "${BASE}"

DOCKER_COMPOSE="docker-compose.yml"
if [ ! -f "${DOCKER_COMPOSE}" ]; then
    curl https://www.theaipiary.com/scripts/docker-compose.yml -o "${DOCKER_COMPOSE}"
fi

AIPIARY_ENV="userdata/swai/provider.env"
if [ ! -f "${AIPIARY_ENV}" ]; then
    read -p "AIpiary user name (email): " AIPIARY_USER
    read -p "AIpiary worker token: " AIPIARY_WORKER_TOKEN
    mkdir -p $(dirname "${AIPIARY_ENV}")
    echo "AIPIARY_API_URL='https://www.theaipiary.com/'" > "${AIPIARY_ENV}"
    echo "AIPIARY_USER='${AIPIARY_USER}'" >> "${AIPIARY_ENV}"
    echo "AIPIARY_WORKER_TOKEN='${AIPIARY_WORKER_TOKEN}'" >> "${AIPIARY_ENV}"
fi

docker compose -f "${DOCKER_COMPOSE}" up || echo "done $?"
