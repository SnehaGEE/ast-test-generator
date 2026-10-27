# One image serves both the React app and the API, e.g. on Render.

# 1. Build the React frontend.
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. Python API with the C and Java toolchains it runs programs with.
FROM python:3.11-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py ./
COPY src/ ./src/
COPY --from=frontend /frontend/dist ./frontend/dist

# Visitors' programs run as this unprivileged user, not as root.
RUN useradd --create-home branchlab
USER branchlab

ENV PYTHONUNBUFFERED=1 PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
