FROM python:3.12-slim

WORKDIR /app

# Dependencias de sistema para processamento de PDF e compilacao
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias primeiro (aproveita cache do Docker em rebuilds)
COPY requirements.txt .

# Instalar PyTorch CPU-only antes do resto (evita baixar versao CUDA desnecessaria)
RUN pip install --no-cache-dir \
    torch>=2.5.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Instalar demais dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo-fonte (exceto o que esta em .dockerignore)
COPY . .

EXPOSE 8501

# healthcheck simples para saber quando o app esta pronto
HEALTHCHECK CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
