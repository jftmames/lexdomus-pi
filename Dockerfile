# Dockerfile
FROM python:3.10-slim

# 1. Instalar utilidades del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Configurar directorio de trabajo
WORKDIR /app

# 3. Copiar y cachear dependencias (esto acelera builds futuros)
COPY requirements.txt .
COPY requirements.api.txt .

# 4. Instalar dependencias (unimos ambos archivos)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements.api.txt

# 5. Copiar TODO el código del proyecto (api, app, data, indices, verdiktia, etc.)
COPY . .

# 6. Exponer puerto (Render inyecta PORT automáticamente, pero esto es buena práctica)
EXPOSE 8000

# 7. Comando de arranque: usa la variable de entorno PORT de Render
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
