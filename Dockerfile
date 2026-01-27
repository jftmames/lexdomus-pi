# Dockerfile — container del backend (Render/Fly/other)
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias del sistema si hiciera falta (pypdf/faiss, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Copiamos todo el repo (incluye data/indices)
COPY . /app

# Instala deps del proyecto + backend
# Si ya tienes requirements.txt en el repo, instala ambos:
RUN pip install --upgrade pip \
 && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi \
 && pip install -r requirements.api.txt

# Puerto por defecto de Uvicorn
EXPOSE 8000

ENV USE_LLM=0
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
