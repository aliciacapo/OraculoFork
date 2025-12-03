#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

echo "=== Django Auth Service Starting ==="

# Debug: Show critical environment variables
echo "Environment variables check:"
echo "  JWT_SECRET_KEY: ${JWT_SECRET_KEY:0:20}..." 
echo "  INTERNAL_AUTH_TOKEN: ${INTERNAL_AUTH_TOKEN:0:20}..."
echo "  DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:0:20}..."
echo "  DB_HOST: ${DB_HOST:-not_set}"

# Wait for database
echo "Waiting for database at ${DB_HOST:-db}:${DB_PORT:-5432}..."
while ! pg_isready -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}" > /dev/null 2>&1; do
    echo "Database not ready, waiting..."
    sleep 2
done
echo "✓ Database is ready!"

# Change to Django project directory
cd /app/src/django_auth

# Run Django migrations
echo "Running Django migrations..."
python manage.py migrate --noinput

# Collect static files (skip if fails, not critical for development)
echo "Collecting static files..."
python manage.py collectstatic --noinput || echo "Static files collection skipped"

# Create superuser if environment variable is set
CREATE_SUPERUSER=${CREATE_SUPERUSER:-false}
if [ "$CREATE_SUPERUSER" = "true" ]; then
    echo "[entrypoint] CREATE_SUPERUSER=true; attempting to create admin user (idempotent)..."
    
    DJANGO_SUPERUSER_USERNAME=${DJANGO_SUPERUSER_USERNAME:-admin}
    DJANGO_SUPERUSER_EMAIL=${DJANGO_SUPERUSER_EMAIL:-admin@example.com}
    DJANGO_SUPERUSER_PASSWORD=${DJANGO_SUPERUSER_PASSWORD:-}
    
    if [ -z "$DJANGO_SUPERUSER_PASSWORD" ]; then
        echo "[entrypoint][warning] DJANGO_SUPERUSER_PASSWORD is empty. Will not create superuser." >&2
        echo "[entrypoint][warning] Set DJANGO_SUPERUSER_PASSWORD in environment to enable superuser creation." >&2
    else
        echo "[entrypoint] Creating superuser with username: $DJANGO_SUPERUSER_USERNAME"
        python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
username = '$DJANGO_SUPERUSER_USERNAME'
email = '$DJANGO_SUPERUSER_EMAIL'
password = '$DJANGO_SUPERUSER_PASSWORD'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print('[entrypoint] Superuser created:', username)
else:
    print('[entrypoint] Superuser already exists:', username)
" || echo "[entrypoint][error] Superuser creation failed"
    fi
else
    echo "[entrypoint] CREATE_SUPERUSER is not true; skipping superuser creation."
fi


# Show migration status for debugging
echo "Migration status:"
python manage.py showmigrations --plan || true

echo "Starting Django development server on 0.0.0.0:8001..."
exec python manage.py runserver 0.0.0.0:8001
