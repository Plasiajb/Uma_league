from pathlib import Path
import os, dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY","dev-secret-key")

# --- 智能判断 DEBUG 模式 ---
# 只有在 Railway 上明确设置了 DJANGO_DEBUG=false 时，才关闭 DEBUG
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() != "false"

ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages",
    "django.contrib.staticfiles", 
    "cloudinary_storage",
    "turf",
    "cloudinary",
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

DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"


# --- 静态文件 (Static) 和媒体文件 (Media) 的简化配置 ---

# 静态文件 (由开发者提供，随代码部署)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# 推荐使用 WhiteNoise 的专用存储后端，性能更好
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# 媒体文件 (由用户上传，动态内容)
MEDIA_URL = '/media/'

# --- 智能判断使用哪个存储后端 (更简洁的版本) ---
# 如果 CLOUDINARY_URL 环境变量存在 (即在线上环境)
if 'CLOUDINARY_URL' in os.environ:
    # 生产环境：使用 Cloudinary
    # django-cloudinary-storage 会自动从环境变量中读取所有密钥，无需额外配置
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
else:
    # 本地开发环境：使用本地文件系统
    MEDIA_ROOT = BASE_DIR / 'media'


# --- 其他生产环境配置 ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
_raw = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [x.strip() for x in _raw.split(",") if x.strip()]