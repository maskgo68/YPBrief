FROM node:22-slim AS web-build

WORKDIR /web

COPY web/package*.json ./
RUN npm ci

COPY web ./
RUN npm run build


FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV YPBRIEF_ENV_FILE=/app/data/key.env

WORKDIR /app

COPY pyproject.toml ./
COPY key.env.example ./key.env.example
COPY src ./src
COPY docker-entrypoint.sh ./docker-entrypoint.sh
COPY --from=web-build /web/dist ./web/dist

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[transcripts,llm]" \
    && chmod +x ./docker-entrypoint.sh

VOLUME ["/app/data", "/app/exports", "/app/logs"]

EXPOSE 48787

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "ypbrief_api.app:app", "--host", "0.0.0.0", "--port", "48787"]
