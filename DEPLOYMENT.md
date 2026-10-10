# Deploying: Django hosting + PostgreSQL + Cloudflare R2 + WhiteNoise

A concrete checklist for this specific architecture. It assumes you've
already read [Getting started](README.md#getting-started) and run this
locally at least once — this is "what changes for production," not a
repeat of local setup.

**Which Django host?** This guide is written to work with any
Heroku-style Django PaaS (Render, Railway, Fly.io, PythonAnywhere, etc.)
— the artifacts it relies on (`Procfile`, `runtime.txt`, env vars,
`requirements.txt`) are read by all of them, just through slightly
different dashboards. Steps 3 and 5 are the only host-specific parts;
tell me which one you've picked and I'll give you the exact clicks.

---

## Pre-flight checklist

Before you touch a hosting dashboard, confirm locally:

- [ ] `python manage.py test` passes (all four apps)
- [ ] `pip-audit -r requirements.txt` comes back clean (or you've reviewed
      whatever it flags)
- [ ] You know which Django host you're using
- [ ] You have (or can create) a PostgreSQL database reachable from that host
- [ ] You have a Cloudflare account (R2 is available on the free plan)

## 1. Provision PostgreSQL

Most Django hosts either provision a Postgres instance for you (one
click, in the same dashboard as the app) or let you attach an external
one (Neon, Supabase, ElephantSQL, etc.). Either way, you end up with a
connection string in this shape:

```
postgres://USER:PASSWORD@HOST:5432/DBNAME
```

That whole string is your `DATABASE_URL` — see step 4. Nothing else in
this codebase needs to change for PostgreSQL specifically; `dj-database-url`
in `config/settings.py` already reads it (see README.md,
[Switching to PostgreSQL](README.md#switching-to-postgresql)).

## 2. Cloudflare R2

1. **Create the bucket**: Cloudflare dashboard → R2 → **Create bucket**.
   Name it something like `university-materials`. Location hint: pick
   whichever region is closest to your users — R2 doesn't charge for
   egress either way, but latency still benefits from proximity.
2. **Keep it private.** Don't turn on "Public access" for the bucket —
   this codebase generates its own signed, time-limited URLs
   (`AWS_QUERYSTRING_AUTH = True` in `config/settings.py`, already set),
   so a public bucket isn't needed and would work against the
   "downloads require login" behavior the app already has.
3. **Create an API token**: R2 → **Overview** → under **Account Details**,
   select **Manage** next to **API Tokens** → **Create Account API
   token** (or **User API token** — Account tokens survive even if your
   own user is later removed, which is usually what you want for a
   deployed app). Permission: **Object Read & Write**, scoped to just
   the one bucket you made. This gives you:
   - **Access Key ID** → `AWS_ACCESS_KEY_ID`
   - **Secret Access Key** → `AWS_SECRET_ACCESS_KEY`

   **Both are shown exactly once**, right after creation — copy them
   straight into your host's env var settings immediately. If you
   navigate away before copying the Secret Access Key, Cloudflare can't
   show it to you again; you'd delete that token and create a new one.
4. **Find your endpoint URL**: the R2 **Overview** page shows your
   Account ID directly (right sidebar / account details) — your
   endpoint is `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` with
   that ID substituted in → `AWS_S3_ENDPOINT_URL`. (If your bucket was
   created with a specific data jurisdiction — EU or FedRAMP — the
   endpoint has an extra segment, e.g. `https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`;
   most buckets aren't, so plain `.r2.cloudflarestorage.com` is right
   unless you deliberately chose one.)
5. **Bucket name** → `AWS_STORAGE_BUCKET_NAME` (exactly what you named
   it in step 1).
6. **Optional — a custom domain** (e.g. `files.yourschool.edu` instead
   of the raw `r2.cloudflarestorage.com` URL): R2 → your bucket →
   **Settings** → **Custom Domains**. If you set one up, put it in
   `AWS_S3_CUSTOM_DOMAIN` (just the domain, no `https://`). If you skip
   this, everything still works — file URLs just look like the raw R2
   endpoint instead of your own domain.
7. **CORS**: not required for this app as it stands — the PDF preview
   loads via a plain `<iframe src="...">`, which browsers allow
   cross-origin without CORS (CORS governs script-initiated requests
   like `fetch()`, not iframe navigation). You'd only need to add a CORS
   policy on the bucket if you later add JavaScript that fetches file
   bytes directly (e.g. a custom PDF.js viewer instead of the native
   browser one).

That's the whole R2 side. `config/settings.py` activates the R2 backend
automatically the moment `AWS_STORAGE_BUCKET_NAME` and
`AWS_S3_ENDPOINT_URL` are both set (see its comments right above
`STORAGES` and `CONTENT_SECURITY_POLICY` for exactly what that switches
on, including why the PDF-preview CSP rule updates itself too).

## 3. Choose your Django host

Whichever you pick, you're looking for the same handful of settings:

- **Build command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- **Start command**: `gunicorn config.wsgi:application` (already in `Procfile` — many hosts auto-detect this)
- **Release/pre-deploy command** (runs migrations before each new
  deploy goes live): `python manage.py migrate --noinput` (also
  already in `Procfile` as `release:` — Render, Railway, and
  Heroku-style hosts differ in whether they read this automatically or
  want it set separately in their dashboard; check whichever you use)
- **Python version**: `runtime.txt` pins `3.13.15` — hosts that read
  this file will match it automatically

Tell me which host once you've picked one and I'll walk through its
specific dashboard/CLI steps rather than speaking generically.

## 4. Environment variables

Set every one of these in your host's environment variable settings
(never commit them — `.env` stays local-only, per `.gitignore`).
`.env.example` documents each with more detail than this table.

| Variable | Set it to |
|---|---|
| `DJANGO_SECRET_KEY` | A fresh random value — **not** the one from your local `.env` — generate a new one for production: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | Your host's domain (e.g. `yourapp.onrender.com`), plus your custom domain once you have one |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://` + the same domain(s), e.g. `https://yourapp.onrender.com` |
| `DJANGO_BEHIND_PROXY` | `True` — virtually every Django-hosting PaaS terminates TLS at a proxy in front of your app (see the caveat in `config/settings.py` right above `SECURE_PROXY_SSL_HEADER` — worth actually reading once, not just pasting `True`) |
| `DATABASE_URL` | The Postgres connection string from step 1 |
| `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | From step 2 |
| `AWS_S3_CUSTOM_DOMAIN` | From step 2, only if you set one up |
| `MAX_MATERIAL_UPLOAD_MB` | `100`, or whatever your host's own request-size limits actually allow — check that separately, since a host-level proxy limit smaller than this will reject large uploads before Django ever sees them |
| `DJANGO_TIME_ZONE` | `Africa/Lagos` (default) or whatever fits your users |

## 5. Deploy

Push to whatever branch your host watches (or trigger a manual deploy).
Watch the build log for:
- `collectstatic` finding and hashing your CSS (confirms WhiteNoise will serve it)
- `migrate` running cleanly against the *production* database for the
  first time — this applies the same four `0001_initial` migrations
  you already generated and tested locally, now against Postgres

## 6. One-time setup on the deployed app

Run these against production — how you get a shell depends on your
host (most give you either a web-based console or a CLI like
`render exec` / `railway run` / `fly ssh console`):

```bash
python manage.py createsuperuser
```

Then, same manual step as local setup (README.md's Getting Started
covers why `createsuperuser` doesn't set our custom `role` field):

```bash
python manage.py shell -c "
from accounts.models import User
u = User.objects.get(username='YOUR_SUPERUSER_USERNAME')
u.role = User.Role.ADMIN
u.save()
"
```

Then log into `/admin/` on your live domain and seed at least one
Faculty/Department/Course/Session/Semester — see README.md,
[Seeding the catalog](README.md#seeding-the-catalog-your-first-faculty-department-course).

## 7. Verify it actually works

In roughly this order, on the live URL:

- [ ] Home page loads, static CSS is styled (not a plain unstyled page —
      confirms WhiteNoise)
- [ ] Register a test student account
- [ ] Log out, log back in
- [ ] As Admin, upload a real PDF at `/materials/upload/` — confirms
      R2 credentials are correct and the content-verification validator
      accepts a genuine file
- [ ] Open that material's detail page — the PDF should render in the
      inline preview. **If it doesn't**, open your browser's dev tools
      console: a Content-Security-Policy violation will name the exact
      blocked origin, which almost always means `AWS_S3_CUSTOM_DOMAIN`
      is set to something CSP isn't expecting, or R2 built the URL
      differently than the wildcard in `config/settings.py` assumes —
      see that file's comment above `_file_storage_origins`
- [ ] Download the material — confirms it streams correctly from R2
      through the app
- [ ] Bookmark it, then check `/bookmarks/`
- [ ] Hit `/materials/dashboard/` as Admin — counts should be non-zero
- [ ] Log in with a wrong password 5 times, then confirm even the
      *correct* password is briefly refused (django-axes working —
      see SECURITY.md, "Rate limit login")
- [ ] Try `/materials/upload/` as a Student (not Admin) — should be a
      403, not a crash
- [ ] Check response headers (dev tools → Network tab) for
      `Content-Security-Policy` and `Strict-Transport-Security` —
      confirms the security headers from SECURITY.md are actually live

## Troubleshooting

**`DisallowedHost` / 400 Bad Request** — your live domain isn't in
`DJANGO_ALLOWED_HOSTS` yet. Add it (comma-separated if you have more
than one).

**CSRF verification failed on login/register/upload** — same idea for
`DJANGO_CSRF_TRUSTED_ORIGINS`; it needs the full `https://domain`, not
just the bare domain.

**Redirect loop on every page** — `DJANGO_BEHIND_PROXY=True` was set on
a host that ISN'T actually stripping/overwriting the
`X-Forwarded-Proto` header, so Django can't tell the request is already
HTTPS and keeps "redirecting" it. Read the comment in
`config/settings.py` above `SECURE_PROXY_SSL_HEADER`, and confirm with
your specific host's docs.

**File uploads fail / 500 on upload** — almost always R2 credentials or
`AWS_S3_ENDPOINT_URL`. Double check the endpoint is the full
`https://<account_id>.r2.cloudflarestorage.com` URL (not just the
account ID), and that the API token's permission actually covers the
bucket you named in `AWS_STORAGE_BUCKET_NAME`.

**PDF preview blocked, everything else works** — see the CSP note in
the verification checklist above.

**Static files 404 / unstyled site** — `collectstatic` didn't run as
part of your build step; check your host's build command matches step 3.

## After you're live

- **Backups**: ask your Postgres provider what their backup story is —
  this codebase doesn't implement its own (blueprint section 21 calls
  for "database backups" as an infrastructure concern, not application
  code, and that's the right split: your DB provider almost certainly
  does this better than a hand-rolled script would).
- **Monitoring**: at minimum, watch your host's error logs for the
  first few days of real traffic. Nothing in this codebase currently
  sends errors anywhere (no Sentry/error-tracking integration) — worth
  adding once you're past initial launch, out of scope for this pass.
- **`pip-audit`**: already scheduled weekly in
  `.github/workflows/security.yml` once this is on GitHub — but that
  only catches known CVEs in dependencies, not application bugs.
