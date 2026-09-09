# Verified from the official library/python registry on 2026-09-09.
FROM python:3.11.16-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    USE_LLM=0
WORKDIR /app

# API lock includes the complete core dependency closure.
COPY requirements.api.txt ./
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.api.txt \
    && pip check

# .dockerignore admits runtime code; a reviewed snapshot must be mounted and pinned explicitly.
COPY . .
RUN groupadd --gid 10001 lexdomus \
    && useradd --uid 10001 --gid lexdomus --no-create-home lexdomus
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
