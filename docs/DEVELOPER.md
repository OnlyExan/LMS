# Developer Guide

How the LMS is built, how to work on it, and how it's deployed. Start here, then use:
- [`BACKEND.md`](BACKEND.md): every URL, template and context variable
- [`TESTING.md`](TESTING.md): the test suite
- [`USER_GUIDE.md`](USER_GUIDE.md): how the app is used

## Contents
1. [Stack](#stack)
2. [Local setup](#local-setup)
3. [Project layout](#project-layout)
4. [Architecture](#architecture)
5. [Design decisions and changes from the proposal](#design-decisions-and-changes-from-the-proposal)
6. [Rules for new code](#rules-for-new-code)
7. [Team workflow](#team-workflow)
8. [Deployment](#deployment)
9. [Troubleshooting](#troubleshooting)

## Stack
| Part | Choice |
|---|---|
| Language / framework | Python 3.11, Django 5.2 |
| Frontend | Server-rendered Django templates, custom CSS (`static/css/`), a little plain JavaScript |
| Database | SQLite for local development, PostgreSQL on Supabase in production |
| File storage | Local `media/` folder in development, Supabase Storage (S3-compatible, private bucket) in production |
| Hosting | Vercel |
| Login protection | django-axes |
| Project tracking | Linear, team `LSM` |

## Local setup
The README has the short version. In full:

```powershell
git clone https://github.com/OnlyExan/LMS.git
cd LMS
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
Copy-Item .env.example .env          # Mac/Linux: cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo           # optional demo data, password lmsdemo1
python manage.py runserver
```

Create the virtual environment from PowerShell on Windows. A `.venv` copied from another machine or built under WSL won't activate; delete it and make a new one.

### `.env` variables
`.env` is git-ignored. Never commit it.

| Variable | Local | Production |
|---|---|---|
| `SECRET_KEY` | Can stay blank while `DEBUG=True` (a dev key is used) | **Required.** Long random string |
| `DEBUG` | `True` | `False` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | `.vercel.app` plus any custom domain |
| `CSRF_TRUSTED_ORIGINS` | blank | `https://<your-app>.vercel.app` |
| `POSTGRES_DB`, `_USER`, `_PASSWORD`, `_HOST`, `_PORT` | Leave `POSTGRES_DB` blank to use SQLite | Supabase **Transaction pooler** details (port `6543`) |
| `SUPABASE_S3_BUCKET`, `_ENDPOINT`, `_REGION`, `_ACCESS_KEY`, `_SECRET_KEY` | Leave `SUPABASE_S3_BUCKET` blank to save uploads to `media/` | From Supabase **Storage → S3** |

Management commands (`migrate`, `seed_demo`, `wipe_data`) run against whichever database `.env` points to. Check `POSTGRES_DB` before running anything destructive.

## Project layout
```
config/            settings.py, root urls.py, wsgi.py, test_runner.py
accounts/          School, User, AdminInvite, AuditLog; auth, invites, school admin, platform mode
  decorators.py      role guards (school_member_required, student_required, ...)
  middleware.py      ActingSchoolMiddleware (platform mode + per-school time zone)
  auth_backends.py   log in with username or email
  context_processors.py  values every page needs (sidebar badge)
  db_security.py     turns on Supabase RLS after migrate
  management/commands/   seed_demo, wipe_data
courses/           Course, Enrollment; catalogue, enroll/drop, roster
assignments/       Assignment, Submission, SubmissionVersion, Grade; submit, grading, gradebook
  filetypes.py       allowed upload types
  signals.py         delete uploaded files when their rows are deleted
templates/         base.html, dashboard.html + dashboard/ partials, one folder per app
static/css/        main.css (shell), dashboard.css, admin.css, login.css, platform.css
tests/             all tests (helpers.py has the shared two-school fixture)
docs/              this guide, BACKEND.md, TESTING.md, USER_GUIDE.md
```

## Architecture
The app is one Django project split into three apps. Inside each request the code falls into three layers:

| Layer | Where | Job |
|---|---|---|
| **Presentation** | `templates/`, `static/`, `views.py`, `urls.py` | Route the request, pick the template, build its context |
| **Business logic** | `forms.py`, `decorators.py`, `middleware.py`, scoping helpers (`school_courses`, `visible_assignments`), model methods (`Course.can_manage`, `Submission.save`), `signals.py`, `filetypes.py` | Roles, tenant scoping, validation, lateness, versioning, upload rules |
| **Data access** | `models.py`, migrations, the Django ORM | Tables, constraints, queries |

A typical request: URL → view, wrapped in a role decorator → the view gets objects through a school-scoped helper → a form validates any input → the model saves (computing things like `is_late`) → the template renders.

### Data model
```
School ─┬─< User (role: student | instructor | admin; platform = superuser, no school)
        ├─< AdminInvite (token, role, expires_at, invited_by)
        ├─< AuditLog
        └─< Course (instructor → User) ─┬─< Enrollment >─ User (student)
                                        └─< Assignment ─< Submission >─ User (student)
                                                            ├─< SubmissionVersion
                                                            └── Grade (one per submission)
```
- Only `School`, `User`, `Course`, `AdminInvite` and `AuditLog` store a school. Everything else reaches its school through its parent, so the school is never stored twice.
- `Enrollment` and `Submission` are unique per (student, course) and (assignment, student).
- `Grade.graded_by` and `AdminInvite.invited_by` are kept if that user is deleted (set to null).

## Design decisions and changes from the proposal
The approved proposal described a different frontend and a single-school system. These changes were made on purpose during design and implementation.

| Change | Proposal said | What we built | Why |
|---|---|---|---|
| **Frontend** | A frontend calling a web API | Server-rendered Django templates, no separate API | One codebase and one deployment for a 14-week project. Django's forms, CSRF protection and template inheritance come built in, and there's no API layer to secure separately. |
| **Multi-tenancy** | Not mentioned | Every user belongs to a **School**. Students join with a school join code; instructors and admins join by invite link; each school has its own admin. | Lets one deployment serve several schools with no data shared between them. It became the core security requirement: every query is scoped to the user's school. |
| **Mobile layout** | Listed as a feature | Deferred (LSM-20 canceled) | Time; the desktop layout came first. |
| **Email notifications** | — | Out of scope (LSM-62). Invite and password-reset links are shown to the admin to pass on, and in-app indicators (due soon, new grades, ungraded count) replace notification emails. | No mail service needed for the demo. |

Other decisions worth knowing:
- **Roles are set by the server only.** Sign-up always creates a student, create-school creates an admin, an invite gives the role it was issued with. No public form has a role field.
- **Superuser "platform mode"** lets the site owner view any school as its admin without being a member. The borrowed school and role exist for that request only and are never saved.
- **Resubmission keeps history.** Every submit creates a `SubmissionVersion`, so instructors can compare attempts. Resubmitting is locked once graded.
- **Deletes are POST forms with a JavaScript `confirm()`**, not separate confirmation pages.
- **The current grade is computed, not stored.** `Grade.percentage` and the dashboard's current grade are calculated from points, so they stay correct if an assignment's points change.
- **Login lockout** (django-axes): 5 failures per username + IP, 1-hour lock.
- **Supabase RLS** is turned on for every table with no policies. That closes Supabase's public REST API; Django connects as the table owner, so it's unaffected.

## Rules for new code
1. **Scope every query to the user's school.** Start from `school_courses(user)`, `school_assignments(user)` / `visible_assignments(user)`, or filter `school=request.user.school`. Never `Model.objects.all()` in a view. Look objects up inside the scoped queryset, so another school's IDs return 404.
2. **Put a role decorator on every view:** `school_member_required`, `student_required`, `instructor_required` or `admin_required`. For course or assignment edits, also check `course.can_manage(request.user)`.
3. **Never take a role from user input.** Set it in the form's `save()` or the view.
4. **Anything that changes data is POST-only** (`@require_POST`) with `{% csrf_token %}`.
5. **Admin actions call `audit(...)`** so they show in the Activity log.
6. **Calling `login()` yourself?** Pass `backend=LOGIN_BACKEND`. There are two auth backends, so Django can't pick one on its own.
7. **New model fields need a migration.** Run `python manage.py makemigrations`, commit the migration with the model change, and run `migrate` on Supabase after merging.
8. **Write tests** in `tests/`. Use `LMSTestCase` from `tests/helpers.py` for backend tests (two schools, stub templates) and include a cross-school check. See `TESTING.md`.
9. **Update `docs/BACKEND.md`** when you add a URL or change what a template receives.

### Adding a page, step by step
1. View in the app's `views.py`, with a decorator and scoped queries.
2. URL in the app's `urls.py`, with a `name`.
3. Template in `templates/<app>/`, extending `base.html`. Check `BACKEND.md` for the context.
4. A tests file, or tests added to an existing one.
5. A row in `BACKEND.md`.

## Team workflow
- **One branch per Linear ticket**, named after it: `LSM-97`, `LSM-100-file-types`, etc. Linear links branches that start with the ticket ID.
- **Commit messages start with the ticket:** `LSM-92: late/on-time and course filters on grading queue`.
- **Pull requests:**
  - Put `Fixes LSM-xx` in the description so Linear moves the ticket to Done on merge (`Part of LSM-xx` if it doesn't finish the ticket).
  - Say what changed and how it was tested.
  - Keep unrelated work in separate PRs.
- **Before pushing:** `python manage.py test` must pass.
- **After pulling:** run `pip install -r requirements.txt` (new packages) and `python manage.py migrate` (new migrations).
- **Linear statuses:** Todo → In Progress → In Review (PR open) → Done (merged). We also use **Partially Done** for parent tickets whose backend is finished but whose frontend isn't.

## Deployment
Production runs on **Vercel** (the app) and **Supabase** (PostgreSQL and file storage).

### How it fits together
- Vercel detects the Django project from `manage.py` and serves it through `config.wsgi`. It runs as serverless functions, so the app keeps no state on disk.
- **Database:** Supabase's **Transaction pooler** connection (port 6543), not the direct connection. Settings use `CONN_MAX_AGE=0` and SSL, which serverless functions need.
- **Uploads:** Vercel's file system is read-only, so uploads go to a **private** Supabase Storage bucket through `django-storages`. Files are served with signed, expiring URLs.
- **Static files:** `collectstatic` gathers `static/` into `staticfiles/` (`STATIC_ROOT`), which Vercel serves.
- **HTTPS:** when `DEBUG=False`, settings force HTTPS, secure cookies and HSTS. Vercel handles the certificates.

### Environment variables on Vercel
Set every production variable from the [`.env` table](#env-variables) in **Vercel → Settings → Environment Variables**, for both **Production** and **Preview** (PR preview deployments need them too, or they fail with `DisallowedHost`). Redeploy after changing variables.

### Shipping a change
1. Merge the PR into `main`. Vercel deploys automatically.
2. **If the PR has migrations**, run them against Supabase from your machine, with your `.env` pointed at Supabase:
   ```powershell
   python manage.py migrate
   ```
   This also turns RLS on for any new tables.
3. Check the site. Errors show in **Vercel → Logs** (settings print errors to the console because `DEBUG` is off).

### Supabase notes
- The Security Advisor should show no "RLS Disabled" errors. "RLS Enabled No Policy" and "Unused Index" notices are expected and harmless.
- Free Supabase projects pause after a period of inactivity. Check the dashboard before a demo and restore the project if it's paused; data is kept.

## Troubleshooting
| Error | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'axes'` (or any package) | Your `.venv` is out of date. `pip install -r requirements.txt` |
| `relation "..." does not exist` / page 500s after a merge | A migration hasn't been run on that database. `python manage.py migrate` |
| `ValueError: You have multiple authentication backends configured...` | A `login()` call without a backend. Use `login(request, user, backend=LOGIN_BACKEND)` |
| `ImproperlyConfigured: SECRET_KEY must be set in .env when DEBUG=False` | Set `SECRET_KEY`, or use `DEBUG=True` locally |
| `DisallowedHost` | Add the host to `ALLOWED_HOSTS` (on Vercel: for Production **and** Preview) |
| `CSRF verification failed` on the deployed site | Add the site's `https://` URL to `CSRF_TRUSTED_ORIGINS` |
| `TemplateDoesNotExist` | The page's template hasn't been built yet. Check the "Pages still to build" list in `BACKEND.md` |
| `.venv\Scripts\Activate.ps1` won't run | Delete `.venv` and recreate it from PowerShell. If scripts are blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Supabase warns "RLS Disabled in Public" | New tables were created without running our `migrate` hook. Run `python manage.py migrate` against Supabase |
| Uploads fail on Vercel | Check the five `SUPABASE_S3_*` variables and that the bucket exists |
