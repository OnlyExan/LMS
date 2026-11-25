from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import School, User
from assignments.models import Assignment, Grade, Submission
from courses.models import Course, Enrollment
from tests.helpers import PW


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class GradebookTests(TestCase):
    """Gradebook %: graded work only (matches the student dashboard). Cell labels."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        s = School.objects.create(name="GB U")
        cls.inst = User.objects.create_user("gbinst", password=PW, school=s, role=User.INSTRUCTOR)
        cls.stu = User.objects.create_user("gbstu", password=PW, school=s, role=User.STUDENT)
        cls.course = Course.objects.create(school=s, code="GB1", title="GB", instructor=cls.inst, term="Fall")
        Enrollment.objects.create(student=cls.stu, course=cls.course)
        mk = lambda title, days, pts: Assignment.objects.create(
            course=cls.course, title=title, due_date=now + timedelta(days=days), points_possible=pts)
        cls.hw1 = mk("HW1", -10, 100)      # graded on time: 91/100
        cls.hw2 = mk("HW2", -5, 100)       # submitted late, graded: 80/100
        cls.prop = mk("Proposal", -3, 50)  # submitted, not graded
        cls.hw3 = mk("HW3", -1, 100)       # never submitted, past due -> Missing
        cls.final = mk("Final", 9, 200)    # not due yet -> "—"
        for a, pts, late in ((cls.hw1, 91, False), (cls.hw2, 80, True)):
            sub = Submission.objects.create(assignment=a, student=cls.stu, response_text="x")
            Submission.objects.filter(pk=sub.pk).update(is_late=late)  # save() recomputes
            Grade.objects.create(submission=sub, points_earned=pts, graded_by=cls.inst)
        Submission.objects.create(assignment=cls.prop, student=cls.stu, response_text="x")

    def setUp(self):
        self.client.force_login(self.inst)
        self.r = self.client.get(reverse("assignments:gradebook", args=[self.course.pk]))
        self.row = self.r.context["rows"][0]

    def test_percent_uses_graded_work_only(self):
        self.assertEqual(self.row["earned"], 171)
        self.assertEqual(self.row["graded_possible"], 200)  # not 550
        self.assertAlmostEqual(float(self.row["percent"]), 85.5)
        self.assertEqual(self.r.context["total_possible"], 550)  # header still shows the course total

    def test_matches_student_dashboard(self):
        self.client.force_login(self.stu)
        enr = self.client.get(reverse("dashboard")).context["enrollments"][0]
        self.assertAlmostEqual(float(enr.current_grade), float(self.row["percent"]))

    def test_cell_states(self):
        cells = {c["assignment"].title: c for c in self.row["cells"]}
        self.assertTrue(cells["HW3"]["missing"])
        self.assertFalse(cells["Final"]["missing"])  # not due yet is not missing
        self.assertIsNone(cells["Proposal"]["grade"])
        self.assertIsNotNone(cells["Proposal"]["submission"])

    def test_page_labels(self):
        html = self.r.content.decode()
        self.assertIn("Missing", html)
        self.assertIn('title="Not due yet"', html)
        self.assertIn("85.5%", html)
        self.assertIn('<span class="gb-possible-val">200</span>', html)
        self.assertNotIn("31.1%", html)  # old bug: 171 / 550 = 31.1%
        # late badge kept on the graded late HW2 cell
        hw2 = html.split(f'name="g-{self.hw2.submissions.get().pk}"', 1)[1].split("</td>", 1)[0]
        self.assertIn('value="80"', hw2)
        self.assertIn("Late", hw2)

    def test_no_graded_work_shows_dash(self):
        Grade.objects.filter(submission__student=self.stu).delete()
        r = self.client.get(reverse("assignments:gradebook", args=[self.course.pk]))
        self.assertIsNone(r.context["rows"][0]["percent"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BulkGradingTests(TestCase):
    """Editable gradebook: one Save for many cells, validated, all-or-nothing, scoped."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        s = School.objects.create(name="Bulk U")
        cls.inst = User.objects.create_user("binst", password=PW, school=s, role=User.INSTRUCTOR)
        cls.inst2 = User.objects.create_user("binst2", password=PW, school=s, role=User.INSTRUCTOR)
        cls.admin = User.objects.create_user("badmin", password=PW, school=s, role=User.ADMIN)
        cls.stu = User.objects.create_user("bstu", password=PW, school=s, role=User.STUDENT)
        cls.stu2 = User.objects.create_user("bstu2", password=PW, school=s, role=User.STUDENT)
        cls.course = Course.objects.create(school=s, code="BG1", title="BG", instructor=cls.inst, term="Fall")
        for st in (cls.stu, cls.stu2):
            Enrollment.objects.create(student=st, course=cls.course)
        cls.hw = Assignment.objects.create(course=cls.course, title="HW", points_possible=50,
                                           due_date=now - timedelta(days=1))
        cls.hw2 = Assignment.objects.create(course=cls.course, title="HW2", points_possible=100,
                                            due_date=now - timedelta(days=1))
        cls.sub_new = Submission.objects.create(assignment=cls.hw, student=cls.stu, response_text="a")
        cls.sub_graded = Submission.objects.create(assignment=cls.hw, student=cls.stu2, response_text="b")
        Grade.objects.create(submission=cls.sub_graded, points_earned=40, graded_by=cls.inst, feedback="ok")
        # stu2 never submitted HW2 -> Missing, not editable
        # another course (other instructor) with a submission we must not be able to grade from here
        other = Course.objects.create(school=s, code="BG2", title="Other", instructor=cls.inst2, term="Fall")
        Enrollment.objects.create(student=cls.stu, course=other)
        oa = Assignment.objects.create(course=other, title="X", points_possible=10, due_date=now)
        cls.other_sub = Submission.objects.create(assignment=oa, student=cls.stu, response_text="c")

    def url(self):
        return reverse("assignments:gradebook", args=[self.course.pk])

    def post(self, data, user=None):
        self.client.force_login(user or self.inst)
        return self.client.post(self.url(), data)

    def test_saves_new_and_changed_grades_together(self):
        r = self.post({f"g-{self.sub_new.pk}": "45.5", f"g-{self.sub_graded.pk}": "38"})
        self.assertRedirects(r, self.url())
        g_new = Grade.objects.get(submission=self.sub_new)
        self.assertEqual((g_new.points_earned, g_new.graded_by), (45.5, self.inst))
        g_old = Grade.objects.get(submission=self.sub_graded)
        self.assertEqual(g_old.points_earned, 38)
        self.assertEqual(g_old.feedback, "ok")  # feedback untouched
        msgs = [str(m) for m in r.wsgi_request._messages]
        self.assertIn("Saved 2 grades.", msgs)

    def test_unchanged_cells_not_rewritten(self):
        before = Grade.objects.get(submission=self.sub_graded).graded_at
        r = self.post({f"g-{self.sub_new.pk}": "", f"g-{self.sub_graded.pk}": "40"})
        self.assertRedirects(r, self.url())
        self.assertEqual(Grade.objects.get(submission=self.sub_graded).graded_at, before)
        self.assertFalse(Grade.objects.filter(submission=self.sub_new).exists())  # blank stays ungraded
        self.assertIn("No changes to save.", [str(m) for m in r.wsgi_request._messages])

    def test_one_bad_cell_saves_nothing(self):
        r = self.post({f"g-{self.sub_new.pk}": "45", f"g-{self.sub_graded.pk}": "60"})  # 60 > 50
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Grade.objects.filter(submission=self.sub_new).exists())
        self.assertEqual(Grade.objects.get(submission=self.sub_graded).points_earned, 40)
        cells = {c["submission"].pk: c for row in r.context["rows"] for c in row["cells"] if c["submission"]}
        self.assertEqual(cells[self.sub_graded.pk]["error"], "Must be between 0 and 50.")
        self.assertEqual(cells[self.sub_new.pk]["value"], "45")  # typed values kept
        self.assertContains(r, "Must be between 0 and 50.")

    def test_validation_messages(self):
        for raw, msg in (("abc", "Enter a number."), ("-1", "Must be between 0 and 50."),
                         ("4.555", "Use at most 2 decimal places."), ("nan", "Enter a number.")):
            r = self.post({f"g-{self.sub_new.pk}": raw})
            cells = {c["submission"].pk: c for row in r.context["rows"] for c in row["cells"] if c["submission"]}
            self.assertEqual(cells[self.sub_new.pk]["error"], msg, raw)
        self.assertFalse(Grade.objects.filter(submission=self.sub_new).exists())

    def test_cannot_clear_existing_grade(self):
        r = self.post({f"g-{self.sub_graded.pk}": ""})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Grade.objects.filter(submission=self.sub_graded).exists())

    def test_other_course_submission_ignored(self):
        self.post({f"g-{self.other_sub.pk}": "5", "g-999999": "1", "g-abc": "1"})
        self.assertFalse(Grade.objects.filter(submission=self.other_sub).exists())

    def test_only_course_instructor_or_admin(self):
        data = {f"g-{self.sub_new.pk}": "10"}
        for user in (self.inst2, self.stu):
            self.assertIn(self.post(data, user).status_code, (403, 404), user.username)
        self.assertFalse(Grade.objects.filter(submission=self.sub_new).exists())
        self.assertEqual(self.post(data, self.admin).status_code, 302)  # school admin can
        self.assertEqual(Grade.objects.get(submission=self.sub_new).graded_by, self.admin)

    def test_page_has_inputs_for_submitted_and_missing_work(self):
        self.client.force_login(self.inst)
        html = self.client.get(self.url()).content.decode()
        self.assertIn(f'name="g-{self.sub_new.pk}"', html)
        self.assertIn(f'name="g-{self.sub_graded.pk}" value="40"', html)
        # 2 submitted cells + HW2 missing for both students (past due, never submitted)
        self.assertEqual(html.count('class="gb-input"'), 4)
        self.assertIn(f'name="m-{self.stu2.pk}-{self.hw2.pk}"', html)
        self.assertIn("Missing", html)
        self.assertIn('id="gbSave"', html)
        self.assertIn("csrfmiddlewaretoken", html)

    def test_column_headers_link_to_assignment(self):
        self.client.force_login(self.inst)
        html = self.client.get(self.url()).content.decode()
        self.assertIn(f'href="{reverse("assignments:assignment_detail", args=[self.hw2.pk])}">', html)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MissingWorkGradingTests(TestCase):
    """Typing a score (usually 0) into a Missing cell grades work that was never turned in."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        s = School.objects.create(name="Miss U")
        cls.inst = User.objects.create_user("minst", password=PW, school=s, role=User.INSTRUCTOR)
        cls.stu = User.objects.create_user("mstu", password=PW, school=s, role=User.STUDENT)
        cls.dropped = User.objects.create_user("mdrop", password=PW, school=s, role=User.STUDENT)
        cls.course = Course.objects.create(school=s, code="MS1", title="MS", instructor=cls.inst, term="Fall")
        Enrollment.objects.create(student=cls.stu, course=cls.course)
        Enrollment.objects.create(student=cls.dropped, course=cls.course, status=Enrollment.DROPPED)
        cls.past = Assignment.objects.create(course=cls.course, title="Past", points_possible=20,
                                             due_date=now - timedelta(days=2))
        cls.future = Assignment.objects.create(course=cls.course, title="Future", points_possible=20,
                                               due_date=now + timedelta(days=2))

    def setUp(self):
        self.client.force_login(self.inst)
        self.url = reverse("assignments:gradebook", args=[self.course.pk])

    def key(self, student, a):
        return f"m-{student.pk}-{a.pk}"

    def test_zero_on_missing_creates_graded_placeholder(self):
        r = self.client.post(self.url, {self.key(self.stu, self.past): "0"})
        self.assertRedirects(r, self.url)
        sub = Submission.objects.get(student=self.stu, assignment=self.past)
        self.assertTrue(sub.is_empty)
        self.assertEqual(sub.grade.points_earned, 0)
        self.assertEqual(sub.grade.graded_by, self.inst)
        self.assertEqual(sub.versions.count(), 0)  # no fake version history

    def test_graded_missing_counts_and_shows_missing_badge(self):
        self.client.post(self.url, {self.key(self.stu, self.past): "0"})
        r = self.client.get(self.url)
        row = r.context["rows"][0]
        self.assertEqual((row["earned"], row["graded_possible"]), (0, 20))
        self.assertEqual(float(row["percent"]), 0.0)
        cell = row["cells"][0]
        self.assertIsNotNone(cell["grade"])
        html = r.content.decode()
        sub = Submission.objects.get(student=self.stu, assignment=self.past)
        after = html.split(f'name="g-{sub.pk}"', 1)[1].split("</td>", 1)[0]
        self.assertIn("Missing", after)
        self.assertNotIn(">Late<", after)

    def test_student_dashboard_no_longer_lists_it_as_missing(self):
        self.client.force_login(self.stu)
        self.assertEqual(len(self.client.get(reverse("dashboard")).context["overdue"]), 1)
        self.client.force_login(self.inst)
        self.client.post(self.url, {self.key(self.stu, self.past): "0"})
        self.client.force_login(self.stu)
        self.assertEqual(len(self.client.get(reverse("dashboard")).context["overdue"]), 0)

    def test_blank_missing_cell_stays_missing(self):
        r = self.client.post(self.url, {self.key(self.stu, self.past): ""})
        self.assertRedirects(r, self.url)
        self.assertFalse(Submission.objects.exists())

    def test_invalid_score_saves_nothing(self):
        r = self.client.post(self.url, {self.key(self.stu, self.past): "25"})  # max 20
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Submission.objects.exists())
        cell = r.context["rows"][0]["cells"][0]
        self.assertEqual((cell["value"], cell["error"]), ("25", "Must be between 0 and 20."))

    def test_not_due_dropped_and_foreign_cells_ignored(self):
        self.client.post(self.url, {
            self.key(self.stu, self.future): "0",      # not due yet
            self.key(self.dropped, self.past): "0",    # not actively enrolled
            f"m-{self.stu.pk}-999999": "0",            # not an assignment in this course
            "m-abc-1": "0",
        })
        self.assertFalse(Submission.objects.exists())

    def test_only_past_due_cells_have_inputs(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn(f'name="{self.key(self.stu, self.past)}"', html)
        self.assertNotIn(f'name="{self.key(self.stu, self.future)}"', html)

    def test_user_detail_doesnt_count_placeholder_as_submitted(self):
        self.client.post(self.url, {self.key(self.stu, self.past): "0"})
        admin = User.objects.create_user("madmin", password=PW, school=self.course.school, role=User.ADMIN)
        self.client.force_login(admin)
        stats = self.client.get(reverse("accounts:user_detail", args=[self.stu.pk])).context["stats"]
        self.assertEqual((stats["submitted"], stats["late"], stats["graded"]), (0, 0, 1))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CourseDueDateColorTests(TestCase):
    def test_past_red_future_black(self):
        now = timezone.now()
        s = School.objects.create(name="Due U")
        inst = User.objects.create_user("dinst", password=PW, school=s, role=User.INSTRUCTOR)
        c = Course.objects.create(school=s, code="DU1", title="DU", instructor=inst, term="Fall")
        Assignment.objects.create(course=c, title="Old", due_date=now - timedelta(days=1))
        Assignment.objects.create(course=c, title="New", due_date=now + timedelta(days=1))
        self.client.force_login(inst)
        html = self.client.get(reverse("courses:course_detail", args=[c.pk])).content.decode()
        self.assertEqual(html.count("due-when due-past"), 1)
        self.assertEqual(html.count("due-when due-future"), 1)
        self.assertIn('title="Past due"', html)
