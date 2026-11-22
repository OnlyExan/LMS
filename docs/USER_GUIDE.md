# LMS User Guide

How to use the LMS as a student, instructor or school admin.

The LMS is shared by several schools. Everyone belongs to one school and only ever sees that school's people, courses and grades.

> **Note:** the assignment pages (assignment list, assignment details, creating an assignment and submitting work) are still being built. The steps for them below describe how they work behind the scenes; button names may change slightly when the pages are finished.

## Contents
- [Getting started](#getting-started)
- [Students](#students)
- [Instructors](#instructors)
- [School admins](#school-admins)
- [Platform admins](#platform-admins)
- [Account settings](#account-settings)
- [Troubleshooting](#troubleshooting)

## Getting started

### Ways to join
| You are… | How you join |
|---|---|
| A **student** | Get your school's **join code** from your instructor or school admin. On the login page click **Student? Sign up with a join code**, enter the code and fill in your details. Your admin may also send you an invite link instead. |
| An **instructor** or **admin** | Your school admin sends you an **invite link**. Open it, choose a username and password, and click **Create account & join**. The link works once and expires (7 days by default). |
| Starting a **new school** | On the login page click **Create a School**. You fill in your details and the school's name, and you become its first admin. |

If a sign-up link says **This invite has expired**, ask your school admin to send a new one.

### Logging in and out
- Log in with your **username or email** and password.
- **Log out** is at the top right. You're also logged out when you close the browser, and after 8 hours at most, which keeps shared lab computers safe.
- After **5 wrong passwords** in a row, login is locked for **1 hour** for that account on that computer. Wait, or ask your admin for a password reset link.

### Finding your way around
The sidebar on the left has:
- **Account**: your profile and password
- **Dashboard**: your home page
- **Courses**: your school's courses
- **Grades** (students) or **Grading** (instructors and admins). The red number on **Grading** is how many submissions are waiting for a grade.
- **Admin** (school admins only)

The arrow at the bottom of the sidebar collapses it to icons only.

## Students

### Your dashboard
- **Missing**: assignments past their due date (within the last 14 days) that you never turned in.
- **Due this week**: assignments due in the next 7 days that you haven't submitted yet, with a **Submit** button. If there's nothing, you'll see "You're all caught up".
- **My courses**: each course you're enrolled in with its instructor and your **current grade** (points earned out of points possible on graded work).
- **Recent grades**: anything graded in the last 7 days, with a link to **See all grades**.

### Joining and leaving a course
1. Go to **Courses**. Use the search box, the code box, the term dropdown or **My courses** to narrow the list.
2. Open a course and click **Enroll**.
3. To leave, open the course and click **Drop course**. You can enroll again later; your past work is kept.

You can only see a course's assignments after you enroll.

### Submitting an assignment
1. Open the assignment from your dashboard, the course page or the assignments list.
2. Type a response, attach a file, or both.
   - Your instructor chooses which **file types** are allowed. The page lists them (for example "Allowed: .pdf, .docx"), and the file picker only shows those types.
   - Some assignments are **text only** and have no file upload.
   - Files must be under **10 MB**.
3. Submit. If you submit after the due date, it's saved and marked **Late**.

**Resubmitting:** you can resubmit as many times as you like **until the assignment is graded**. Every attempt is kept, so your instructor can see your earlier versions.

### Seeing your grades
- **Grades** in the sidebar (or **See all grades** on your dashboard) lists every graded assignment with points, percent and your instructor's feedback.
- Only you, your instructors and your school's admins can see your grades.

## Instructors

### Your dashboard
- **Courses taught**, **Students** (counted once even if they're in several of your courses) and **To grade**.
- **My courses**: each course with its student count and either **N to grade** or **All graded**. Shortcuts to the **Roster** and **Gradebook**.
- **Due this week**: your assignments due in the next 7 days and how many students have turned each one in.
- **Quick actions**: **+ New course**, **Grading queue**, **All assignments**.

### Courses
1. **Courses → + New course**. Enter the **Course code**, **Title**, **Term** and an optional **Description**, then click **Create course**. You're the instructor of any course you create.
   - A course code can only be used once per term in your school.
2. On the course page:
   - **Edit** changes the details.
   - **Roster** lists enrolled students with their status.
   - **Gradebook** shows every student against every assignment.
   - **Delete course** asks you to confirm first, because it removes all of the course's assignments, submissions and grades.

### Assignments
1. On a course page click **+ Assignment**.
2. Fill in the title, description, **due date** and **points possible**.
3. Choose what students can turn in:
   - Tick the **Allowed file types**: PDF, Word, plain text/Markdown, ZIP, images, PowerPoint, Excel/CSV or source code. New assignments start with PDF, Word, text, ZIP and images ticked.
   - Or tick **Text response only (no file upload)**.
   - Programs and scripts (.exe, .bat, .msi and similar) are never allowed.
4. Save. You can edit or delete the assignment later from its page.

### Grading
1. Click **Grading** in the sidebar (or **Grading queue** on your dashboard). It opens on **Ungraded**.
2. Narrow the list with the **Ungraded / Graded / All** buttons, the course dropdown, the **late / on time** dropdown and the search box (student name or assignment).
3. Open a submission. You'll see the student's response, a **Download file** link, whether it was **Late**, and the **Version history** if they resubmitted.
4. Enter **Points earned** and optional **Feedback**, then click **Save grade**. You go back to the queue.

To change a grade, find the submission under **Graded** and save it again. Once a submission is graded, the student can no longer resubmit it. You can only grade submissions in courses you teach.

### Gradebook
**Gradebook** (from the course page or your dashboard) shows a table of every enrolled student against every assignment, with **Late** and **Ungraded** marked, plus each student's total points and percent.

## School admins

Admins can do everything an instructor can, for every course in the school, plus manage the school itself.

### Your dashboard
Counts of **Students**, **Instructors**, **Admins**, **Courses** and **Pending invites**, the **Student join code**, and quick actions: **Invite instructor / admin**, **Manage users**, **New course**, **School settings**.

### The Admin area
**Admin** in the sidebar has four tabs: **Settings**, **Users**, **Invites** and **Activity**.

#### Inviting people
1. **+ Invite user** (on any admin page) or **Invites → Invite someone**.
2. **Single invite:** enter an email, pick a role (Student, Instructor or Admin) and click **Create invite**.
   **Bulk invite:** paste up to 50 emails (separated by commas, semicolons, spaces or new lines), pick one role for everyone and click **Create invites**.
3. The LMS doesn't send email. Copy the link it shows (or use **Copy** / **Copy all pending links** on the Invites tab) and send it yourself.

On the **Invites** tab:
- **Pending** shows who you invited, the role, who sent it and when it expires. **Revoke** stops a link from working.
- **Expired** shows expired or revoked links, with **Re-invite** to send a new one.

Students don't need an invite; they can sign up with the join code.

#### Managing users (Users tab)
- Search by name, username or email, and filter with **All / Students / Instructors / Admins**. 25 people per page.
- **Role** dropdown: changes someone's role straight away.
- **Edit**: fix someone's name or email. Students can't change their own, so do it here.
- **Reset password**: creates a one-time link (valid 24 hours) for you to give them. Their old password keeps working until they use it.
- **Deactivate** / **Reactivate**: a deactivated user can't log in, but their work and grades are kept.
- **Bulk actions:** tick several people (or the top box for the whole page), choose an action from **Choose action…** and click **Apply**.
- Click a name for their **detail page**: students show enrollments, recent submissions and stats (submitted, graded, late, average grade); instructors show the courses they teach. It also lists recent admin activity for that person.

You can't change your own role or deactivate yourself.

#### School settings (Settings tab)
- **Branding:** school name, logo (PNG, JPG, WebP or GIF, under 2 MB, shown in the top bar) and brand color (used for the sidebar, buttons and highlights).
- **Enrollment & access:**
  - **Allow students to sign up with the join code**: turn off to make the school invite-only. Existing students aren't affected.
  - **Invite links expire after**: applies to new invites only.
- **Academic:** the school's **time zone**. Due dates and times show in this time zone for everyone.
- **Student join code:** **Copy** it to share, or **Regenerate code** if it leaked. The old code stops working immediately.

#### Activity log (Activity tab)
A record of admin actions in your school: role changes, deactivations, user edits, reset links, invites sent and revoked, settings changes and join-code changes. Filter by action or search by person. Newest first, 50 per page.

## Platform admins

Platform admins run the whole LMS (the site's superuser accounts). They don't belong to a school.

- **Platform** in the sidebar lists every school with its member count, course count and join code.
- **View as admin** opens a school as if you were its admin. A banner shows which school you're viewing; click **Exit** (or **Platform** in the sidebar) to leave.
- **Django admin** opens Django's built-in database admin for support work.

## Account settings
Click **Account** in the sidebar.
- **Profile:** first name, last name and email. Students can't change these; ask your school admin.
- **Change password:** enter your old password and the new one twice. You stay logged in on this device.
- The panel on the right shows your role, school, when you joined and your last login.

## Troubleshooting
| Problem | What to do |
|---|---|
| "Invalid username/email or password" | Check caps lock. You can use your username or your email. |
| "Too many failed attempts, try again later" | Wait 1 hour, or ask your school admin for a password reset link. |
| "This invite has expired" | The link was used, revoked or timed out. Ask your admin to **Re-invite** you. |
| The join code doesn't work | It may have been regenerated, or your school may be invite-only. Ask your instructor or admin. |
| "File type not allowed" | Your instructor limited the file types. The message lists the allowed ones; save your file in one of them. |
| I can't resubmit | The assignment has already been graded. |
| I can't change my name | Students can't. Ask your school admin to fix it from **Users → Edit**. |
| I can't see a course's assignments | Enroll in the course first. |
