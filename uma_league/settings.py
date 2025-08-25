
from pathlib import Path
import os, dj_database_url
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY","dev-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG","true").lower()=="true"
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "turf",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "uma_league.urls"
TEMPLATES = [{
    "BACKEND":"django.template.backends.django.DjangoTemplates",
    "DIRS":[BASE_DIR/"templates"],"APP_DIRS":True,
    "OPTIONS":{"context_processors":[
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "turf.contexts.promo_context", 
    ]},
}]
WSGI_APPLICATION = "uma_league.wsgi.application"
DATABASES = {"default":{"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"db.sqlite3"}}
if os.getenv("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600, ssl_require=False)
LANGUAGE_CODE="zh-hans"; TIME_ZONE="Europe/Stockholm"; USE_I18N=True; USE_TZ=True
STATIC_URL="/static/"; STATIC_ROOT=BASE_DIR/"staticfiles"; STATICFILES_DIRS=[BASE_DIR/"static"]
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"

import os

# 反向代理下让 Django 识别 HTTPS（Railway/Nginx 常用）
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 从环境变量读取可信域名，逗号分隔，必须带协议（https://）
_raw = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [x.strip() for x in _raw.split(",") if x.strip()]

# 静态文件
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# 让 WhiteNoise 提供压缩+带指纹的静态资源（生产环境推荐）
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

