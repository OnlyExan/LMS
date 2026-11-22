# Backend reference

Every URL, template and context variable, plus how the backend features work. Use this when building or changing a page.

**Status:** the backend is done for auth, school admin, courses, assignments, grading, dashboards and search. Every page has a template except the four assignment pages (`assignment_list`, `assignment_detail`, `assignment_form`, `submit`, LSM-34/102). Their views work and are tested; see [Pages still to build](#pages-still-to-build).

## Rules for templates
- Every page `{% extends "base.html" %}`.
- **POST-only actions** need `<form method="post">` with `{% csrf_token %}`: logout, enroll, drop, revoke invite, change role, toggle active, bulk users, edit user, reset-password link, delete course, delete assignment, exit platform mode.
- **Delete buttons** confirm with a browser pop-up, not a confirm page:
  ```html
  <form method="post" action="{% url 'courses:course_delete' course.pk %}"
        onsubmit="return confirm('Delete {{ course.code }}? This removes all its assignments, submissions and grades.');">
    {% csrf_token %}<button>Delete course</button>
  </form>
  ```
- Forms: `{{ form.as_p }}` works everywhere. Forms with uploads (submit, school settings) need `enctype="multipart/form-data"`.
- Flash messages: `base.html` loops `{% for m in messages %}`. Invite links and password-reset links are shown this way, since there's no email.
- Role checks: `user.role` is `"student"`, `"instructor"`, `"admin"` or `"platform"` (superusers only).
- Actions that accept `next` (invite, change role, toggle active, bulk, edit user, reset link) redirect back to it. Off-site URLs are ignored.

## On every page
| Name | Where it comes from | Use |
|---|---|---|
| `user.school` | Logged-in user | `.name`, `.logo`, `.brand_color` for the top bar and sidebar |
| `request.acting_school` | `ActingSchoolMiddleware` | Set while a superuser is viewing a school as its admin. Show the banner and the exit button |
| `nav_ungraded` | `accounts.context_processors.nav_counts` (LSM-97) | Ungraded submissions for the sidebar Grading badge. Instructors: own courses. Admins: whole school. Not set for students |

Dates and times display in the school's time zone (`School.timezone`); the middleware turns it on for each request.

## accounts

| URL name | Path | Template | Context |
|---|---|---|---|
| `home` | `/` | — | Redirects to `dashboard` |
| `accounts:login` | `/accounts/login/` | `accounts/login.html` | `form`. Accepts username **or** email |
| `accounts:logout` | `/accounts/logout/` | POST only → login | |
| `accounts:register` | `/accounts/register/` | `accounts/register.html` | `form` (join_code, username, first/last name, email, password1/2). `?code=ABC123` pre-fills the code |
| `accounts:create_school` | `/accounts/create-school/` | `accounts/create_school.html` | `form` (school_name + user fields) |
| `accounts:accept_invite` | `/accounts/invite/<token>/` | `accounts/accept_invite.html` or `accounts/invite_invalid.html` (410) | `form`, `invite` (`.school .role .email .invited_by .expires_at`) |
| `accounts:account_settings` | `/accounts/settings/` | `accounts/account_settings.html` | `profile_form`, `password_form`, `can_edit_details`. POST field `action` = `profile` or `password`. Students can't change name/email |
| `accounts:password_reset_confirm` | `/accounts/reset/<uidb64>/<token>/` | `accounts/password_reset_confirm.html` | Django's `form`, `validlink` |
| `accounts:password_reset_complete` | `/accounts/reset/done/` | `accounts/password_reset_complete.html` | |
| — (lockout) | any login after 5 failures | `accounts/locked_out.html` (HTTP 429) | See [Login lockout](#login-lockout) |

### School admin (`@admin_required`)
| URL name | Path | Template | Context |
|---|---|---|---|
| `accounts:invite_user` | `/accounts/admin/invites/new/` | `accounts/invite_user.html` | `form` (email, role), `bulk_form` (emails, role), `mode` (`single`/`bulk`), `next`, `max_bulk` (50). POST field `mode=bulk` for bulk |
| `accounts:invite_list` | `/accounts/admin/invites/` | `accounts/invite_list.html` | `invites`, `active`, `expired` (each `.email .role .is_valid .expires_at .invited_by`) |
| `accounts:revoke_invite` | `/accounts/admin/invites/<pk>/revoke/` | POST only | |
| `accounts:manage_users` | `/accounts/admin/users/` | `accounts/manage_users.html` | `users`/`page` (25 per page), `role_choices`, `q`, `role`, `filter_qs` (for pager links), `bulk_actions`. GET `?q=&role=&page=` |
| `accounts:bulk_users` | `/accounts/admin/users/bulk/` | POST only | Fields `action` (key of `bulk_actions`), `ids` (repeated). Never changes yourself |
| `accounts:user_detail` | `/accounts/admin/users/<pk>/` | `accounts/user_detail.html` | `target`, `role_choices`, `activity` (last 10). Students: `enrollments`, `submissions` (15 newest), `stats` (`submitted graded late average`). Others: `courses` (`.student_count .ungraded`) |
| `accounts:edit_user` | `/accounts/admin/users/<pk>/edit/` | POST only | first_name, last_name, email |
| `accounts:change_role` | `/accounts/admin/users/<pk>/role/` | POST only, field `role` | Can't change your own role or grant `platform` |
| `accounts:toggle_active` | `/accounts/admin/users/<pk>/toggle-active/` | POST only | |
| `accounts:reset_password_link` | `/accounts/admin/users/<pk>/reset-password/` | POST only | Flashes a one-time link (24 h). Not for yourself or deactivated users |
| `accounts:school_settings` | `/accounts/admin/settings/` | `accounts/school_settings.html` | `form` (name, logo ≤2 MB, brand_color `#rrggbb`, allow_self_signup, invite_expiry_days, timezone), `school` (`.join_code`). POST `regenerate_join_code` for a new code |
| `accounts:activity_log` | `/accounts/admin/activity/` | `accounts/activity_log.html` | `page` (50 per page), `action`, `q`, `action_choices`, `filter_qs`. GET `?action=&q=&page=` |

### Platform mode (superusers)
| URL name | Path | Template | Context |
|---|---|---|---|
| `accounts:switch_school` | `/accounts/platform/schools/` | `accounts/switch_school.html` | `schools` (`.member_count .course_count`), `acting_school`. POST field `school` |
| `accounts:exit_school` | `/accounts/platform/exit/` | POST only | |

## dashboard — `/dashboard/` (`dashboard`) → `dashboard.html`
`dashboard.html` includes `dashboard/_student.html`, `_instructor.html` or `_admin.html`. Always: `role`, `school`.
- **student:** `enrollments` (active only; each `.course` and `.current_grade`, % weighted by points, `None` if nothing graded), `due_soon` (due in 7 days, not submitted), `overdue` (past due in the last 14 days, never submitted), `recent_grades` (graded in the last 7 days)
- **instructor:** `courses` (`.student_count .ungraded`), `ungraded_count`, `student_total` (counted once across courses), `due_soon` (`.submitted` = how many turned it in)
- **admin:** `student_count`, `instructor_count`, `admin_count`, `course_count`, `pending_invites`

## courses

| URL name | Path | Template | Context |
|---|---|---|---|
| `courses:course_list` | `/courses/` | `courses/course_list.html` | `courses` (`.student_count`), `enrolled_ids`, `terms`, `filters` (`term code q mine`). GET `?term=&code=&q=&mine=1` |
| `courses:course_detail` | `/courses/<pk>/` | `courses/course_detail.html` | `course`, `enrollment`, `is_enrolled`, `can_manage`, `assignments` (empty for students until they enroll) |
| `courses:course_create` | `/courses/new/` | `courses/course_form.html` | `form`, `course=None`. Admins pick the instructor; instructors own what they create |
| `courses:course_edit` | `/courses/<pk>/edit/` | `courses/course_form.html` | `form`, `course` |
| `courses:course_delete` | `/courses/<pk>/delete/` | POST only | |
| `courses:enroll` / `courses:drop` | `/courses/<pk>/enroll/`, `/drop/` | POST only (students) | Drop marks the enrollment `dropped`; re-enrolling reactivates it |
| `courses:roster` | `/courses/<pk>/roster/` | `courses/roster.html` | `course`, `enrollments` (`.student .status`) |

## assignments and grading

| URL name | Path | Template | Context |
|---|---|---|---|
| `assignments:assignment_list` | `/assignments/` | `assignments/assignment_list.html` ⚠️ | `assignments`, `submitted_ids`, `courses`, `filters` (`course q due_after due_before`). GET `?course=&q=&due_after=YYYY-MM-DD&due_before=&upcoming=1` |
| `assignments:assignment_create` | `/assignments/course/<course_pk>/new/` | `assignments/assignment_form.html` ⚠️ | `form`, `course`, `assignment=None` |
| `assignments:assignment_edit` | `/assignments/<pk>/edit/` | `assignments/assignment_form.html` ⚠️ | `form`, `course`, `assignment` |
| `assignments:assignment_delete` | `/assignments/<pk>/delete/` | POST only | |
| `assignments:assignment_detail` | `/assignments/<pk>/` | `assignments/assignment_detail.html` ⚠️ | `assignment`, `course`, `is_past_due`. **Student:** `submission`, `versions`, `grade`, `can_submit`. **Instructor/admin:** `submissions`, `submission_count`, `ungraded_count`, `enrolled_count` |
| `assignments:submit` | `/assignments/<pk>/submit/` | `assignments/submit.html` ⚠️ | `form`, `assignment`, `submission` (existing; can resubmit until graded) |
| `assignments:submission_list` | `/assignments/submissions/` | `assignments/submission_list.html` | `submissions` (`.student .assignment .is_late .grade`), `status`, `filters` (`course q late`), `courses` (dropdown: courses you grade). GET `?status=ungraded|graded|all&course=&late=&q=`, where `late=1` is late only and `late=0` on time only (LSM-92) |
| `assignments:grade_submission` | `/assignments/submissions/<pk>/grade/` | `assignments/grade_form.html` | `form` (points_earned, feedback), `submission`, `grade`, `versions` |
| `assignments:my_grades` | `/assignments/grades/` | `assignments/my_grades.html` | `grades` (use `grade.percentage`) |
| `assignments:gradebook` | `/assignments/course/<course_pk>/gradebook/` | `assignments/gradebook.html` | `course`, `assignments`, `total_possible`, `rows` → each `{student, cells:[{assignment, submission, grade, missing}], earned, graded_possible, percent}`. `percent` = earned / points possible **on graded work only** (same as the dashboard's current grade; `None` if nothing graded). `missing` = past due and never submitted |

⚠️ = template not built yet.

Uploaded files: `{{ submission.file_upload.url }}`. Submission history: `versions` is newest first; each has `.number .response_text .file_upload .submitted_at .is_late`. Old files are kept on resubmit.

### Allowed file types (LSM-100)
- **Assignment form** has two extra fields: `text_only` (checkbox, "Text response only") and `file_types` (checkboxes from the safe list). `{{ form.as_p }}` renders both. You must pick at least one type or text only.
- **Submit form:** for text-only assignments the `file_upload` field is removed entirely. Otherwise the file input already has `accept=".pdf,.docx,…"` and help text "Allowed: …". Wrap the file input in `{% if form.file_upload %}` if you lay fields out by hand.
- **On the assignment**, for detail pages: `assignment.allowed_extensions` (list like `[".pdf", ".docx"]`), `assignment.accepts_files` (False = text only), `assignment.accept_attr` (comma-joined, for a hand-built `<input type="file">`).

## Pages still to build
The four ⚠️ templates above. With `{{ form.as_p }}` the LSM-100 file-type checkboxes and the limited file picker appear automatically. The assignment list should include the filter form from LSM-91 (course dropdown from `courses`, `due_after`/`due_before` date inputs, "Upcoming only" checkbox `upcoming=1`, search `q`).

## How the backend works

### Apps and models
| App | Models |
|---|---|
| `accounts` | `School` (name, slug, join_code, logo, brand_color, allow_self_signup, invite_expiry_days, timezone), `User` (custom; `school`, `role`), `AdminInvite`, `AuditLog` |
| `courses` | `Course` (unique per school + code + term), `Enrollment` (status `active`/`dropped`) |
| `assignments` | `Assignment` (`allowed_file_types`), `Submission` (one per student per assignment), `SubmissionVersion` (every attempt), `Grade` (one per submission) |

### Tenant isolation
Every query starts from the user's school: `school_courses(user)` in `courses/views.py`, `school_assignments(user)` and `visible_assignments(user)` in `assignments/views.py`, and `school=request.user.school` lookups in `accounts/views.py`. Objects from another school return 404. `Course.clean()` also blocks an instructor from a different school. New views must use these helpers instead of `Model.objects.all()`.

### Roles and access
- Roles are set on the server only: sign-up makes a student, create-school makes an admin, an invite gives the role it was issued with. No form has a role field except the admin's change-role control, which can't grant `platform`.
- Decorators in `accounts/decorators.py`: `school_member_required`, `student_required`, `instructor_required` (instructors and admins), `admin_required`. Each also requires login and a school.
- Editing a course or assignment also checks `Course.can_manage(user)`: the course's instructor or a school admin.

### Superuser platform mode
Superusers have role `platform` and no school. On `/accounts/platform/schools/` they pick a school and browse as its admin. `ActingSchoolMiddleware` borrows that school and the admin role for the request only; `User.save()` never writes them to the database.

### Login and lockout
- `accounts.auth_backends.UsernameOrEmailBackend` lets people log in with a username or an email.
- <a id="login-lockout"></a>**django-axes** locks a username + IP pair after 5 failed logins for 1 hour (`AXES_*` in `settings.py`). A successful login resets the count. The lockout page is `accounts/locked_out.html`.
- Because two backends are configured, any code that calls `login()` itself must pass `backend=LOGIN_BACKEND` (see `accounts/views.py`).

### Audit log
`audit(request, action, target, details)` in `accounts/views.py` records admin actions in `AuditLog`: role changes, activate/deactivate, user edits, reset links, invites sent and revoked, settings changes and join-code resets. Names are copied into the entry so the log still reads correctly after a user is deleted.

### Uploads and storage
- Local development saves files under `media/`. When `SUPABASE_S3_BUCKET` is set, files go to Supabase Storage through `django-storages`.
- Limits: submissions 10 MB, school logo 2 MB. Allowed submission types come from `assignments/filetypes.py`; dangerous extensions (`.exe`, `.bat`, `.msi`, `.ps1`, `.js`, …) are always rejected, including `name.pdf.exe`.
- Every submit or resubmit saves a `SubmissionVersion`. Signals in `assignments/signals.py` delete a file from storage when its row is deleted (after the database commit).

### Database security (Supabase)
After every `migrate` on Postgres, `accounts/db_security.py` turns on Row Level Security for every table in `public`. This closes Supabase's public REST API. Django connects as the table owner, so it isn't affected. Don't add RLS policies: the app doesn't use the Supabase API, and a policy would reopen access. Supabase's "RLS Enabled No Policy" and "Unused Index" notices are expected.

### Management commands
| Command | What it does |
|---|---|
| `python manage.py seed_demo` | Add demo schools, users, courses, assignments and grades (safe to re-run). `--flush` resets, `--clear` deletes demo data only |
| `python manage.py wipe_data` | Delete everything except superusers |

These run against whatever database `.env` points to.

## Tests
See [`docs/TESTING.md`](TESTING.md). `python manage.py test` runs 159 tests with stub templates, so missing pages don't fail it.
