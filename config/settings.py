"""
Django settings for the University Centralized Learning Materials Platform.

Reads configuration from environment variables (see .env.example) so the
same codebase can run against local SQLite in development and a managed
PostgreSQL + cloud storage stack in production, without code changes.

This file also carries most of the project's security configuration —
cookies, headers, password hashing, login throttling, and CSP. See
SECURITY.md for the full rationale behind each choice below, mapped
against a standard hardening checklist; the comments here summarize
the "what", SECURITY.md has the "why" and what's out of scope.
"""
import os
import sys
import tempfile
from pathlib import Path

import dj_database_url
from django.contrib.messages import constants as message_constants
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# True while running `python manage.py test`. The WhiteNoise "manifest" static storage refuses to
# render {% static %} until `collectstatic` has run, which it hasn't in a test run (or in CI), so
# tests use Django's plain static storage instead. Production is unaffected.
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Core / secrets
# ---------------------------------------------------------------------------
# SECRET_KEY is read from the environment — see .env.example. The fallback
# string below is intentionally obviously-fake ("change-me") rather than a
# random-looking value, so a deployment that forgets to set the real one
# fails loudly/obviously instead of silently running on a guessable key.
# It is the ONLY secret-shaped value in this codebase; everything else
# (DB credentials, any future API keys) must go through os.environ /.env
# the same way — never hard-code a credential into a .py file. See
# SECURITY.md, "Hide API keys" / "Purge secrets from Git".
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DJANGO_DEBUG", True)

if not DEBUG:
    if not SECRET_KEY or SECRET_KEY in {
        "change-this-to-a-random-secret-key",
        "dev-insecure-secret-key-change-me",
    }:
        raise RuntimeError(
            "Set DJANGO_SECRET_KEY to a strong, unique secret in production."
        )
elif not SECRET_KEY:
    SECRET_KEY = "dev-insecure-secret-key-change-me"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# ---------------------------------------------------------------------------
# Transport security (SECURITY.md: "Force HTTPS", "Secure session cookies")
# ---------------------------------------------------------------------------
# DJANGO_BEHIND_PROXY: only turn this on if your host puts a load balancer
# / reverse proxy in front of Django that (a) terminates TLS itself and
# (b) is *guaranteed* to overwrite (not just append to) any inbound
# X-Forwarded-Proto header from the client. Getting this wrong lets a
# client spoof "https" and defeat SECURE_SSL_REDIRECT entirely — it's
# off by default for exactly that reason. Most free-tier PaaS hosts
# (Render, Railway, Fly.io, etc.) satisfy both conditions; a bare VPS
# with no reverse proxy in front of it does not, and should leave this
# unset.
if env_bool("DJANGO_BEHIND_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7  # 1 week; raise once you're confident HTTPS never breaks
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Cookies: HttpOnly stops JavaScript (including injected XSS payloads)
# from ever reading the session/CSRF cookie; Secure stops them being
# sent over plain HTTP; SameSite=Lax is the modern default CSRF defence
# (blocks the cookie being sent on most cross-site requests) that still
# allows normal top-level navigation (e.g. following a link from email).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True  # safe here: forms use Django's {% csrf_token %}, no JS ever needs to read this cookie
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Security (see SECURITY.md)
    "axes",  # login attempt throttling / lockout
    "csp",  # Content-Security-Policy header
    # Local apps
    "accounts",
    "academics",
    "materials",
    "bookmarks",
    "exams",  # Exam Preparation: past questions + summaries
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",  # must be LAST — axes' own requirement
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# DATABASE_URL, e.g. postgres://USER:PASSWORD@HOST:PORT/NAME — read from
# the environment only, never written here. Falls back to local SQLite
# so `manage.py runserver` works with zero setup. See SECURITY.md,
# "Expose only the public DB key" / "Enable row-level security" for why
# this single-connection-string model (rather than a client-exposed
# key + database-level policies) is the right shape for a Django app.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# AxesStandaloneBackend must come first: it's what actually enforces a
# lockout (raising PermissionDenied) once AXES_FAILURE_LIMIT is hit;
# ModelBackend does Django's normal username/password check.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Password hashing (SECURITY.md: "Hash passwords"). Django hashes every
# password automatically via set_password()/UserCreationForm — this list
# only controls *which algorithm*. Argon2 (the current OWASP-recommended
# default) is tried first for new hashes; PBKDF2 stays listed after it
# purely so any password hashed before this change still verifies
# correctly — Django tries each hasher in order until one matches, and
# transparently re-hashes with Argon2 next time that user logs in.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# ---------------------------------------------------------------------------
# Login throttling (SECURITY.md: "Rate limit login", "Add bot protection")
# ---------------------------------------------------------------------------
# Locks out the (username, IP) *combination* rather than either alone:
# locking by IP only would let one attacker's failed guesses lock out
# every other student on the same campus Wi-Fi/NAT; locking by username
# only would let anyone lock a specific student out of their own account
# just by failing their password from anywhere. Combining both is
# django-axes' own recommended default for exactly this reason.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours, after which the lockout expires on its own
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True  # a correct login clears that account's failure count

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Africa/Lagos")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
if TESTING:
    # Tests upload real files; keep them out of the project's media/ folder.
    MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="handoutvault-test-media-"))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# --- Cloudflare R2 (or any S3-compatible object storage) for uploaded
