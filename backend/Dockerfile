# ---- Stage 1: whisper.cpp (local speech-to-text for captions) ----
FROM debian:bookworm-slim AS whisper
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates curl && rm -rf /var/lib/apt/lists/*
ARG WHISPER_REF=v1.7.6
RUN git clone --depth 1 --branch ${WHISPER_REF} https://github.com/ggml-org/whisper.cpp /src
WORKDIR /src
# Static, portable build (Render's CPUs may differ from the build machine's).
RUN cmake -B build -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DWHISPER_BUILD_TESTS=OFF \
        -DWHISPER_BUILD_EXAMPLES=ON -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j"$(nproc)" --config Release --target whisper-cli
# "base" model: fast on server CPUs, good enough for short captions.
ARG WHISPER_MODEL=ggml-base.en-q5_1.bin
RUN mkdir -p /models && curl -fsSL -o /models/${WHISPER_MODEL} \
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${WHISPER_MODEL}

# ---- Stage 1b: YouTube proof-of-origin token server (bgutil) ----
# yt-dlp asks this local server for the tokens YouTube now expects, which helps requests
# from cloud servers get through. Keep the version in step with the pip plugin below.
FROM node:22-bookworm-slim AS pot
ARG BGUTIL_VERSION=2.0.2
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${BGUTIL_VERSION} https://github.com/Brainicism/bgutil-ytdlp-pot-provider /bgutil
WORKDIR /bgutil/server
RUN npm ci && npx tsc && npm prune --omit=dev

# ---- Stage 2: the app ----
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl fonts-dejavu-core libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# Bold caption font (SIL Open Font License).
RUN mkdir -p /usr/share/fonts/truetype/archivo && curl -fsSL -o \
        /usr/share/fonts/truetype/archivo/ArchivoBlack-Regular.ttf \
        https://github.com/google/fonts/raw/main/ofl/archivoblack/ArchivoBlack-Regular.ttf
COPY --from=whisper /src/build/bin/whisper-cli /usr/local/bin/whisper-cli
# Node runtime + the built token server (started by start.sh in worker mode).
COPY --from=pot /usr/local/bin/node /usr/local/bin/node
COPY --from=pot /bgutil/server /opt/bgutil/server
# Deno: the JavaScript runtime yt-dlp recommends for YouTube's player challenges.
COPY --from=denoland/deno:bin-2.1.4 /deno /usr/local/bin/deno
COPY --from=whisper /models /models

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gta_clipper ./gta_clipper

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/tmp/hypecut \
    WHISPER_MODEL=/models/ggml-base.en-q5_1.bin \
    PORT=10000
EXPOSE 10000
COPY start.sh ./start.sh
RUN chmod +x ./start.sh
# Default: the API. The worker service runs `./start.sh worker` (see render.yaml).
CMD ["./start.sh", "api"]
