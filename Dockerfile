# Docker image for WTO Policy Support
FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -e .

# 数据目录 (挂载点)
RUN mkdir -p /app/data/cache /app/data/snapshots
VOLUME ["/app/data"]

# 默认: 拉新一次后启动 web UI
ENV PYTHONUNBUFFERED=1

# 启动时先拉新, 再 web UI
CMD ["sh", "-c", "wto-update && wto-web --server.port=${PORT:-8501} --server.address=0.0.0.0"]
