# Upgrading the LIVE HandoutVault: Liquid Glass interface + Exam Preparation

Read this once, top to bottom, before you copy anything. The site is live and its address is already in QR
codes and chats, so this update was built to be **additive and reversible**.

## What this update does

- Re-skins the whole site in the iOS "Liquid Glass" style (light and dark, phone and desktop).
- Adds an **Exam Preparation** button under the search bar (login required) leading to **Past Questions**
  and **Summaries**. Only Admins can add, edit or delete them; students can browse, preview and download.
  They are filed by faculty / department / course like handouts, and a summary can be linked to a handout.
- Fixes two small bugs on the way: the handout filters didn't apply by themselves (a security rule blocked
  the old script), and PDF previews of locally stored files were blocked.

## What it does NOT do

- It does **not** change your site address or your Render service name, so every QR code and link keeps working.
- It does **not** add any package, so `requirements.txt` is unchanged, and it needs **no new environment variables**.
- It does **not** change or delete any existing table or row. The only database change is two **new** tables
  (`exams_pastquestion`, `exams_summary`). Your users, passwords, handouts, bookmarks and download history are untouched,
  and nobody gets logged out.
- It does not touch Cloudflare R2 or your uploaded files.

## How it was checked, and what was not

Checked (details in the tests, all 70 pass):
- **An upgrade rehearsal.** A copy of your *current* code was given realistic data (admin, students, handouts,
  bookmarks, downloads); the new code and its migration were then applied to it. Result: every row still there, the
  old passwords still work for students and the admin, every page loads, and the SQL the migration runs is only
  `CREATE TABLE` / `CREATE INDEX` for the two new tables.
- **Rollback safety.** Your old code was run against the upgraded database and works, so going back is safe.
- **Your current web addresses are locked by a test** (`config/test_pages.py`), so an update can only ever add routes.
- Every page was opened in a real (headless) browser at phone and desktop sizes, in light and dark, with no
  console errors and no sideways scrolling; the theme toggle and the filters were exercised.

Not checked (be honest with yourself about these):
- It was rehearsed on SQLite, not on your Render PostgreSQL. The SQL is plain table creation, which is identical, but
  the very first deploy is the real test, which is why the steps below include a backup and a rollback.
- It was not tried on a real iPhone or Android phone. Open it on both after deploying.
- I have not seen your live code. If you (or anyone) edited files other than the two admin commands since the
  last package I gave you, step 4 shows you exactly where to look.

## Before you start

1. **Check your database plan first.** If your Render PostgreSQL is on the free plan, it **expires 30 days after
   it was created** (there is a short grace period, then it is deleted) and free databases have **no backups**.
   Open the database in Render and look at its expiry date. If it is close, upgrade it or move to a database that
   does not expire *before anything else*. That matters more than this update.
2. Pick a quiet time (not during an exam rush or right before a demo). Render rebuilds the site, so expect a
   short interruption while it deploys.

## Steps

### 1. Back up the live data (10 minutes, strongly recommended)

Use a **new terminal window** that you will close afterwards, so the production address never lingers in your
normal working terminal. Replace the placeholder with your database's **External** connection string
(Render, your database, "External Database URL"). Never paste that string into a chat.

PowerShell:
```
cd <your project folder, the one with manage.py>
.\venv\Scripts\activate
$env:DATABASE_URL = "PASTE-THE-EXTERNAL-URL-HERE"
python manage.py dumpdata accounts academics materials bookmarks --indent 2 --output backup-YYYY-MM-DD.json
```
Command Prompt: use `set DATABASE_URL=PASTE-THE-EXTERNAL-URL-HERE` instead of the `$env:` line.

`dumpdata` only reads. **Do not run `migrate`, `test` or `runserver` in that window.** Close it when it finishes.
The backup file contains real names, emails and password hashes: keep it private and never commit it (add the line
`backup-*.json` to your `.gitignore`). Your uploaded files live in R2 and are not part of this backup.

### 2. Work on a branch

```
git checkout -b glass-ui-exam-prep
```
If anything goes wrong later, your main branch (what is live) is untouched.

### 3. Copy the files in

