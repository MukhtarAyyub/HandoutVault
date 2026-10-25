# University Materials Platform

A centralized web application for university students to browse, search,
preview, download, and bookmark lecture materials — with a simple Admin
side for uploading and organizing them. This is the Phase 1 MVP from the
project blueprint: Python, Django, PostgreSQL (SQLite for local dev),
Admin and Student roles only, built to run on free-tier cloud resources.

> **Looking for something specific?** Jump to [Getting started](#getting-started),
> [Seeding the catalog](#seeding-the-catalog-your-first-faculty-department-course),
> [Environment variables](#environment-variables), [Running the tests](#running-the-tests),
> [Switching to PostgreSQL](#switching-to-postgresql), or [Swapping in cloud storage](#swapping-in-cloud-storage).
> **Deploying?** Skip straight to **[DEPLOYMENT.md](DEPLOYMENT.md)** — a concrete
> checklist for Django hosting + PostgreSQL + Cloudflare R2 + WhiteNoise.
> **For security** — cookies, headers, login throttling, file-upload
> validation, and more — see [SECURITY.md](SECURITY.md), which maps every hardening
> measure in this codebase to exactly where it lives.

---

## Contents

1. [What's built](#whats-built)
2. [Tech stack](#tech-stack)
3. [Project structure](#project-structure)
4. [Getting started](#getting-started)
5. [Seeding the catalog](#seeding-the-catalog-your-first-faculty-department-course)
6. [Environment variables](#environment-variables)
7. [Running the tests](#running-the-tests)
8. [How file uploads work](#how-file-uploads-work)
9. [Switching to PostgreSQL](#switching-to-postgresql)
10. [Swapping in cloud storage](#swapping-in-cloud-storage)
11. [Deployment](#deployment) *(pointer — full checklist is [DEPLOYMENT.md](DEPLOYMENT.md))*
12. [Design notes](#design-notes)
13. [What's intentionally not built yet](#whats-intentionally-not-built-yet)
14. [Troubleshooting](#troubleshooting)
15. [Deployment](DEPLOYMENT.md) *(separate file — the concrete, step-by-step production checklist)*
16. [Security](SECURITY.md) *(separate file — cookies, headers, login throttling, file validation, and a full checklist mapping)*

---

## What's built

**Everyone (no account needed)**
- Browse the catalog: Faculty → Department → Course
- Search materials by course code, title, or topic
- Filter by faculty, level, semester, session, and file type

**Students** (register at `/accounts/register/`)
- Everything above, plus:
- **Exam Preparation** (`/exam-prep/`, login required): browse and download **past questions** and
  **summaries**, filed under the same faculty / department / course as the handouts. A summary can
  be linked to the handout it summarises and then appears on that handout's page
- Download materials (every download is logged)
- Preview PDFs in the browser before downloading
- Bookmark materials and view them later at `/bookmarks/`

**Admins** (created via `createsuperuser` or promoted in `/admin/`)
- Everything above, plus:
- Upload, edit, and delete materials at `/materials/upload/`
- Manage the Faculty/Department/Course/Session/Semester catalog and
  student accounts via Django's built-in admin site at `/admin/`
- Add, edit and delete **past questions** and **summaries** at `/exam-prep/<past-questions|summaries>/add/`
  (Admin only; students can't upload)
- A small stats dashboard at `/materials/dashboard/` (student/course/
  material/download totals, recent uploads and downloads)

This intentionally stops at the blueprint's **Phase 1 MVP** (its section
18). Advanced search engines, download-history pages, material
versioning, notifications, and the AI summary features are Phase 2/3 —
see [What's intentionally not built yet](#whats-intentionally-not-built-yet).

## Tech stack

| Layer      | Choice                                            |
|------------|----------------------------------------------------|
| Backend    | Python 3.12, Django 5.1                            |
| Database   | PostgreSQL in production, SQLite for local dev      |
| Frontend   | Django Templates, one hand-written "Liquid Glass" stylesheet and about 100 lines of JavaScript. No frameworks, no CDN, no web fonts (system fonts) |
| File storage | Local disk in dev; pluggable — see [cloud storage](#swapping-in-cloud-storage) |
| Static files | WhiteNoise (no separate CDN/nginx step needed)   |
| Auth       | Django's built-in auth, custom `User` model with a `role` field |
| Security   | Argon2 password hashing, django-axes (login throttling), django-csp — see [SECURITY.md](SECURITY.md) |

No React, no build step, no Node — matching the blueprint's call for the
frontend to stay Django Templates + Bootstrap for the MVP.

## Project structure

```
university_materials/
├── manage.py
├── requirements.txt
├── .env.example          # copy to .env and fill in
├── config/                # project-wide settings, root URLs
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py             # for gunicorn/production
│   └── asgi.py
├── accounts/               # custom User (Admin/Student), register/login/logout
├── academics/               # Faculty, Department, Course, Session, Semester
├── materials/               # Material, Download, upload/search/preview views
├── bookmarks/                # student bookmarks
├── exams/                    # Exam Preparation: past questions + summaries (models, views, forms, tests)
├── templates/                # one subfolder per app, plus base.html, home.html and partials/ (icons, form field, course switcher)
└── static/css/style.css       # the whole design system in one file
```

Every `models.py`, `views.py`, `forms.py`, `urls.py`, and `admin.py` in
the four apps opens with a docstring explaining that file's role and any
non-obvious design decisions — read those first when getting oriented;
this README covers the "how to run it" side, the docstrings cover the
"why it's built this way" side.

## Getting started

Requires Python 3.11+.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# open .env and set DJANGO_SECRET_KEY at minimum — everything else has
# a working default for local development (SQLite, DEBUG=True)

# 4. Create the database tables
python manage.py makemigrations
python manage.py migrate

# 5. Create your Admin account
python manage.py createsuperuser
# (this is the ONLY way to create an Admin — the public /accounts/register/
# form always creates a Student account, by design)

# 6. Run it
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`. Log into `/admin/` with the superuser
you just created — that account already has `role=admin` and full
access to `/materials/upload/` and `/materials/dashboard/` too, since
`createsuperuser` sets `is_staff`/`is_superuser` directly and our own
`role` field defaults to `admin` for any user with `is_staff=True`
created this way... actually — **one manual step**: `createsuperuser`
doesn't know about our custom `role` field, so it leaves it at the
model default of `student`. Set it to `admin` right after creating the
account:

```bash
python manage.py shell -c "
from accounts.models import User
u = User.objects.get(username='YOUR_SUPERUSER_USERNAME')
u.role = User.Role.ADMIN
u.save()
"
```

(A superuser can still do anything through `/admin/` regardless of
`role` — Django's own `is_superuser` flag overrides all permission
checks there — but the project's own Admin-only pages like
`/materials/upload/` check `role`, not `is_superuser`, so this step is
what unlocks those.)

## Seeding the catalog (your first Faculty, Department, Course)

There's no dedicated "add a Faculty" page in the student/Admin-facing
app — by design, matching the blueprint's scoping (section 4: Admin has
"complete control" via administration, not a second parallel UI for it).
Add your academic structure through `/admin/`:

1. Go to `/admin/`, log in as your Admin.
2. Under **Academics**, add at least one **Faculty**, one **Department**
   (linked to that Faculty), and one **Course** (linked to that
   Department).
3. Add at least one **Academic session** (e.g. `2026/2027`) and each
   **Semester** you need (`First Semester` / `Second Semester`).
4. Go to `/materials/upload/` and upload your first material against
   that course.

After that, students can reach it by browsing from the home page
(Faculty → Department → Course) or by searching for the course code.

## Environment variables

All read from `.env` (see `.env.example`) via `python-dotenv`; every one
has a sensible default for local development except `DJANGO_SECRET_KEY`.

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(insecure placeholder)* | **Set a real random value before deploying.** Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `True` | Set `False` in production — never run with `DEBUG=True` on the open internet |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated; add your real domain(s) when deploying |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | *(empty)* | Comma-separated; needed in production behind HTTPS + a custom domain |
| `DJANGO_BEHIND_PROXY` | `False` | Only `True` if your host's reverse proxy terminates HTTPS itself — see [SECURITY.md](SECURITY.md), "Force HTTPS" before enabling |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | See [Switching to PostgreSQL](#switching-to-postgresql) |
| `MAX_MATERIAL_UPLOAD_MB` | `100` | Enforced both in the upload form (`materials/validators.py`) and as Django's request-body size limit (`config/settings.py`) |
| `DJANGO_TIME_ZONE` | `Africa/Lagos` | Any IANA time zone name; affects how upload/download timestamps display |

## Running the tests

Each app ships a `tests.py` covering the permission boundaries and core
flows from the blueprint's own Testing checklist (section 24) —
registration/login, Student-vs-Admin access to every Admin-only view,
upload validation (rejected extensions, oversized files, mismatched
file content), download logging, bookmarking, search/filtering, and
catalog browsing — plus the security hardening added later: login
lockout (`accounts.tests.LoginRateLimitTests`), the registration
honeypot (`accounts.tests.BotProtectionTests`), and malformed
filter-parameter handling (`materials.tests.SearchAndFilterTests.
test_malformed_numeric_filter_is_ignored_not_500`).

```bash
python manage.py test
```

or per app, e.g. `python manage.py test materials`. Also run
`pip-audit -r requirements.txt` (already in `requirements.txt`) to scan
for known CVEs in dependencies — see
`.github/workflows/security.yml` for the CI job that runs both
automatically. These tests were written and carefully reviewed against
Django and each library's documented behavior, but — worth being
upfront about — the environment this project was generated in had no
network access to actually `pip install` anything and run them for
real. Run `python manage.py test` yourself right after your first
`pip install -r requirements.txt`, before you rely on this as a working
base.

## How file uploads work

- **Validation** (`materials/validators.py`): extension whitelist
  (`.pdf .pptx .docx .xlsx .txt`), a size cap
  (`MAX_MATERIAL_UPLOAD_MB`), and content verification — the file's
  actual bytes are checked against its extension (PDF signature;
  real-ZIP-with-the-right-internal-file for `.docx`/`.pptx`/`.xlsx`; a
  text heuristic for `.txt`), so a renamed `.exe` saved as `.pdf`
  doesn't pass just because of its filename. See
  [SECURITY.md](SECURITY.md), "Restrict file uploads" for the full
  detail, including what this still doesn't catch (malware/macros
  inside an otherwise-genuine Office file). This runs as a model-field
  validator, so it applies identically whether a Material is created
  through the upload form, the Django admin, or a script — see the
  docstring in `materials/forms.py` for why it isn't duplicated at the
  form level.
- **Storage**: local disk under `media/` in development
  (`FileSystemStorage`, Django's default). `materials/models.py`
  computes and stores `file_type`/`file_size` at save time rather than
  reading them from storage on every page view — see that file's
  docstring for why that matters once storage moves off local disk.
- **Never executed**: downloads are served with
  `Content-Disposition: attachment` (`materials.views.material_download`)
  — a browser is told to download the file, never to run or render it
  in a trusted context.

## Switching to PostgreSQL

Nothing to change in code — `config/settings.py` reads the database
config from a single `DATABASE_URL` env var via `dj-database-url`.
Set it in `.env` (or your host's environment variable settings):

```
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
```

Then run `python manage.py migrate` again against the new database.
Most free-tier hosts (Render, Railway, Neon, Supabase, etc.) hand you
a ready-made URL in exactly this format — check whichever you pick for
their current free-tier terms, since those change over time.

## Swapping in cloud storage

The blueprint calls for materials to live in object storage rather than
on the app server's own disk (section 7). Local `FileSystemStorage` is
still the default (zero setup for `runserver`), but the project now
ships with **Cloudflare R2 support built in and ready to configure** —
nothing in `materials/models.py` or `views.py` assumes a local path,
and `config/settings.py` switches the storage backend (and the PDF-preview
CSP rule that has to travel with it) automatically the moment R2's
environment variables are set. Setup steps, where each credential comes
from, and what to do if the preview doesn't load: **[DEPLOYMENT.md, "Cloudflare R2"](DEPLOYMENT.md#2-cloudflare-r2)**.

## Deployment

Concrete, step-by-step, for the Django hosting + PostgreSQL + Cloudflare
R2 + WhiteNoise architecture this project is built for — provisioning
Postgres, setting up the R2 bucket, every environment variable
production needs, and a post-deploy verification checklist:
**[DEPLOYMENT.md](DEPLOYMENT.md)**.

## Design notes

The visual design is intentionally not default Bootstrap or a generic
SaaS-dashboard look — it leans into a "campus registry / card catalog"
feel (navy ink, a restrained gold accent, a serif for headings, hairline
rows instead of boxed cards) since the subject is an academic archive,
not a marketing product. All of it lives in `static/css/style.css` as
CSS custom properties (`--ink`, `--paper`, `--accent`, etc.) — change
those few variables to reskin the whole site without touching templates.

## What's intentionally not built yet

Everything below is explicitly Phase 2 or Phase 3 in the blueprint
(sections 19–20) and was left out on purpose, to keep this MVP small
enough to actually finish, run, and deploy first:

- Advanced search (a dedicated engine like Meilisearch/Typesense)
- Per-student download history and "popular materials" views
- Material versioning, course subscriptions, notifications
- PWA / offline support
- Past Questions / Assignments / Solutions sub-sections per course
- AI-generated summaries, key concepts, or study questions
- A malware/macro scanner for uploaded Office files (see [SECURITY.md](SECURITY.md), "Restrict file uploads" for exactly what today's validation does and doesn't catch)
- Rate limiting and audit logging (blueprint section 21) — straightforward
  to add with `django-ratelimit` and Python's `logging` module respectively,
  but not wired in here
- A CDN in front of file downloads (blueprint section 22) — not needed
  until real traffic shows it's needed

## Troubleshooting

**`ModuleNotFoundError: No module named 'django'`** — you're not in the
virtual environment, or step 2 of Getting Started didn't complete. Run
`source .venv/bin/activate` then `pip install -r requirements.txt`.

**Uploading a material fails with a 403** — you're logged in as a
Student, or as an Admin whose `role` field never got set (see the note
at the end of Getting Started about `createsuperuser`).

**A PDF won't preview in the browser** — some browsers block embedding
PDFs served without `DEBUG=True`'s permissive dev-server headers, or
the file genuinely isn't a valid PDF (our upload validator checks the
extension, not the file's real contents — see [How file uploads work](#how-file-uploads-work)).
Downloading it directly is always available as a fallback.

## Design: "Liquid Glass"

The interface follows Apple's iOS 26/27 "Liquid Glass" look: frosted translucent surfaces over a soft
gradient wallpaper, large rounded corners, capsule buttons, a glowing search bar, a floating tab bar on
phones, and automatic light / dark themes (with a toggle that remembers the choice).

- Everything lives in `static/css/style.css`. Colours, radii and shadows are CSS variables at the top;
  change those to re-skin the whole site. The dark palette is defined once and generated into two places
  on purpose (explicit choice, and the no-JavaScript fallback) - the file's header explains how.
- `static/js/app.js` does three small things (theme toggle, filter auto-apply, dismissing banners) and
  contains no inline code, so it works under the strict Content-Security-Policy.
- Blur is expensive on cheap phones, so it's limited to a few large surfaces, and the site falls back
  to solid panels where `backdrop-filter` is unavailable or the visitor asks for reduced transparency.
- Icons are one inline SVG sprite (`templates/partials/icons.html`), used as
  `{% include "partials/icon.html" with name="search" %}`.
