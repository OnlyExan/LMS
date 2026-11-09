from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import School, User
from assignments.models import Assignment
from courses.models import Course, Enrollment

TEMPLATE_NAMES = """accounts/login.html accounts/accept_invite.html accounts/create_school.html
accounts/invite_invalid.html accounts/invite_list.html accounts/invite_user.html
accounts/manage_users.html accounts/register.html accounts/school_settings.html
assignments/assignment_confirm_delete.html assignments/assignment_detail.html
assignments/assignment_form.html assignments/assignment_list.html assignments/grade_form.html
assignments/gradebook.html assignments/my_grades.html assignments/submission_list.html
assignments/submit.html courses/course_confirm_delete.html courses/course_detail.html
courses/course_form.html courses/course_list.html courses/roster.html dashboard.html""".split()

# stub templates so backend tests don't depend on the frontend
STUB_TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "OPTIONS": {
        "loaders": [("django.template.loaders.locmem.Loader",
                     {n: f"stub:{n}" for n in TEMPLATE_NAMES})],
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]

PW = "Str0ng-pass-123"


@override_settings(TEMPLATES=STUB_TEMPLATES, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LMSTestCase(TestCase):
    """Two schools (A, B), each with admin/instructor/student, one course, one assignment."""

    @classmethod
    def setUpTestData(cls):
        cls.data = {}
        for tag in ("a", "b"):
            school = School.objects.create(name=f"School {tag.upper()}")
            admin = User.objects.create_user(f"admin_{tag}", password=PW, school=school, role=User.ADMIN)
            inst = User.objects.create_user(f"inst_{tag}", password=PW, school=school, role=User.INSTRUCTOR)
            stu = User.objects.create_user(f"stu_{tag}", password=PW, school=school, role=User.STUDENT)
            course = Course.objects.create(school=school, code=f"CSE{tag}", title="Web Dev",
                                           instructor=inst, term="Fall 2026")
            Enrollment.objects.create(student=stu, course=course)
            asg = Assignment.objects.create(course=course, title="HW1",
                                            due_date=timezone.now() + timedelta(days=3))
            cls.data[tag] = dict(school=school, admin=admin, inst=inst, stu=stu,
                                 course=course, asg=asg)

    def login(self, user):
        self.client.force_login(user)
