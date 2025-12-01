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
if [ "${CREATE_SUPERUSER:-false}" = "true" ]; then
    echo "Creating superuser..."
    python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
" || echo "Superuser creation skipped"
fi

# Show migration status for debugging
echo "Migration status:"
python manage.py showmigrations --plan || true

echo "Starting Django development server on 0.0.0.0:8001..."
exec python manage.py runserver 0.0.0.0:8001