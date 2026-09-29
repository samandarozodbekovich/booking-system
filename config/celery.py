import os

from celery import Celery

# Celery runs as a separate process, so it must load Django settings itself.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
# Read every setting that starts with CELERY_ from settings.py.
app.config_from_object("django.conf:settings", namespace="CELERY")
# Find tasks.py in every installed app.
app.autodiscover_tasks()