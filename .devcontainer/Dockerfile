# Development tools; the production API uses the separate root Dockerfile.
FROM python:3.11.16-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84 AS python
FROM node:24.19.0-bookworm@sha256:4196d66a565c6f195728d9952f161f4adfe2ad753052a08b7ec7f1c5a6bda42b
COPY --from=python /usr/local/ /usr/local/
ENV USE_LLM=0 PYTHONDONTWRITEBYTECODE=1 NEXT_TELEMETRY_DISABLED=1
CMD ["sleep", "infinity"]
