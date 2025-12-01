FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy and set up entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set Python path to include src directory
ENV PYTHONPATH=/app/src:/app

# Indicate this is running in Docker
ENV DOCKER_CONTAINER=true

EXPOSE 8001

CMD ["/app/entrypoint.sh"]