# Security

This maps a standard web-app security checklist onto what's actually in
this codebase — what's implemented (and where), what doesn't apply to
this architecture (and why), and what's explicitly left as your
responsibility as the deployer (mostly infrastructure choices this
codebase can't make for you). Written to be checked item by item, not
just skimmed once.

**Being upfront about the limits of this pass**: the environment this
project was built in had no network access, so nothing below was tested
against a live server, a real browser, or an actual PostgreSQL/S3-style
backend — it's careful reading of Django/library documentation and
static analysis of this specific code, not a penetration test. Treat
this as a strong starting point, not a certification. Run
`python manage.py test`, `pip-audit`, and your own judgment before
trusting this with real student data.

---

### Document the code properly
Every `models.py`, `views.py`, `forms.py`, `urls.py`, and `admin.py`
across all four apps opens with a module docstring explaining that
file's role and its non-obvious design decisions; non-trivial functions
have their own docstrings too. README.md covers setup/operations; this
file covers security specifically. Nothing in this security pass changed
that policy — the new code below (axes/csp config, the validators
rewrite, the honeypot) is documented to the same standard as everything
that came before it.

### Hide API keys
This project has no third-party API keys today (no payment processor,
no email service, no external API) — but the pattern is already in
place for whenever one shows up. `SECRET_KEY` (the one secret this
codebase does have) is read from an environment variable in
`config/settings.py`, never hard-coded, with an obviously-fake fallback
("dev-insecure-secret-key-change-me") rather than a random-looking
placeholder, so a deployment that forgets to set the real one is
unmistakable rather than silently insecure. `.env` (where the real
value lives locally) is in `.gitignore`. **Follow the same pattern for
any key you add later**: put it in `.env`, read it with
`os.environ.get(...)` in `settings.py`, add it to `.env.example` with a
placeholder (never the real value), document it in README's
"Environment variables" table.

### Purge secrets from Git
This codebase was generated fresh and was never committed to a git
repository — there's no history to purge. `git init` here starts clean.
Two things worth doing the moment you do put this under version control:
1. Confirm `.env` is genuinely ignored before your first commit —
   `git status` should never list it. `.gitignore` already excludes it.
2. If a secret ever DOES get committed by accident later, changing it
   afterwards in `.env` is not enough — rotate the actual credential
   (new `DJANGO_SECRET_KEY`, new DB password, etc.) and consider the old
   one permanently compromised, since it lives in git history forever
   unless you rewrite it (`git filter-repo` or BFG Repo-Cleaner) — and
   even then, assume anyone who already cloned it has a copy.

### Expose only the public DB key
This checklist item describes a different architecture than the one
here — it's the right instinct for a backend-as-a-service setup
(Supabase, Firebase) where a browser holds a key and talks to the
database directly, so that key has to be scoped down to "public" and
paired with database-level policies. **Django doesn't work that way,
and nothing here is a "DB key" in that sense**: the browser only ever
talks to Django views over HTTP; only the Django process itself holds
`DATABASE_URL` (server-side environment variable, never sent to a
client, never appears in any template or static file); Postgres is
never reachable from outside your server/host network. There's no key
to scope down because there's no client-side database access to scope.

### Enable row-level security
Same architecture note as above. RLS policies matter when the database
itself has to distinguish which end-user is asking (because that
end-user's client is the one connecting). Here, every query runs as
the one application-level Postgres role Django connects with —
access control happens in Django (see "Enforce server-side auth" and
"Lock record access" below), not in Postgres. Bolting on Postgres RLS
policies here wouldn't add protection Django doesn't already provide,
and would actively fight `python manage.py migrate`/the ORM's own
connection pooling, which isn't designed around per-request Postgres
roles. If you later add a separate service that DOES connect to the
same database directly from a browser or an untrusted context, that's
exactly when RLS becomes the right tool — it isn't one here.

### Encrypt sensitive data
- **Passwords**: hashed, never stored or logged in plain text — see
  "Hash passwords" below.
- **In transit**: enforced by "Force HTTPS" below — everything between
  browser and server is encrypted once deployed correctly.
- **At rest**: this codebase stores names, emails, student IDs, and
  uploaded course materials — none of it is the kind of data (payment
  details, national ID numbers, health records) that typically calls
  for application-level field encryption on top of the database's own
  protection. Rely on your database and storage provider's at-rest
  encryption (essentially universal on managed Postgres and S3-compatible
  object storage today — confirm it's on for whichever you pick) rather
  than hand-rolled field encryption, which mainly adds complexity and
  ways to lose data (e.g. losing the encryption key) for a threat model
  this project doesn't have. If your institution's data-protection policy
  requires field-level encryption regardless, `django-encrypted-model-fields`
  is the standard option for `student_id`/`email`— it wasn't added here
  since scope should be driven by an actual policy requirement, not
  added speculatively.

### Enforce server-side auth
Every check happens in Django views, never trusted from the client:
- `materials.views.material_download`, `bookmarks.views.toggle_bookmark`,
  `bookmarks.views.bookmark_list` — `@login_required`.
- `materials.views.material_upload` / `material_edit` / `material_delete`
  / `admin_dashboard` — `@admin_required` (`accounts/permissions.py`),
  which re-checks `request.user.role` server-side on every request; it
  does not trust a client-supplied role, a cookie value, or anything
  else the browser sends other than the authenticated session itself.
- No view infers permissions from request data (a hidden form field, a
  query param) — only from `request.user`, which Django's session
  middleware derives server-side from the signed session cookie.

### Lock record access
(a.k.a. object-level authorization — not just "logged in", but "allowed
to touch *this* record specifically.")
- `bookmarks.views.toggle_bookmark` only ever creates/deletes a bookmark
  row scoped to `student=request.user` — there's no code path where a
  student can add or remove another student's bookmark, even by
  guessing another material's ID, because the student half of the
  lookup key is never taken from the request.
- `bookmarks.views.bookmark_list` queries `request.user.bookmarks` —
  a student can only ever see their own.
- Materials themselves are intentionally NOT owner-locked — any Admin
  can edit/delete any material, matching the spec's own scoping
  (section 3: "Admin has complete control"), not a gap. There's exactly
  one class of "record" in this app with a real per-user ownership
  boundary (bookmarks), and it's enforced.

### Block field tampering
(a.k.a. mass-assignment protection — can a POST body set a field the
form never intended to expose?)
- `accounts.forms.StudentRegistrationForm.Meta.fields` explicitly lists
  seven fields. `role` is not one of them — `accounts.views.register`
  hard-codes `user.role = User.Role.STUDENT` after `form.save()`, so no
  POST body, however constructed, can register an Admin account through
  the public form. There is exactly one way to create an Admin:
  `manage.py createsuperuser` plus the manual `role` promotion step
  documented in README, or promotion through `/admin/` by an existing
  Admin.
- `materials.forms.MaterialUploadForm.Meta.fields` lists only the
  fields a real upload form should expose. `uploaded_by` is set
  server-side in `materials.views.material_upload`
  (`material.uploaded_by = request.user`), never read from form data.
  `file_type`/`file_size` are `editable=False` on the model, so Django
  excludes them from any ModelForm automatically regardless of what a
  POST body contains.

### Secure session cookies
In `config/settings.py`: `SESSION_COOKIE_HTTPONLY = True` (JavaScript,
including an XSS payload, can never read the session cookie),
`SESSION_COOKIE_SAMESITE = "Lax"` (blocks the cookie being sent on most
cross-site requests — the standard modern CSRF defence layer, on top of
Django's token-based CSRF protection which was already on), and
`SESSION_COOKIE_SECURE = True` outside `DEBUG` (never sent over plain
HTTP once deployed). The CSRF cookie gets the same treatment
(`CSRF_COOKIE_HTTPONLY`/`SAMESITE`/`SECURE`).

### Hash passwords
Handled by Django itself — `UserCreationForm` and `createsuperuser` both
call `User.set_password()`, which always hashes; nothing in this
codebase ever reads, stores, or logs a raw password. The one thing
configured here is *which* algorithm: `PASSWORD_HASHERS` in
`config/settings.py` now lists Argon2 first (the current OWASP-recommended
default, needs the `argon2-cffi` package — already in `requirements.txt`),
with PBKDF2 kept after it purely so a password hashed before this
change still verifies; Django re-hashes it with Argon2 transparently
the next time that user logs in.

### Rate limit login
`django-axes` (already in `requirements.txt`, wired into
`AUTHENTICATION_BACKENDS`/`MIDDLEWARE` in `config/settings.py`) locks
out further attempts after `AXES_FAILURE_LIMIT` (5) failures for
`AXES_COOLOFF_TIME` (1 hour), keyed on the **combination** of username
and IP — deliberately not either alone: IP-only would let one bad actor
lock out everyone sharing a campus network's IP; username-only would
let anyone lock a specific student out of their own account just by
failing their password a few times from anywhere. Run
`python manage.py migrate` again after installing it — axes tracks
attempts in its own database tables. Covered by
`accounts.tests.LoginRateLimitTests`.

### Add bot protection
A honeypot field (`website`) on `accounts.forms.StudentRegistrationForm` —
positioned off-screen (`.hp-field-wrap` in `static/css/style.css`,
off-screen positioning rather than `display:none` since some simple
bots specifically check for and skip that) and out of the tab order, so
a sighted human filling in the form by hand never sees or fills it; a
submission that DOES fill it in is rejected. This is a real but modest
defence — effective against simple/unsophisticated bots, not against
one built specifically to target this exact form. If registration spam
becomes an actual problem, the next steps up are `django-recaptcha`/
hCaptcha (needs your own API key from that provider, stored the same
way as any other secret — see "Hide API keys") or extending
`django-axes`-style throttling to the registration endpoint too.
Covered by `accounts.tests.BotProtectionTests`.

### Parameterize queries
Nothing to add — this was already true throughout, by construction: the
codebase uses the Django ORM exclusively (`Model.objects.filter(...)`
etc.) and contains zero raw SQL (no `.raw()`, no `cursor.execute()`, no
`.extra()` — checked directly, not assumed). The ORM parameterizes
every query it builds; there is no code path where user input is
interpolated into a SQL string.

### Validate all input
- Registration and material upload go through Django Forms
  (`StudentRegistrationForm`, `MaterialUploadForm`), which validate
  type, length, and uniqueness before anything touches the database.
- `materials.views.material_list`'s search/filter GET parameters
  (course/level/semester/session IDs) now go through a `_safe_int()`
  helper before reaching the ORM — added during this pass, since
  `?level=abc` previously reached `.filter(level="abc")` directly,
  which would raise an uncaught exception (a 500 error) rather than
  failing gracefully. It now just matches nothing, like an empty filter.
  Covered by `materials.tests.SearchAndFilterTests.
  test_malformed_numeric_filter_is_ignored_not_500`. (Worth being
  precise about what this is and isn't: the *ORM* was never at SQL-injection
  risk here, since even the old code went through `.filter()`, not raw
  SQL — this fix is about availability/robustness, not injection.)
- File uploads: see "Restrict file uploads" below.

### Escape user content
Django's template engine auto-escapes every `{{ variable }}` by
default. Checked directly: this codebase contains zero uses of `|safe`,
`mark_safe`, or `{% autoescape off %}` anywhere — nothing turns that
protection off for any user-supplied content (material titles, topics,
descriptions, names, etc.). If you ever DO need to render trusted HTML
somewhere, reach for those explicitly and narrowly rather than
disabling escaping more broadly, and never on a field a Student can set.

### Restrict file uploads
`materials/validators.py` (rewritten during this pass) now checks two
independent things, not just the filename:
1. Extension whitelist (`.pdf .pptx .docx .xlsx .txt`) + size cap
   (`MAX_MATERIAL_UPLOAD_MB`) — as before.
2. **Actual content**, using only the Python standard library (no new
   system dependency like libmagic): PDFs are checked for the real
   `%PDF-` signature; `.docx`/`.pptx`/`.xlsx` are opened as real ZIP
   archives (`zipfile`) and checked for the one internal file each
   format is guaranteed to contain (`word/document.xml`,
   `ppt/presentation.xml`, `xl/workbook.xml`); `.txt` gets a best-effort
   heuristic (no NUL bytes, decodes as UTF-8) since plain text has no
   real signature to check. A `virus.exe` renamed to `lecture.pdf` — or
   an `.xlsx` renamed to `.docx` — is now rejected at upload, not just
   at the extension. Verified against real generated zip/PDF files
   directly (see the worked check run during development; also covered
   by `materials.tests.UploadValidationTests`).
- **Path traversal**: not hand-rolled here — Django's storage layer
  (`Storage.generate_filename()` / `get_valid_name()`) already rejects
  filenames that would escape `MEDIA_ROOT` before this project's code
  ever sees them.
- **Never executed**: uploaded files are only ever served back via
  `materials.views.material_download`, which sends them with
  `Content-Disposition: attachment` — a browser is told to download the
  file, never to run or render it in a trusted context.
- **What's still NOT covered**: this doesn't scan for malware/macros
  inside an otherwise-valid `.docx`/`.xlsx` (a real Office file can
  still carry a malicious macro and pass every check above, since the
  check confirms "this is genuinely an Office document," not "this
  Office document is safe"). If that risk matters for your deployment,
  pair this with a virus/macro scanner (e.g. ClamAV) in front of
  storage — out of scope for what a pure-Python validator can do.

### Trim API responses
This project doesn't have a JSON/API layer to trim — it's server-rendered
Django Templates end to end, so there's no separate response payload
that could over-expose fields the way a REST/GraphQL API response can.
The same underlying principle already shows up in the two places it
actually applies here: Forms use an explicit `fields` allowlist rather
than exposing every model field (see "Block field tampering"), and
templates only render the context each view explicitly passes in — a
template can't accidentally leak a field nobody put in its context. If
you add a JSON API later (e.g. Django REST Framework for a future
mobile client), apply the same allowlist instinct there: DRF serializers
with explicit `fields = [...]`, never `fields = "__all__"` on anything
touching `User`.

### Add security headers
Set explicitly in `config/settings.py`: `SECURE_CONTENT_TYPE_NOSNIFF`,
`SECURE_REFERRER_POLICY = "same-origin"`, `X_FRAME_OPTIONS = "SAMEORIGIN"` (see the update note at the end),
plus HSTS (`SECURE_HSTS_SECONDS` + subdomains + preload) outside
`DEBUG`. `django-csp` (new dependency) adds a Content-Security-Policy —
tuned to what this app's own templates actually load (Bootstrap +
Google Fonts from their real CDN origins, nothing else external, plus
wherever Cloudflare R2 is actually serving uploaded materials from once
that's configured — see DEPLOYMENT.md, "Cloudflare R2", and the
`_file_storage_origins` comment in `config/settings.py`) with
`script-src` locked down to `'self'` plus that one CDN and **no**
`'unsafe-inline'` — that's the directive that actually matters against
XSS, since it's what would stop an injected `<script>` tag from
executing. `style-src` does allow `'unsafe-inline'`, because Bootstrap's
own bundled JS sets inline `style.height` etc. directly during its
collapse/dropdown open-close transitions; every hand-authored
`style="..."` in this project's own templates was moved into
`static/css/style.css` instead (so that allowance is as small as it can
be, not a blanket exemption). **Verify this in a real browser before
launch** — CSP is exactly the kind of thing that's easy to get subtly
wrong without one open in front of you, and check the exact config key
names against whichever `django-csp` version you actually install
(pinned to the 4.x dict-based config format here; 3.x uses different,
individual `CSP_*` settings).

### Force HTTPS
`SECURE_SSL_REDIRECT = True` outside `DEBUG` (`config/settings.py`) —
every plain-HTTP request gets redirected to HTTPS. Paired with HSTS (see
above) so returning browsers skip the insecure request entirely next
time. One thing this can't safely default to "on": if your host puts a
reverse proxy in front of Django that terminates TLS itself (true for
most free-tier PaaS hosts), Django needs `SECURE_PROXY_SSL_HEADER` set
to trust that proxy's `X-Forwarded-Proto` header — but setting that
blindly on a deployment that ISN'T behind such a proxy would let a
client fake "I'm on HTTPS" and defeat the redirect entirely. It's
therefore opt-in via `DJANGO_BEHIND_PROXY=True` in `.env` — read the
comment directly above it in `config/settings.py` before turning it on,
and only do so once you've confirmed your specific host overwrites
(rather than passes through) that header from the client.

### Scan dependencies
`pip-audit` is in `requirements.txt` — run `pip-audit -r requirements.txt`
yourself any time, and `.github/workflows/security.yml` (new) runs it
automatically on every push/PR plus a weekly schedule (to catch newly
disclosed CVEs in dependencies that haven't changed), alongside the full
test suite. This project's own build environment had no network access
to actually run a scan itself — the pinned version ranges in
`requirements.txt` are reasonable/current as of when this was written,
but **run `pip-audit` yourself before deploying**, don't take that on
faith.

---

### Update: Exam Preparation + the glass interface

- **Exam content follows the same rules as handouts.** Every `/exam-prep/` page needs a login
  (`@login_required`: signed-out visitors are sent to the login page and brought back afterwards);
  adding, editing and deleting is Admin-only (`@admin_required`); every upload goes through the same
  extension / size / real-content check (`materials.validators`). Covered by `exams/tests.py`.
- **`X_FRAME_OPTIONS` is now `SAMEORIGIN`** (and the CSP says `frame-ancestors 'self'`) instead of `DENY`.
  Other websites still cannot frame this one, so clickjacking protection is unchanged; the change lets the
  handout page show a PDF preview of a file served from this same domain (local storage). With `DENY` that
  preview was blocked. Files served from Cloudflare R2 were never affected. Covered by
  `config/test_pages.py::SecurityHeaderTests`.
- **Fewer third-party requests.** The redesign dropped the Bootstrap CDN and Google Fonts (system fonts, one
  stylesheet, one script), so pages no longer contact any third party. The CSP allow-list in
  `config/settings.py` still names those hosts; you can remove `https://cdnjs.cloudflare.com` and the Google
  Fonts entries from it whenever you like.
- **A bug fixed along the way:** the old handout filters used an inline `onchange=` handler, which the CSP
  (correctly) blocks, so the dropdowns didn't apply by themselves. Filtering is now done by `static/js/app.js`.
  `config/test_pages.py` fails if any page ever ships an inline handler, inline script or `style=` attribute again.
