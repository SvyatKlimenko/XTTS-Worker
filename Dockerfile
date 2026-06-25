FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

ENV PORT=8888 \
    XTTS_DIR=auto \
    LOG_DIR=auto \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    net-tools \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY start.sh /app/start.sh
COPY healthcheck.sh /app/healthcheck.sh
RUN chmod +x /app/start.sh /app/healthcheck.sh

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
    CMD /app/healthcheck.sh

CMD ["/app/start.sh"]