Unzip the pack, open the folder inside it, select everything in it and copy it into your project folder (the
one containing `manage.py`). Choose **Replace** when asked. Do **not** delete your project folder, and leave your
`venv`, `.env`, `media` and `accounts/management` (your admin commands) alone. The pack does not touch them.

### 4. Look at exactly what changed

```
git status
git diff config/settings.py config/urls.py materials/views.py
```
`config/settings.py` and `config/urls.py` are the two files most likely to have been edited on your side. You
should see **only** the changes shown at the end of this guide. If `git diff` shows that something *you* had
there was removed (for example a line you added for Render), put your line back (`git checkout -p` or edit by hand)
and keep the new lines.

### 5. Test on your own computer (not against the live database)

First make sure you are *not* pointed at production:
```
python manage.py shell -c "from django.db import connection; print(connection.vendor)"
```
It must print `sqlite`. If it prints `postgresql`, **stop**: your `.env` or terminal still points at the live
database. Fix that first. Then:
```
python manage.py check
python manage.py makemigrations --check
python manage.py migrate
python manage.py test
python manage.py runserver
```
`check` says "no issues"; `makemigrations --check` says "No changes detected"; `test` ends with `OK`. Open
http://127.0.0.1:8000, look around, log in, open Exam Preparation.

### 6. Deploy

```
git add -A
git commit -m "Liquid Glass interface and Exam Preparation"
git checkout main
git merge glass-ui-exam-prep
git push
```
(Use your real main branch name if it is not `main`.) Render starts a deploy. Watch the log: you should see
`Applying exams.0001_initial... OK` once, then the service goes live. Your existing start command already runs
`migrate`, so nothing else is needed.

### 7. Check the live site

- The address from your QR code opens the new design.
- The moon icon switches light and dark.
- A student account still sees its handouts and bookmarks.
- Signed out, tap **Exam Preparation**: you land on the login page, and after logging in you arrive in Exam Preparation.
- As Admin: Exam Preparation, **Add past question**, upload a PDF, open it, download it.
- Open the site on an iPhone and an Android phone.

### 8. Add the content

Admins add past questions and summaries from Exam Preparation (or from a handout's page: **Add a summary of
this handout** pre-fills the form).

## If something looks wrong: roll back

In Render open the service, go to **Events** (deploys), find the previous successful deploy and **roll back**
to it. (Or run `git revert <merge commit>` and push.) The two new tables stay in the database; the old code ignores
them, which the rehearsal confirmed. **Never delete those tables by hand.** Then send me the deploy log
(no passwords or database URLs) and I will look at it.

## The settings changes, in plain words

1. `"exams"` is added to `INSTALLED_APPS` (the new section must be registered; without it the site will not start).
2. `X_FRAME_OPTIONS` goes from `DENY` to `SAMEORIGIN`, and the CSP `frame-ancestors` from `'none'` to `'self'`. Other
   websites still cannot frame yours. This only lets a handout page show a preview of a file from your own
   domain. Revert both lines if you prefer; PDF previews from R2 work either way.
3. A `TESTING` switch so `manage.py test` never needs `collectstatic`, never writes test files into `media/`, and
   **never uploads to R2 even if your keys are in `.env`**. It does nothing in production.

## Files in this pack

New: `config/test_pages.py`, `static/js/app.js`, the whole `exams/` app and every file in `templates/`

Changed: `README.md`, `SECURITY.md`, `config/settings.py`, `config/urls.py`, `materials/views.py`, `static/css/style.css`, `templates/academics/course_list.html`, `templates/academics/department_list.html`, `templates/accounts/login.html`, `templates/accounts/register.html`, `templates/base.html`, `templates/bookmarks/bookmark_list.html`, `templates/home.html`, `templates/materials/admin_dashboard.html`, `templates/materials/material_confirm_delete.html`, `templates/materials/material_detail.html`, `templates/materials/material_form.html`, `templates/materials/material_list.html`

## Exact changes to your existing files

