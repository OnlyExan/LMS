"""Demo data: `python manage.py seed_demo` (safe to re-run)."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import School, User
from assignments.models import Assignment, Grade, Submission
from courses.grading import PLUS_MINUS_SCALE
from courses.models import AssignmentGroup, Course, Enrollment

PASSWORD = "lmsdemo1"  # passes Django's default validators

SCHOOLS = {
    "Cal State Demo": {
        "admin": ("demo_admin", "Ava", "Admin"),
        "instructors": [("prof_gonzalez", "Gabriel", "Gonzalez"), ("prof_lee", "Dana", "Lee")],
        "students": [("stu_maria", "Maria", "Lopez"), ("stu_jay", "Jay", "Patel"),
                     ("stu_kim", "Kim", "Nguyen"), ("stu_omar", "Omar", "Hassan"),
                     ("stu_tess", "Tess", "Brown")],
        "courses": [
            ("CSE4100", "Systems Administration & Self-Hosting", "prof_gonzalez"),
            ("CSE3100", "Database Systems", "prof_lee"),
            ("CSE4400", "Applied Machine Learning", "prof_gonzalez"),
            # Maria isn't enrolled here, so her My courses and All tabs differ
            ("CSE4600", "Web Application Development", "prof_lee"),
        ],
    },
    # second tenant so isolation is visible in the demo
    "Riverside Tech": {
        "admin": ("rt_admin", "Rob", "Turner"),
        "instructors": [("rt_prof", "Sam", "Rivera")],
        "students": [("rt_stu1", "Lena", "Cho"), ("rt_stu2", "Max", "Ford")],
        "courses": [("CS101", "Intro to Programming", "rt_prof")],
    },
}

# one course shows the grading options; the rest stay on total points + default A-F
COURSE_GRADING = {
    "CSE4400": {
        "scale": PLUS_MINUS_SCALE,
        # (group, weight %, assignments)
        "groups": [("Homework", 40, ["Homework 1", "Homework 2", "Homework 3"]),
                   ("Projects", 35, ["Project Proposal"]),
                   ("Final", 25, ["Final Project"])],
        "grade_recent": True,  # grade the proposals too, so two groups count and weights matter
    },
}

# (title, days from now, points, what students turn in, allowed file types)
ASSIGNMENTS = [("Homework 1", -14, 100, Assignment.BOTH, ["pdf", "word", "text"]),
               ("Homework 2", -5, 100, Assignment.BOTH, ["pdf", "word", "text"]),
               ("Project Proposal", -2, 50, Assignment.TEXT, []),
               ("Homework 3", 3, 100, Assignment.BOTH, ["pdf", "word", "text"]),
               ("Final Project", 21, 200, Assignment.FILE, ["pdf", "word", "zip"])]

# rough level per student so the demo shows every letter color (A green ... D/F red)
STUDENT_LEVEL = {"stu_jay": 95, "stu_maria": 87, "stu_tess": 81, "stu_kim": 74, "stu_omar": 60,
                 "rt_stu1": 90, "rt_stu2": 78}

# (course, assignment, student): allows resubmission after grading, and the student resubmitted
RESUBMITTED = ("CSE4400", "Homework 2", "stu_maria")

# left unsubmitted so the student's "Due in the next 7 days" isn't empty in the demo
NOT_YET_SUBMITTED = {("stu_maria", "Homework 3")}


class Command(BaseCommand):
    help = "Seed demo schools, users, courses, assignments, submissions and grades."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true",
                            help="Delete existing demo schools first.")
        parser.add_argument("--clear", action="store_true",
                            help="Delete demo schools and stop (no reseed).")

    @transaction.atomic
    def handle(self, *args, flush=False, clear=False, **opts):
        now = timezone.now()
        if flush or clear:
            for name in SCHOOLS:
                for s in School.objects.filter(name=name):
                    # PROTECT on instructor -> delete courses before users
                    Course.objects.filter(school=s).delete()
                    s.delete()  # cascades users, invites, enrollments, submissions, grades
        if clear:
            self.stdout.write(self.style.SUCCESS("Demo data deleted."))
            return

        for school_name, cfg in SCHOOLS.items():
            school, _ = School.objects.get_or_create(name=school_name)
            users = {}

            def mk(username, first, last, role):
                u, created = User.objects.get_or_create(
                    username=username,
                    defaults=dict(first_name=first, last_name=last, school=school, role=role,
                                  email=f"{username}@demo.edu"))
                if created:
                    validate_password(PASSWORD, u)  # follow the same rules as real signups
                    u.set_password(PASSWORD)
                    u.save()
                users[username] = u
                return u

            mk(*cfg["admin"], User.ADMIN)
            for i in cfg["instructors"]:
                mk(*i, User.INSTRUCTOR)
            students = [mk(*s, User.STUDENT) for s in cfg["students"]]

            for idx, (code, title, inst) in enumerate(cfg["courses"]):
                course, _ = Course.objects.get_or_create(
                    school=school, code=code, term="Fall 2026",
                    defaults=dict(title=title, instructor=users[inst],
                                  description=f"{title} — demo course."))
                # not every student in every course
                for j, stu in enumerate(students):
                    if (j + idx) % 4 != 3:
                        Enrollment.objects.get_or_create(student=stu, course=course)

                grading = COURSE_GRADING.get(code, {})
                if grading:
                    course.grading_scale = grading["scale"]
                    course.weighted_grading = True
                    course.save(update_fields=["grading_scale", "weighted_grading"])

                enrolled = [e.student for e in course.enrollments.filter(status="active")]
                for a_idx, (a_title, days, pts, kind, types) in enumerate(ASSIGNMENTS):
                    asg, _ = Assignment.objects.get_or_create(
                        course=course, title=a_title,
                        defaults=dict(due_date=now + timedelta(days=days),
                                      points_possible=pts,
                                      description=f"{a_title} for {code}."))
                    # demo settings (also applied to an already-seeded database)
                    allow = (code, a_title) == RESUBMITTED[:2]
                    if (asg.submission_type, asg.allowed_file_types, asg.allow_resubmit) != (kind, types, allow):
                        asg.submission_type, asg.allowed_file_types, asg.allow_resubmit = kind, types, allow
                        asg.save(update_fields=["submission_type", "allowed_file_types", "allow_resubmit"])
                    for pos, (g_name, weight, titles) in enumerate(grading.get("groups", [])):
                        if a_title in titles:
                            group, _ = AssignmentGroup.objects.update_or_create(
                                course=course, name=g_name, defaults=dict(weight=weight, position=pos))
                            if asg.group_id != group.pk:
                                asg.group = group
                                asg.save(update_fields=["group"])
                    if days > 7:
                        continue  # final project: nothing submitted yet
                    for s_idx, stu in enumerate(enrolled):
                        if (s_idx + a_idx) % 5 == 4 or (stu.username, a_title) in NOT_YET_SUBMITTED:
                            continue  # some missing submissions
                        sub = Submission.objects.filter(assignment=asg, student=stu).first()
                        if not sub:
                            sub = Submission(assignment=asg, student=stu,
                                             response_text=f"{stu.first_name}'s answer to {a_title}.")
                            sub.save()
                            # backdate: on time for most, late for every 3rd
                            late = (s_idx + a_idx) % 3 == 0
                            when = asg.due_date + timedelta(hours=6 if late else -6)
                            if when > now:  # still due in the future: turned in early, can't be late
                                when, late = now - timedelta(hours=2 + s_idx), False
                            Submission.objects.filter(pk=sub.pk).update(
                                submitted_at=when, is_late=late)
                            sub.versions.update(submitted_at=when, is_late=late)
                        # older work is graded, newest past-due work left ungraded
                        # weighted demo course also grades its newest work (queue keeps the others')
                        recent = grading.get("grade_recent") and days < 0
                        if (days <= -5 or recent) and not hasattr(sub, "grade"):
                            level = STUDENT_LEVEL.get(stu.username, 80) + (a_idx * 3) % 7 - 3  # +/-3 per assignment
                            score = pts * Decimal(min(level, 100)) / 100
                            Grade.objects.create(submission=sub, points_earned=round(score, 2),
                                                 feedback="Nice work." if score > pts * Decimal("0.85")
                                                 else "Review the rubric.",
                                                 graded_by=course.instructor)
                            # graded a day after it was due (instead of "just now")
                            Grade.objects.filter(submission=sub).update(
                                graded_at=min(asg.due_date + timedelta(days=1), now - timedelta(hours=1)))

                        # one resubmission after grading, so "Resubmitted" shows in the queue and gradebook
                        if (code, a_title, stu.username) == RESUBMITTED and hasattr(sub, "grade") \
                                and not sub.needs_regrade:
                            sub.refresh_from_db()
                            sub.response_text = f"{stu.first_name}'s revised answer to {a_title}, after feedback."
                            sub.save(keep_late=True)  # new version, now; grade stays until regraded

            self.stdout.write(self.style.SUCCESS(
                f"{school_name}: join code {school.join_code}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Every demo user's password: {PASSWORD}\n"
            "  admin:      demo_admin   (Cal State Demo)\n"
            "  CSE4400 is weighted (Homework 40 / Projects 35 / Final 25) with a +/- scale;\n"
            "    Maria resubmitted Homework 2 there after grading (shows as Resubmitted)\n"
            "  Project Proposal is Text only, Final Project is File upload only (drop zone)\n"
            "  Maria is in 3 of the 4 Cal State courses (not CSE4600), so Courses > All shows one more\n"
            "  instructor: prof_gonzalez / prof_lee\n"
            "  student:    stu_maria, stu_jay, stu_kim, stu_omar, stu_tess\n"
            "  other school: rt_admin, rt_prof, rt_stu1, rt_stu2"))
