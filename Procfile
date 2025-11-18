web: alembic upgrade head && gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120
worker: celery -A app.tasks.celery_main worker --loglevel=info --concurrency=2
release: alembic upgrade head
