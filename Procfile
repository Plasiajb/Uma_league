web: python manage.py migrate && python manage.py collectstatic --noinput --clear && gunicorn uma_league.wsgi:application --preload --bind 0.0.0.0:$PORT
