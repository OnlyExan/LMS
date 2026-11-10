"""Demo data: `python manage.py seed_demo` (safe to re-run)."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import School, User
from assignments.models import Assignment, Grade, Submission
from courses.models import Course, Enrollment

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

# (title, days from now, points)
ASSIGNMENTS = [("Homework 1", -14, 100), ("Homework 2", -5, 100),
               ("Project Proposal", -2, 50), ("Homework 3", 3, 100), ("Final Project", 21, 200)]


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

                enrolled = [e.student for e in course.enrollments.filter(status="active")]
                for a_idx, (a_title, days, pts) in enumerate(ASSIGNMENTS):
                    asg, _ = Assignment.objects.get_or_create(
                        course=course, title=a_title,
                        defaults=dict(due_date=now + timedelta(days=days),
                                      points_possible=pts,
                                      description=f"{a_title} for {code}."))
                    if days > 7:
                        continue  # final project: nothing submitted yet
                    for s_idx, stu in enumerate(enrolled):
                        if (s_idx + a_idx) % 5 == 4:
                            continue  # some missing submissions
                        sub = Submission.objects.filter(assignment=asg, student=stu).first()
                        if not sub:
                            sub = Submission(assignment=asg, student=stu,
                                             response_text=f"{stu.first_name}'s answer to {a_title}.")
                            sub.save()
                            # backdate: on time for most, late for every 3rd
                            late = (s_idx + a_idx) % 3 == 0
                            when = asg.due_date + timedelta(hours=6 if late else -6)
                            Submission.objects.filter(pk=sub.pk).update(
                                submitted_at=when, is_late=late)
                            sub.versions.update(submitted_at=when, is_late=late)
                        # older work is graded, newest past-due work left ungraded
                        if days <= -5 and not hasattr(sub, "grade"):
                            score = pts * Decimal(70 + (s_idx * 7 + a_idx * 5) % 30) / 100
                            Grade.objects.create(submission=sub, points_earned=round(score, 2),
                                                 feedback="Nice work." if score > pts * Decimal("0.85")
                                                 else "Review the rubric.",
                                                 graded_by=course.instructor)

            self.stdout.write(self.style.SUCCESS(
                f"{school_name}: join code {school.join_code}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Every demo user's password: {PASSWORD}\n"
            "  admin:      demo_admin   (Cal State Demo)\n"
            "  instructor: prof_gonzalez / prof_lee\n"
            "  student:    stu_maria, stu_jay, stu_kim, stu_omar, stu_tess\n"
            "  other school: rt_admin, rt_prof, rt_stu1, rt_stu2"))