# materials — see DEPLOYMENT.md, "Cloudflare R2" for bucket setup and
# where each of these values comes from. Local disk (above) stays the
# default so `runserver` needs zero setup; R2 only activates once
# AWS_STORAGE_BUCKET_NAME + AWS_S3_ENDPOINT_URL are BOTH set, so a
# half-entered config fails obviously (uploads keep landing locally,
# nothing silently half-works against a misconfigured bucket).
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "")  # e.g. https://<account_id>.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")  # optional: a domain you've mapped to the bucket
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "auto")  # R2 has no regions; "auto" is its documented value
AWS_S3_ADDRESSING_STYLE = "path"  # R2's documented recommendation for S3-compatible clients
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_QUERYSTRING_AUTH = True     # generate signed, time-limited URLs — the bucket itself stays private
AWS_QUERYSTRING_EXPIRE = 3600   # seconds a signed preview/download URL stays valid (1 hour)
AWS_DEFAULT_ACL = None          # R2 doesn't use S3-style ACLs — leave unset, never "public-read"
AWS_S3_FILE_OVERWRITE = False   # don't silently replace a same-named file already in the bucket

# Never during tests: a developer with real R2 keys in .env must not have `manage.py test` upload to the live bucket.
USE_R2_STORAGE = bool(AWS_STORAGE_BUCKET_NAME and AWS_S3_ENDPOINT_URL) and not TESTING
if USE_R2_STORAGE:
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}

# ---------------------------------------------------------------------------
# Uploads (SECURITY.md: "Restrict file uploads")
# ---------------------------------------------------------------------------
MAX_MATERIAL_UPLOAD_MB = int(os.environ.get("MAX_MATERIAL_UPLOAD_MB", 100))
# Files larger than this are streamed to a temp file instead of held in RAM.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_MATERIAL_UPLOAD_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# Security headers (SECURITY.md: "Add security headers")
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True  # stop browsers "guessing" a different content-type than we set
SECURE_REFERRER_POLICY = "same-origin"  # don't leak full URLs to third-party resources
# SAMEORIGIN, not DENY: other websites still can't frame this one (clickjacking protection), but
# the handout page may frame this site's OWN files - the PDF preview <iframe> - when materials are
# served from this domain (local disk). With DENY, every locally-served preview was blocked.
X_FRAME_OPTIONS = "SAMEORIGIN"

# Content-Security-Policy — django-csp 4.x's dict-based config format;
# if you're on django-csp 3.x, translate this into the individual
# CSP_DEFAULT_SRC / CSP_SCRIPT_SRC / ... settings it expects instead
# (check `python -c "import csp; print(csp.__version__)"`).
#
# script-src has NO 'unsafe-inline' — the one directive that actually
# matters against XSS, since it's what would stop an injected
# <script> tag from executing. style-src does allow 'unsafe-inline'
# because Bootstrap's bundled JS (collapse/dropdown) sets inline
# `style.height` etc. directly during its open/close transitions; every
# *authored* inline style="" in this project's own templates was
# removed instead (see static/css/style.css) so this is the smallest
# allowance that keeps the UI working, not a blanket exemption.
# Origins the PDF-preview <iframe> (materials/material_detail.html) is
# allowed to load from — just 'self' while files are served from local
# disk; once USE_R2_STORAGE is on (above), this also allows wherever R2
# actually serves the file from. If a preview doesn't load after
# deploying, open your browser's console: a CSP violation names the
# exact blocked origin, which is the one to add here. AWS_S3_CUSTOM_DOMAIN
# gives an exact match; without one, boto3/django-storages builds R2 URLs
# as https://<account_id>.r2.cloudflarestorage.com/<bucket>/... (the
# path-style addressing requested above) — the wildcard covers that and
# the virtual-hosted-style alternative (https://<bucket>.<account_id>...)
# in case that's ever what you see instead.
_file_storage_origins = []
if USE_R2_STORAGE:
    if AWS_S3_CUSTOM_DOMAIN:
        _file_storage_origins.append(f"https://{AWS_S3_CUSTOM_DOMAIN}")
    else:
        _file_storage_origins.append("https://*.r2.cloudflarestorage.com")

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "https://cdnjs.cloudflare.com"],
        "style-src": ["'self'", "https://cdnjs.cloudflare.com", "https://fonts.googleapis.com", "'unsafe-inline'"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "img-src": ["'self'", "data:", *_file_storage_origins],
        "connect-src": ["'self'"],
        "frame-src": ["'self'", *_file_storage_origins],  # the PDF preview <iframe>
        "frame-ancestors": ["'self'"],  # same idea as X_FRAME_OPTIONS above
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    }
}

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Map Django's message levels to Bootstrap 5 alert classes for templates.
MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}
