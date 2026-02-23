FROM python:3.12-slim

WORKDIR /app

# Instala dependências primeiro (cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY app/ ./app/

# Cria pasta de uploads (será sobrescrita pelo volume)
RUN mkdir -p /uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]
