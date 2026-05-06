FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.cache/huggingface \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common \
        ca-certificates \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        python3.11-distutils \
        python3-pip \
        espeak-ng \
        libsndfile1 \
        ffmpeg \
        git \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python3.11 -m pip install --upgrade pip \
    && python3.11 -m pip install --no-cache-dir -r requirements.txt

COPY handler.py .

# Pré-baixa pesos do Kokoro para PT-BR durante o build (CRÍTICO contra cold start).
# Idioma único deste worker — falha aqui significa que a versão da lib não tem PT
# e a imagem não deve subir silenciosamente.
RUN python3.11 -c "from kokoro import KPipeline; KPipeline(lang_code='p', repo_id='hexgrad/Kokoro-82M')"

# Activated only after the cache has been populated above: forces the HF Hub
# client to use local files at runtime, eliminating the 5 HEAD requests + the
# "unauthenticated requests" warning seen on every cold start.
ENV HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

CMD ["python3.11", "-u", "handler.py"]