`config/settings.py`
```diff
--- a/config/settings.py
+++ b/config/settings.py
@@ -12,6 +12,8 @@
 the "what", SECURITY.md has the "why" and what's out of scope.
 """
 import os
+import sys
+import tempfile
 from pathlib import Path
 
 import dj_database_url
@@ -21,6 +23,11 @@
 BASE_DIR = Path(__file__).resolve().parent.parent
 load_dotenv(BASE_DIR / ".env")
 
+# True while running `python manage.py test`. The WhiteNoise "manifest" static storage refuses to
+# render {% static %} until `collectstatic` has run, which it hasn't in a test run (or in CI), so
+# tests use Django's plain static storage instead. Production is unaffected.
+TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
+
 
 def env_bool(name, default=False):
     return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")
@@ -99,6 +106,7 @@
     "academics",
     "materials",
     "bookmarks",
+    "exams",  # Exam Preparation: past questions + summaries
 ]
 
 MIDDLEWARE = [
@@ -219,13 +227,20 @@
 
 MEDIA_URL = "media/"
 MEDIA_ROOT = BASE_DIR / "media"
+if TESTING:
+    # Tests upload real files; keep them out of the project's media/ folder.
+    MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="handoutvault-test-media-"))
 
 STORAGES = {
     "default": {
         "BACKEND": "django.core.files.storage.FileSystemStorage",
     },
     "staticfiles": {
-        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
+        "BACKEND": (
+            "django.contrib.staticfiles.storage.StaticFilesStorage"
+            if TESTING
+            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
+        ),
     },
 }
 
@@ -249,7 +264,8 @@
 AWS_DEFAULT_ACL = None          # R2 doesn't use S3-style ACLs — leave unset, never "public-read"
 AWS_S3_FILE_OVERWRITE = False   # don't silently replace a same-named file already in the bucket
 
-USE_R2_STORAGE = bool(AWS_STORAGE_BUCKET_NAME and AWS_S3_ENDPOINT_URL)
+# Never during tests: a developer with real R2 keys in .env must not have `manage.py test` upload to the live bucket.
+USE_R2_STORAGE = bool(AWS_STORAGE_BUCKET_NAME and AWS_S3_ENDPOINT_URL) and not TESTING
 if USE_R2_STORAGE:
     STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
 
@@ -266,7 +282,10 @@
 # ---------------------------------------------------------------------------
 SECURE_CONTENT_TYPE_NOSNIFF = True  # stop browsers "guessing" a different content-type than we set
 SECURE_REFERRER_POLICY = "same-origin"  # don't leak full URLs to third-party resources
-X_FRAME_OPTIONS = "DENY"  # this site is never meant to be framed by anyone else
+# SAMEORIGIN, not DENY: other websites still can't frame this one (clickjacking protection), but
+# the handout page may frame this site's OWN files - the PDF preview <iframe> - when materials are
+# served from this domain (local disk). With DENY, every locally-served preview was blocked.
+X_FRAME_OPTIONS = "SAMEORIGIN"
 
 # Content-Security-Policy — django-csp 4.x's dict-based config format;
 # if you're on django-csp 3.x, translate this into the individual
@@ -308,7 +327,7 @@
         "img-src": ["'self'", "data:", *_file_storage_origins],
         "connect-src": ["'self'"],
         "frame-src": ["'self'", *_file_storage_origins],  # the PDF preview <iframe>
-        "frame-ancestors": ["'none'"],
+        "frame-ancestors": ["'self'"],  # same idea as X_FRAME_OPTIONS above
         "object-src": ["'none'"],
         "base-uri": ["'self'"],
         "form-action": ["'self'"],
```

`config/urls.py`
```diff
--- a/config/urls.py
+++ b/config/urls.py
@@ -12,6 +12,7 @@
     path("catalog/", include("academics.urls", namespace="academics")),
     path("materials/", include("materials.urls", namespace="materials")),
     path("bookmarks/", include("bookmarks.urls", namespace="bookmarks")),
+    path("exam-prep/", include("exams.urls", namespace="exams")),
 ]
 
 if settings.DEBUG:
```

`materials/views.py` changed in three places (home page counts, a course-switcher on the handout list, and
exam-prep links on a handout's page). It was replaced as a whole file; if you edited it yourself, merge by hand.
