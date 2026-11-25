# Testing

How the LMS is tested, what the suite covers, and what it doesn't.

**Current result:** 241 tests, all passing (about 30 s).

## Running the tests

```powershell
python manage.py test                        # everything
python manage.py test tests.test_lockout     # one file
python manage.py test tests.test_auth.RegisterTests.test_bad_join_code   # one test
```

- Tests always run against a throwaway **SQLite** database, even if `.env` points at Supabase. `config/settings.py` sets `TESTING` when the command is `test` and skips the Postgres config, Supabase storage and the HTTPS redirect.
- Output comes from `config/test_runner.py`: one `PASSED` / `FAILED` / `ERROR` line per test, then a summary like `241 passed, 0 failed, 0 errors, 0 skipped (241 total)`.
- Run `pip install -r requirements.txt` after pulling. The suite imports `axes`, so a stale `.venv` fails with `No module named 'axes'`.

## How the tests are built

All tests live in `tests/`. The app folders' own `tests.py` files are empty.

### Shared fixture: `tests/helpers.py`
`LMSTestCase` builds two complete schools once per class (`setUpTestData`):

| Key | School A (`self.data["a"]`) | School B (`self.data["b"]`) |
|---|---|---|
| `school` | School A | School B |
| `admin`, `inst`, `stu` | `admin_a`, `inst_a`, `stu_a` | `admin_b`, `inst_b`, `stu_b` |
| `course` | `CSEa` taught by `inst_a`, `stu_a` enrolled | `CSEb` taught by `inst_b`, `stu_b` enrolled |
| `asg` | `HW1`, due in 3 days | `HW1`, due in 3 days |

Having two schools in every test is what lets the suite check tenant isolation everywhere: School A users try to reach School B data and must get 403/404.

`self.login(user)` logs a user in without a password (`force_login`). All users share the password `PW` for tests that go through the real login form.

### Stub templates vs real templates
`LMSTestCase` swaps in **stub templates** (each template name renders as `stub:<name>`). Backend tests therefore check views, permissions and context data without needing the frontend, and they keep passing while pages are still being built (for example, the missing assignment pages).

Tests that need to check what a page actually shows use plain `TestCase` with the **real templates**: `test_invites.test_pages_render_with_real_templates`, the dashboard `test_renders` tests, `test_lockout.py`, `test_register_page.py` and the page tests in the other per-page files.

### Speed settings
- Passwords use the fast MD5 hasher in tests only (`override_settings(PASSWORD_HASHERS=...)`).
- Upload tests write to a temp `MEDIA_ROOT` under `/tmp`, never to `media/` or Supabase.
- `test_lockout.py` silences django-axes' warning logs so the output stays readable.

## Coverage by file

Requirement IDs are from Progress Report 1. NFR names: **Tenant** = security, tenant isolation · **Escalation** = security, privilege escalation · **Credentials** = security, credentials · **CSRF** = security, request integrity · **Integrity** = reliability and data integrity · **Audit** = auditability · **Perf** = performance.

