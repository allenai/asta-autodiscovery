#!/bin/bash
exec \
    gunicorn \
    --workers 10 \
    --timeout 0 \
    --bind 0.0.0.0:8000 \
    --enable-stdio-inheritance \
    --access-logfile - \
    --reload \
    'app:create_app()'
