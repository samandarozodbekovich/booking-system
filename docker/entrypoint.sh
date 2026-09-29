#!/bin/sh
set -e

# Only the web container runs migrations and collectstatic,
# so worker and beat don't race with it.
if [ "$RUN_MIGRATIONS" = "1" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
fi

# Hand over to the container's command (gunicorn, celery worker, celery beat)
exec "$@"