| File | Tests | Covers | Requirements | Linear |
|---|---|---|---|---|
| `test_auth.py` | 23 | Register, create school, invites, role decorators, login/logout, admin role/deactivate, dashboard context, superuser platform mode | FR-1.1–1.8, FR-4.1, Escalation, Tenant | LSM-6–15, 42 |
| `test_courses_assignments.py` | 27 | Models, course CRUD, enroll/drop, roster, assignment CRUD + filters, submit → grade → view, cross-tenant checks, upload cleanup | FR-2.1–2.6, FR-3.1–3.9, FR-4.5, Tenant, Integrity | LSM-21–41, 49, 50, 53, 63–65 |
| `test_file_types.py` | 14 | Allowed file types per assignment | FR-3.2, Escalation | LSM-100 |
| `test_account_settings.py` | 9 | Profile + password change, admin edits users | FR-1.6, FR-1.8, Credentials, Tenant | |
| `test_invites.py` | 8 | Single + bulk invites, duplicates, roles, real-page render | FR-1.4, FR-1.5, Escalation | LSM-10, 11 |
| `test_bulk_users.py` | 7 | Bulk role change / deactivate on Manage Users | FR-1.8, Tenant | |
| `test_school_settings.py` | 7 | Branding, invite-only, invite expiry, time zone, join code | FR-1.1, FR-1.2, FR-1.4 | LSM-58, 83, 96 |
| `test_activity_log.py` | 6 | Admin actions recorded, log page scoped + admin-only | Audit, Tenant | |
| `test_lockout.py` | 6 | django-axes login lockout | FR-1.6, Credentials | LSM-99 |
| `test_accept_invite.py` | 5 | Accept-invite page: valid, used, revoked | FR-1.5 | LSM-11, 104 |
| `test_password_reset.py` | 5 | Admin-issued one-time reset links | FR-1.8, Credentials, Tenant | |
| `test_register_page.py` | 5 | Student sign-up page with join code | FR-1.2, FR-1.3 | LSM-7, 13 |
| `test_user_detail.py` | 5 | User detail page for admins | FR-1.8, Tenant | |
| `test_manage_users_paging.py` | 4 | 25-per-page pagination on Manage Users | Perf | LSM-54, 94 |
| `test_student_dashboard.py` | 4 | Student dashboard data + render | FR-4.1, FR-4.2 | LSM-43, 73, 86 |
| `test_instructor_dashboard.py` | 3 | Instructor dashboard data + render | FR-4.1, FR-4.3 | LSM-44, 74, 87 |
| `test_invite_list.py` | 2 | Pending/expired invites, re-invite | FR-1.4, FR-1.8 | LSM-57, 82, 95 |
| `test_db_security.py` | 2 | Supabase RLS hook runs on Postgres only | Tenant | |
| `test_nav_badge.py` | 6 | Sidebar ungraded-count badge | FR-4.3, Tenant | LSM-97 |
| `test_submission_filters.py` | 6 | Grading queue late/on-time + course filters | FR-3.5, FR-4.5 | LSM-92 |
| `test_gradebook.py` | 22 | Gradebook % and cell labels; bulk grading; scoring missing work; course-page due date colors | FR-3.6, FR-3.7, FR-3.9, Integrity, Tenant | LSM-39, 103 |
| `test_polish.py` | 4 | Friendly 403/404 pages, no Save button for students' locked profile, seed data never dated in the future | Usability | |
| `test_security.py` | 8 | Lockout IP can't be spoofed off Vercel, unique emails (case-insensitive), logo must be a real PNG/JPG/WebP/GIF, names JS-escaped in confirm() dialogs | Security | |
| `test_student_grades.py` | 5 | Grades tab shows each course's %, per-course page lists every assignment with Graded/Submitted/Missing/Upcoming, other-school and dropped courses 404, instructors blocked | Functional, Security | |
| `test_letter_grades.py` | 10 | Default and custom letter scales, rounding matches the shown %, custom-scale validation (floor at 0, no duplicate letters or cutoffs, 0–100, ≤2 decimals), letters on student pages and gradebook, class average/high/low ignore dropped students | Functional | |
| `test_weighted_grades.py` | 16 | Weighted grade math (empty and 0-weight groups skipped and rescaled, ungrouped ignored), creating/renaming/removing groups and putting assignments in them, weights must total 100, bad rows rejected, another course's group can't be used or edited, pages without the weights section never wipe groups, gradebook and student pages use the weights, ungrouped warning, turning it off goes back to points | Functional, Security | |
| `test_review_fixes.py` | 10 | Assignment delete pop-up escapes the title, no "0 minutes remaining" on past-due work, `is_past_due`, Graded status on the assignment list, dropped students leave the grading queue / badge / dashboard counts (and come back if re-enrolled), student dashboard uses weights + letter, group dropdown label, resubmit uses a plain file picker (no Clear checkbox) and keeps the file when left empty | Security, Functional, Usability | |
| `test_letter_colors.py` | 4 | Letter colors: A green, B blue, C yellow, D/F red, others gray (+/– keep their letter's color), template filters, gradebook JS uses the same map | Usability | |
| `test_resubmit_after_grade.py` | 8 | Resubmitting graded work is blocked unless the assignment allows it; allowed resubmits keep the old grade (still counted), show Resubmitted, go back into the queue / badge / dashboard count, keep the original on-time status; saving on the grade page clears the flag, the gradebook only when the score changes; the assignment form saves the checkbox | Functional | |
| **Total** | **180** | | | |

### Security tests
These are the tests that back the security requirements. If one fails, treat it as a blocker.

| Risk | Tests |
|---|---|
| One school reading or changing another school's data | `test_courses_assignments.CrossTenantTests` (5 tests), plus the `*other_school*` / `*scoping*` tests in `test_account_settings`, `test_bulk_users`, `test_password_reset`, `test_user_detail`, `test_activity_log` |
| A user giving themselves a higher role | `test_auth.RegisterTests.test_cannot_self_assign_admin_role`, `test_auth.AdminManageTests.test_cannot_change_own_role`, `test_auth.PlatformModeTests.test_school_admin_cannot_grant_platform_role`, `test_invites.test_role_cannot_be_platform`, `test_bulk_users.test_rejects_bad_action_and_platform_role` |
| An instructor grading or editing someone else's course | `test_courses_assignments.AssignmentFlowTests.test_instructor_cannot_grade_other_course`, `CourseViewTests.test_other_instructor_cannot_edit`, `test_file_types.test_only_course_instructor_or_admin_can_change` |
| A superuser's "view as admin" leaking into the database | `test_auth.PlatformModeTests.test_borrowed_school_and_role_never_saved`, `test_full_save_while_acting_skips_school_role` |
| Password guessing | `test_lockout.py` (all 6) |
| Dangerous uploads (`.exe`, `.bat`, `x.pdf.exe`) | `test_file_types.test_executables_never_offered`, `test_disallowed_type_rejected`, `test_double_extension_exe_rejected` |
| Deletes through a GET link | `test_courses_assignments.CourseViewTests.test_delete_is_post_only_and_owner_only`, `test_assignment_delete_post_only` |
| Password reset links reused or used across schools | `test_password_reset.test_full_reset_flow_and_single_use`, `test_other_school_404_and_non_admin_403` |

## File-by-file detail

### `test_auth.py` (23)
| Class | Test | Checks |
|---|---|---|
| RegisterTests | `test_register_joins_school_as_student` | Sign-up with a join code creates a student in that school and logs them in |
| | `test_cannot_self_assign_admin_role` | A forged `role=admin` field is ignored; the account is a student (LSM-15) |
| | `test_bad_join_code` | Unknown code is rejected |
| CreateSchoolTests | `test_creates_school_and_admin` | Creates the school and its first user as admin |
| InviteTests | `test_admin_invites_instructor_and_accept` | Admin invite → accept → instructor in the right school |
| | `test_revoked_invite_invalid` | Revoked link can't be used |
| | `test_non_admin_cannot_invite` | Instructors and students get 403 |
| DecoratorTests | `test_anonymous_redirects_to_login` | Logged-out users go to login |
| | `test_admin_required`, `test_instructor_required` | Role guards allow/deny the right roles |
| | `test_user_without_school_blocked` | A user with no school can't use school pages |
| LoginTests | `test_login_logout` | Login redirects to the dashboard; logout (POST) works |
| AdminManageTests | `test_change_role_and_toggle` | Admin changes a role and deactivates/reactivates |
| | `test_cannot_change_own_role` | Admins can't demote or promote themselves |
| | `test_regenerate_join_code` | New code replaces the old one |
| DashboardTests | `test_role_context` | Each role gets its own dashboard data |
| PlatformModeTests | 7 tests | Superuser picks a school, acts as its admin, exits; borrowed school/role is never saved; regular users can't use platform mode |

### `test_courses_assignments.py` (27)
| Class | Checks |
|---|---|
| ModelTests (5) | Instructor must be in the course's school; deleting an instructor with courses is blocked; `is_late` computed on save (LSM-32); `Grade.percentage`; `__str__` methods |
| CourseViewTests (9) | Instructor owns courses they create; admin can't assign another school's instructor; duplicate code + term rejected; other instructors can't edit; enroll → drop → re-enroll; course filters (LSM-49); deletes are POST-only and owner-only; roster |
| AssignmentFlowTests (5) | Full submit → grade → student sees grade flow; empty submission rejected; unenrolled students get 404; instructors can't grade other courses (LSM-41); assignment CRUD + filters (LSM-29, 50) |
| CrossTenantTests (5) | School A users get 403/404 on every School B detail page, lists only show their school, admins can't manage other schools' users, students can't enroll across schools, the grading queue is scoped |
| FileCleanupTests (3) | Deleting an assignment deletes uploaded files; resubmitting keeps the old file as a version; deleting removes every version's file |

### `test_file_types.py` (14), LSM-100
New assignments get the default preset (PDF, Word, TXT, ZIP, images). Executables are never offered. Allowed types pass, disallowed types are rejected with "File type not allowed. Allowed: …", the check ignores case, and `essay.pdf.exe` is rejected. Text-only assignments have no upload field. The file picker's `accept` attribute matches the allowed types. Instructors set types on create/edit, can choose text-only, must pick at least one type or text-only, and can't submit an unknown type key. Only the course's instructor or a school admin can change the setting.

### `test_lockout.py` (6), LSM-99
After 5 failed logins the account is locked (HTTP 429, `locked_out.html`) even with the right password. 4 failures still allow login. A successful login resets the counter. The lock is per username + IP: other accounts from the same IP and the same account from another IP still work. Failed attempts are recorded in `AccessAttempt`.

### Admin pages
- **`test_account_settings.py` (9):** page renders for every role; students can't change their name even by posting it; instructors can; password change keeps you logged in; wrong old password rejected; admins edit users in their own school only; non-admins can't edit users; Manage Users shows edit buttons.
- **`test_bulk_users.py` (7):** bulk role change and deactivate/reactivate; never touches yourself or another school; rejects unknown actions and the platform role; redirect keeps your filters; admin-only; no checkbox on your own row.
- **`test_activity_log.py` (6):** role changes, edits, invites and settings changes are logged, one entry per user for bulk actions, nothing logged when nothing changed; the log page is school-scoped, filterable and admin-only; user detail shows that user's activity.
- **`test_password_reset.py` (5):** full reset flow, link works once; bad token rejected; other school 404 / non-admin 403; no link for yourself or deactivated users; button appears on Manage Users.
- **`test_user_detail.py` (5):** student and instructor detail pages show the right stats; scoped to your school and admin-only; actions return to the detail page; the users list links to it.
- **`test_manage_users_paging.py` (4):** 25 users per page; last page and bad page numbers handled; pager keeps filters; no pager with one page.
- **`test_school_settings.py` (7):** renders; saves every field; rejects bad values; invite expiry setting is used for new invites; invite-only blocks self sign-up; the school's time zone is applied; regenerating the join code keeps other settings.
- **`test_invites.py` (8), `test_invite_list.py` (2), `test_accept_invite.py` (5):** invite pages render with real templates; single and bulk invites; `next` redirect is honored but off-site URLs are ignored; inviting an existing member is rejected; invalid bulk emails reported; the platform role can't be invited; student invites work; expired invites can be re-sent; accept page shows the school, role and email, logs you in, keeps your input on errors without echoing passwords, and rejects used or revoked links.
- **`test_register_page.py` (5):** sign-up page pre-fills `?code=`; lowercase codes work; bad codes show an error and keep the input; invite-only schools block sign-up; login page links to sign-up.

### Dashboards
- **`test_student_dashboard.py` (4):** dropped courses are hidden; current grade per course is weighted by points; due-soon and overdue lists (overdue stops after 14 days); real page renders; submitted work leaves the due-soon list; empty state.
- **`test_instructor_dashboard.py` (3):** per-course student and ungraded counts, total students counted once across courses, due-soon with how many turned it in; real page renders; empty state.

### `test_db_security.py` (2)
The `post_migrate` hook that turns on Row Level Security runs on Postgres and does nothing on SQLite. The SQL itself was also checked once by hand against a real Postgres 16 database: after `migrate`, all 23 tables had RLS on and Django could still read them.

### Sidebar badge, grading filters, gradebook
- **`test_nav_badge.py` (6), LSM-97:** instructors see their own ungraded count, admins the whole school, another school sees 0, students get nothing; the count drops after grading; the real page shows the Grading badge for instructors and the Grades link for students.
- **`test_submission_filters.py` (6), LSM-92:** late only, on time only, or both; the course dropdown lists only courses you grade; filters are passed back to the page; on the real page the chips and dropdowns keep the selected filters.
- **`test_gradebook.py` (22).** `GradebookTests` (5): the % counts graded work only (171 / 200 = 85.5%, not 171 / 550) and matches the student dashboard's current grade; past-due work with no submission shows **Missing**, work not due yet shows "—"; graded late work keeps its Late badge; no graded work shows "—" for the %. `BulkGradingTests` (8): new and changed grades save together and keep existing feedback; unchanged cells aren't rewritten and blanks stay ungraded; one bad cell saves nothing and keeps what was typed; error messages for non-numbers, negatives, over the max and too many decimals; a graded cell can't be blanked; submissions from other courses (or made-up IDs) are ignored; only the course's instructor or a school admin can save; submitted and missing cells get an input. `MissingWorkGradingTests` (8): a 0 on a missing cell creates an empty, graded placeholder with no version history; it counts toward Earned / % and shows a Missing badge, not Late; it leaves the student's Missing list; blank stays missing; an invalid score saves nothing; not-yet-due, dropped-student and foreign cells are ignored; only past-due cells get an input; the admin's user detail doesn't count it as submitted or late. `CourseDueDateColorTests` (1): past due dates red, upcoming black.

## Not covered yet

| Gap | Why | Plan |
|---|---|---|
| Assignment pages (list, detail, form, submit) | Templates don't exist yet (LSM-34/102). The views are fully tested with stub templates. | Add real-template render tests when the pages land |
| JavaScript behavior (`confirm()` pop-ups, dropdowns that submit on change, invite pop-up) | The suite has no browser. The server side of each action is tested. | Manual check during the demo walkthrough (LSM-70) |
| Full suite on Postgres | Tests run on SQLite for speed. Only the RLS hook was checked on Postgres. | Optional: run once with a local Postgres before the final demo |
| Supabase file storage | Tests write uploads to a temp folder | Manual upload check on the deployed site |
| Performance NFR (500 users, 2 s pages) | No load test; pagination is tested instead | Time a few pages against the seeded demo data |
| Mobile layout | Out of scope (LSM-20 canceled) | — |
