# MusicHub 多阶段 Dockerfile
# Stage 1：用 Node 构建 Vue 前端
# Stage 2：把前端构建产物复制到 Python 后端镜像，作为 FastAPI 静态资源

# ============================================================
# Stage 1：前端构建
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# 优先复制 package.json 和 lock 文件，利用 Docker 缓存
COPY frontend/package.json frontend/package-lock.json* ./

# 安装依赖（如果有 lock 文件用 npm ci，否则用 npm install）
RUN if [ -f package-lock.json ]; then \
        npm ci; \
    else \
        npm install; \
    fi

# 复制前端源码并构建
COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2：后端运行镜像
# ============================================================
FROM python:3.11-slim AS runtime

# 系统依赖：
#   - ffmpeg：mutagen 处理某些封面格式时需要
#   - tzdata：时区支持
#   - wget：healthcheck 用
#   - libxml2/libxslt：lxml 解析 HTML（URL 导入用）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tzdata \
        wget \
        ca-certificates \
        libxml2 \
        libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先复制 pyproject.toml 单独装依赖，利用缓存
COPY backend/pyproject.toml ./backend/
RUN pip install --no-cache-dir -e ./backend

# 再复制后端源码
COPY backend/ ./backend/

# 复制前端构建产物到后端的静态目录
COPY --from=frontend-builder /app/frontend/dist /app/backend/app/static

# 创建运行时目录（音乐输出 / 配置）
RUN mkdir -p /music /config

ENV PORT=5173 \
    MUSIC_DIR=/music \
    CONFIG_DIR=/config \
    LOG_LEVEL=INFO

EXPOSE 5173

# 启动命令
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "5173"]
