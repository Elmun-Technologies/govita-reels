# GoVita Reels Agency — bitta image: Claude Code CLI + HyperFrames + Python tool'lar
FROM node:22-bookworm-slim

ARG TARGETARCH
ARG CLAUDE_CODE_VERSION=2.1.327
ARG SUPERCRONIC_VERSION=v0.2.33

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Tashkent \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENCY_ROOT=/app \
    CHROMIUM_PATH=/usr/bin/chromium \
    HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium \
    PRODUCER_HEADLESS_SHELL_PATH=/usr/bin/chromium \
    HYPERFRAMES_CHROME_SANDBOX=0 \
    HYPERFRAMES_SKIP_SKILLS=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ffmpeg chromium \
        fonts-dejavu-core fonts-noto-color-emoji fonts-liberation \
        ca-certificates curl tzdata jq git util-linux sqlite3 procps \
    && rm -rf /var/lib/apt/lists/*

# supercronic — konteyner ichidagi cron (Mac arm64 va x86_64)
RUN arch="${TARGETARCH:-$(dpkg --print-architecture)}" \
    && curl -fsSL -o /usr/local/bin/supercronic \
       "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${arch}" \
    && chmod +x /usr/local/bin/supercronic

# Claude Code CLI (Max obuna: CLAUDE_CODE_OAUTH_TOKEN env orqali)
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" && npm cache clean --force

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# earshot — agentga "quloq" (ovoz/miks o'lchovi). CPU torch (~1.5GB). O'chirish: --build-arg WITH_EARSHOT=0
ARG WITH_EARSHOT=1
ARG EARSHOT_COMMIT=4ac3d2ac2b151e1c23376f9ce7f3047a17050013
RUN if [ "$WITH_EARSHOT" = "1" ]; then \
      pip3 install --no-cache-dir --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu && \
      pip3 install --no-cache-dir --break-system-packages \
        "earshot[mcp] @ git+https://github.com/Leonxlnx/earshot.git@${EARSHOT_COMMIT}" ; \
    fi

WORKDIR /app
# node_modules image ichida ham bo'lsin (bind-mount bo'lmagan holat uchun)
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
# Repo nusxasi (compose'da bind-mount ustidan yoziladi; bind-mount'siz ishlatish uchun)
COPY . .
RUN chown -R node:node /app

# Claude Code --dangerously-skip-permissions root ostida ishlamaydi → non-root user
USER node
ENV HOME=/home/node
RUN mkdir -p /home/node/.claude /home/node/.config/yt-dlp \
    && echo "--js-runtimes node" > /home/node/.config/yt-dlp/config

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["cron"]
