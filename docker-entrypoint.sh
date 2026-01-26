#!/bin/sh
set -e

# Wait for Postgres to be ready
# checks host "$DATABASE_HOST" on port "$DATABASE_PORT"
echo "Waiting for database connection..."
while ! nc -z $DATABASE_HOST $DATABASE_PORT; do   
  sleep 0.1
done
echo "Database started!"

echo "Applying database migrations..."
python manage.py migrate

exec "$@"