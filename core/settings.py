"""
Django settings for core project (ChayReview).
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    'accounts',
    'restaurants',
    'reviews',
]

if env.bool("USE_CLOUDINARY", default=False):
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# Mặc định dùng SQLite khi phát triển local (miễn phí, không cần cài gì thêm).
# Khi deploy free (Render/Railway...) chỉ cần set biến môi trường DATABASE_URL
# trỏ tới Postgres free-tier (vd: Neon.tech, Supabase).

DATABASES = {
    'default': env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization

LANGUAGE_CODE = 'vi'

TIME_ZONE = 'Asia/Ho_Chi_Minh'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images) - phục vụ qua Whitenoise, hoàn toàn free
# https://whitenoise.readthedocs.io/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (ảnh món ăn, ảnh review do người dùng upload)
# Local dev: lưu trong thư mục media/. Production free: dùng Cloudinary
# (set USE_CLOUDINARY=True + CLOUDINARY_URL trong .env) vì hosting free
# (Render...) không giữ lại file khi redeploy.

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

if env.bool("USE_CLOUDINARY", default=False):
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    CLOUDINARY_STORAGE = {
        'CLOUDINARY_URL': env("CLOUDINARY_URL", default=""),
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Google Analytics (free) - để trống nếu chưa có tài khoản, site vẫn chạy bình thường.
GA_MEASUREMENT_ID = env("GA_MEASUREMENT_ID", default="")

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'restaurants:home'
LOGOUT_REDIRECT_URL = 'restaurants:home'
