web: python manage.py migrate \
 && python manage.py createsuperuser --noinput || true \
 && python manage.py collectstatic --noinput \
 && gunicorn uma_league.wsgi:application --preload --bind 0.0.0.0:$PORT
