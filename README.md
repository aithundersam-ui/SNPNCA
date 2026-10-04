# SNPNCA membership website

Website for the Syndicat National du Personnel Navigant Commercial Algérien: a public home page with a contact form, a members-only area (News and a Q&A assistant over the union's PDFs), and an admin panel. Everything is available in French (default) and English under `/fr/...` and `/en/...`.

## Stack and why

| Part | Choice | Why |
|---|---|---|
| Web framework | Django 5.2 (Python) | Built-in CSRF and XSS protection, ORM (no hand-written SQL from user input), Argon2 password hashing, gettext translation files and `/fr/` `/en/` URLs, migrations and a test runner. |
| Database | PostgreSQL 16 | Also provides the full-text search used to find relevant PDF passages. |
| PDF text | PyMuPDF for the text layer, Tesseract OCR (French, English, Arabic) for scanned pages | Both run on the server; nothing is sent to third parties during extraction. |
| Q&A answers | Claude API (`claude-opus-5-5` by default) | Called only from the server; the key never reaches the browser. |
| Hosting | One VPS with Docker Compose, Caddy for automatic HTTPS | OCR, a background worker and private file storage need a real server; Caddy handles certificates. A 2 vCPU / 4 GB VPS is enough to start. |

## How the Q&A stays inside the documents

1. When an admin uploads a PDF, the worker extracts each page's text (OCR when a page has no text layer), splits it into overlapping passages and indexes them three ways: French and English (stemmed, accent-insensitive) and language-neutral (Arabic, names, numbers).
2. For each question, Claude first lists search keywords in French, English and Arabic. That is what lets an English question find a French passage.
3. The best passages are sent to Claude with strict instructions to answer only from them, in the language of the question, and to list which passages it used.
4. The server enforces the rule, rather than trusting the prompt alone: if nothing matched, Claude is not asked at all; if Claude says the answer isn't there, or cites no valid passage, the member gets a fixed "not found in the documents" reply. Sources shown to the member (document title + page) come from the database, not from model text.

Code: `qa/assistant.py`, `qa/search.py`, `qa/llm.py`, `qa/processing.py`. Tests: `tests/test_qa.py`.

## Deploying on a VPS

1. Point your domain's DNS A record at the server and install Docker.
2. Copy this folder to the server, then:
   ```bash
   cp .env.example .env
   # edit .env: domain, secret key, database password, Master Admin email, SMTP, ANTHROPIC_API_KEY
   python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # use for DJANGO_SECRET_KEY
   docker compose up -d --build
   ```
3. On first start the `web` container runs migrations and **seeds the first Master Admin** from `MASTER_ADMIN_EMAIL`. With no `MASTER_ADMIN_PASSWORD`, a set-password link is emailed (recommended). Running it again does nothing once a Master Admin exists.
4. Log in at `https://your-domain/fr/account/login/`, fill in the home page text (Admin panel → Home page), upload PDFs, and import members.

Data lives in the Docker volumes `pgdata` (database) and `media` (PDFs and images). Back up both, e.g. nightly `docker compose exec db pg_dump -U snpnca snpnca > backup.sql` plus a copy of the `media` volume.

## Local development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # plus: apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara gettext
createdb snpnca                             # PostgreSQL 13+ required
export DJANGO_DEBUG=1 EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
export DATABASE_URL=postgres://USER:PASS@localhost:5432/snpnca MASTER_ADMIN_EMAIL=you@example.com MASTER_ADMIN_PASSWORD=choose-one
python manage.py migrate && python manage.py createcachetable && python manage.py seed_master_admin
python manage.py runserver                  # in another terminal: python manage.py process_documents
```

Run the tests (needs PostgreSQL; Tesseract for the OCR test):

```bash
DJANGO_DEBUG=1 DJANGO_TESTING=1 python manage.py test tests
```

## Translations

All interface text is in `locale/fr/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po` (source strings are English). After changing text in code or templates:

```bash
python manage.py makemessages -l fr -l en --ignore=tests --ignore=staticfiles
# translate the new entries in the .po files
python manage.py compilemessages
```

Admin-written content (home page text, news) has separate French and English fields; if one is empty, the other is shown.

## Roles

| Action | Member | Admin | Master Admin |
|---|---|---|---|
| Home page | ✓ | ✓ | ✓ |
| News, Q&A | ✓ | ✓ | ✓ |
| Create / edit / delete members, CSV import | | ✓ | ✓ |
| Upload / delete PDFs, manage news, answer messages | | ✓ | ✓ |
| Create admins, change roles, edit/delete admins | | | ✓ |

Every rule is checked on the server (`accounts/permissions.py`). The last active Master Admin cannot be deleted, demoted or deactivated.

## CSV import

Columns `full_name,email` with optional `language` (`fr`/`en`) and `role` (`user`/`admin`/`master`, honoured only when the Master Admin imports). UTF-8 required. A preview with per-row errors is shown before anything is created. Rows whose email already exists are **skipped**; members missing from the file are **left untouched**. Each new account gets a set-password email. A template is downloadable from the import page.

## Security notes

- HTTPS enforced (Caddy + `SECURE_SSL_REDIRECT`, HSTS), secure HTTP-only session cookies, CSRF on every form, a strict Content-Security-Policy, no inline scripts.
- Passwords hashed with Argon2; new accounts never get an admin-chosen password.
- Login lockout after 5 failures for 15 minutes (per email, looser per IP); password-reset and contact form are rate-limited; contact form has a honeypot and a minimum fill time.
- PDFs and images are stored outside the web root and served only through views that require login.
- Admin actions (account changes, role changes, uploads, deletions, CSV imports, replies) are written to the audit log, visible in the panel.
- Personal data is limited to the fields in the spec; a privacy notice sits on the contact form.

## Settings reference

See `.env.example`. Notable: `CONTACT_NOTIFY_EMAIL` (where contact submissions go), `MAX_PDF_MB` (default 25), `OCR_LANGUAGES` (default `fra+eng+ara`), `CLAUDE_MODEL`, `QA_RATE_LIMIT` (questions per member per 10 minutes).
