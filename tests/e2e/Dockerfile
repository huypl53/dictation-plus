FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    build-essential libportaudio2 wget unzip \
    && rm -rf /var/lib/apt/lists/*

# Download models in early layer (cached ~140MB)
RUN mkdir -p /models/vosk /models/piper

RUN wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip \
    -O /tmp/vosk-model.zip \
    && unzip -q /tmp/vosk-model.zip -d /models/vosk/ \
    && rm /tmp/vosk-model.zip

RUN wget -q https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx \
    -O /models/piper/en_US-lessac-medium.onnx \
    && wget -q https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json \
    -O /models/piper/en_US-lessac-medium.onnx.json

# Copy app (after model layer so code changes don't re-download)
COPY . /app
WORKDIR /app

# Install app and test dependencies
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir -e ".[dev]" websockets

ENV DICTATION_MODELS_DIR=/models

CMD ["python3", "-m", "pytest", "tests/e2e/test_e2e.py", "-v", "-s", "--tb=short"]
