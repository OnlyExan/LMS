# LMS — CSE 4050 Group Project

## Setup
1. Clone the repo
2. `python -m venv .venv`
3. `.\.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate` (Mac/Linux)
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` (`Copy-Item .env.example .env`). The defaults run locally on SQLite as-is; fill in `SECRET_KEY` before deploying
6. `python manage.py migrate`
7. `python manage.py createsuperuser`
8. `python manage.py seed_demo` (optional demo data)
9. `python manage.py runserver`

## Apps
- `accounts/` — School, User, AdminInvite, auth
- `courses/` — Course, Enrollment
- `assignments/` — Assignment, Submission, Grade

## Demo data
All demo users share the password `lmsdemo1`.

| Role | Username |
|---|---|
| Admin | `demo_admin` |
| Instructor | `prof_gonzalez`, `prof_lee` |
| Student | `stu_maria`, `stu_jay`, `stu_kim`, `stu_omar`, `stu_tess` |
| Second school | `rt_admin`, `rt_prof`, `rt_stu1`, `rt_stu2` |

## Data commands
| Command | What it does |
|---|---|
| `python manage.py seed_demo` | Add demo data (safe to re-run) |
| `python manage.py seed_demo --flush` | Reset demo data (delete + reseed) |
| `python manage.py seed_demo --clear` | Delete demo data only |
| `python manage.py wipe_data` | Delete everything except superusers |
| `python manage.py flush` | Delete everything, superusers included |

These run against whatever database `.env` points to: Supabase if `POSTGRES_*` is set, local SQLite if blank. Check before wiping.

## Tests
`python manage.py test` — runs with stub templates, so it doesn't need the frontend.

## Docs
- `docs/BACKEND.md` — every URL, template, and context variable for the frontend
