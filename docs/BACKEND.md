# Backend → Frontend contract

Backend is done for auth, courses, assignments, grading, dashboard, search, and school admin.
Frontend just needs to create the templates below. Every template should `{% extends "base.html" %}`.

> Folder note: templates go in `templates/assignments/` — the existing `templates/assigments/` folder is misspelled, rename it.

## Rules
- **POST-only actions** (use a `<form method="post">` with `{% csrf_token %}`): logout, enroll, drop, revoke invite, change role, toggle active, and confirming deletes.
- Forms: `{{ form.as_p }}` works for everything. Submit forms with file uploads need `enctype="multipart/form-data"`.
- Flash messages: loop `{% for m in messages %}` in `base.html`.
- Role checks in templates: `user.role` is `"student"`, `"instructor"`, or `"admin"`.
- Nav links (by URL name): `dashboard`, `courses:course_list`, `assignments:assignment_list`, `assignments:my_grades` (student), `assignments:submission_list` (instructor/admin), `accounts:manage_users`, `accounts:invite_list`, `accounts:school_settings` (admin).

## accounts

| URL name | Path | Template | Context |
|---|---|---|---|
| `accounts:login` | `/accounts/login/` | `accounts/login.html` | `form` |
| `accounts:logout` | `/accounts/logout/` | — POST only, redirects to login | |
| `accounts:register` | `/accounts/register/` | `accounts/register.html` | `form` (username, first/last name, email, password1/2, join_code) |
| `accounts:create_school` | `/accounts/create-school/` | `accounts/create_school.html` | `form` (school_name + user fields) |
| `accounts:accept_invite` | `/accounts/invite/<token>/` | `accounts/accept_invite.html` / `accounts/invite_invalid.html` | `form`, `invite` |
| `accounts:invite_user` | `/accounts/admin/invites/new/` | `accounts/invite_user.html` | `form` (email, role) |
| `accounts:invite_list` | `/accounts/admin/invites/` | `accounts/invite_list.html` | `invites` (each has `.email .role .is_valid .expires_at .invited_by`) |
| `accounts:revoke_invite` | `/accounts/admin/invites/<pk>/revoke/` | POST only | |
| `accounts:manage_users` | `/accounts/admin/users/` | `accounts/manage_users.html` | `users`, `role_choices`, `q`, `role`; GET filters `?q=&role=` |
| `accounts:change_role` | `/accounts/admin/users/<pk>/role/` | POST only, field `role` | |
| `accounts:toggle_active` | `/accounts/admin/users/<pk>/toggle-active/` | POST only | |
| `accounts:school_settings` | `/accounts/admin/settings/` | `accounts/school_settings.html` | `form` (name, regenerate_join_code), `school` (`.join_code`) |

| `accounts:switch_school` | `/accounts/platform/schools/` | `accounts/switch_school.html` | superuser only. `schools` (each `.member_count .course_count`), `acting_school`; POST field `school` |
| `accounts:exit_school` | `/accounts/platform/exit/` | POST only | |

Superuser platform mode: a superuser picks a school and browses as its admin. `request.acting_school` is set while acting (show a banner + exit button in `base.html`).

The invite link shows up as a flash message after creating an invite (we're not sending email).

## dashboard — `/` (`dashboard`) → `dashboard.html`
Always: `role`, `school`.
- **student**: `enrollments` (`.course`), `due_soon` (assignments due in 7 days, not yet submitted), `recent_grades` (graded in last 7 days)
- **instructor**: `courses` (each has `.student_count`), `ungraded_count`
- **admin**: `student_count`, `instructor_count`, `admin_count`, `course_count`, `pending_invites`

## courses

| URL name | Path | Template | Context |
|---|---|---|---|
| `courses:course_list` | `/courses/` | `courses/course_list.html` | `courses` (`.student_count`), `enrolled_ids`, `terms`, `filters`; GET `?term=&code=&q=&mine=1` |
| `courses:course_detail` | `/courses/<pk>/` | `courses/course_detail.html` | `course`, `enrollment`, `is_enrolled`, `can_manage`, `assignments` |
| `courses:course_create` | `/courses/new/` | `courses/course_form.html` | `form`, `course=None` |
| `courses:course_edit` | `/courses/<pk>/edit/` | `courses/course_form.html` | `form`, `course` |
| `courses:course_delete` | `/courses/<pk>/delete/` | `courses/course_confirm_delete.html` | `course` (POST to confirm) |
| `courses:enroll` / `courses:drop` | `/courses/<pk>/enroll/`, `/drop/` | POST only (students) | |
| `courses:roster` | `/courses/<pk>/roster/` | `courses/roster.html` | `course`, `enrollments` (`.student .status`) |

## assignments + grading

| URL name | Path | Template | Context |
|---|---|---|---|
| `assignments:assignment_list` | `/assignments/` | `assignments/assignment_list.html` | `assignments`, `submitted_ids`, `courses`, `filters`; GET `?course=&q=&due_after=YYYY-MM-DD&due_before=&upcoming=1` |
| `assignments:assignment_create` | `/assignments/course/<course_pk>/new/` | `assignments/assignment_form.html` | `form`, `course`, `assignment=None` |
| `assignments:assignment_edit` | `/assignments/<pk>/edit/` | `assignments/assignment_form.html` | `form`, `course`, `assignment` |
| `assignments:assignment_delete` | `/assignments/<pk>/delete/` | `assignments/assignment_confirm_delete.html` | `assignment` |
| `assignments:assignment_detail` | `/assignments/<pk>/` | `assignments/assignment_detail.html` | `assignment`, `course`, `is_past_due` + **student:** `submission`, `versions`, `grade`, `can_submit` · **instructor/admin:** `submissions`, `submission_count`, `ungraded_count`, `enrolled_count` |
| `assignments:submit` | `/assignments/<pk>/submit/` | `assignments/submit.html` | `form` (response_text, file_upload), `assignment`, `submission` (existing, can resubmit until graded) |
| `assignments:submission_list` | `/assignments/submissions/` | `assignments/submission_list.html` | `submissions` (`.student .assignment .is_late .grade`), `status`, `filters`; GET `?status=ungraded|graded|all&course=&q=` |
| `assignments:grade_submission` | `/assignments/submissions/<pk>/grade/` | `assignments/grade_form.html` | `form` (points_earned, feedback), `submission`, `grade`, `versions` |
| `assignments:my_grades` | `/assignments/grades/` | `assignments/my_grades.html` | `grades` (use `grade.percentage`) |
| `assignments:gradebook` | `/assignments/course/<course_pk>/gradebook/` | `assignments/gradebook.html` | `course`, `assignments`, `total_possible`, `rows` → each `{student, cells:[{assignment, submission, grade}], earned, percent}` |

Uploaded files: `{{ submission.file_upload.url }}`.
Submission history: `versions` is newest-first; each has `.number .response_text .file_upload .submitted_at .is_late`. Old files are kept on resubmit.

## Running tests
`python manage.py test` — 38 tests, they use stub templates so they pass without the frontend.
