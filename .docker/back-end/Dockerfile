# Use a imagem oficial do Python 3.10.17
FROM python:3.10.17-slim

# Define o diretório de trabalho
WORKDIR /app

# Forçando output sem buffer (Error Handling?)
ENV PYTHONUNBUFFERED=1

# Indicate this is running in Docker
ENV DOCKER_CONTAINER=true

# Copia os arquivos do projeto para o contêiner
COPY requirements.txt .

# Instala os requerimentos no contêiner
RUN pip install --no-cache-dir -r requirements.txt