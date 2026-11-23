from datetime import timedelta
from decimal import Decimal

from django.http import QueryDict
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from assignments.models import Assignment, Grade, Submission
from courses.forms import CourseForm
from courses.grading import DEFAULT_SCALE, letter_for
from courses.models import Enrollment
from tests.helpers import LMSTestCase


class LetterForTests(SimpleTestCase):
    def test_default_scale(self):
        self.assertEqual(letter_for(DEFAULT_SCALE, 95), "A")
        self.assertEqual(letter_for(DEFAULT_SCALE, 90), "A")
        self.assertEqual(letter_for(DEFAULT_SCALE, 89.9), "B")
        self.assertEqual(letter_for(DEFAULT_SCALE, 0), "F")
        self.assertIsNone(letter_for(DEFAULT_SCALE, None))

    def test_uses_shown_rounding(self):
        # 89.96 shows as 90.0%, so it should be an A, not a B
        self.assertEqual(letter_for(DEFAULT_SCALE, Decimal("89.96")), "A")
        self.assertEqual(letter_for(DEFAULT_SCALE, Decimal("89.94")), "B")


class CourseScaleFormTests(LMSTestCase):
    def _post(self, mode, rows=()):
        a = self.data["a"]
        q = QueryDict(mutable=True)
        q.update({"code": a["course"].code, "title": "T", "term": a["course"].term,
                  "description": "", "scale_mode": mode})
        for letter, minimum in rows:
            q.appendlist("scale_letter", letter)
            q.appendlist("scale_min", minimum)
        return CourseForm(q, instance=a["course"], user=a["inst"])

    def test_default_clears_custom(self):
        c = self.data["a"]["course"]
        c.grading_scale = [["P", 50], ["NP", 0]]
        c.save()
        form = self._post("default")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().grading_scale)

    def test_custom_saved_sorted(self):
        form = self._post("custom", [("C", "70"), ("A", "90"), ("F", "0"), ("B", "80.5"), ("", "")])
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().grading_scale, [["A", 90], ["B", 80.5], ["C", 70], ["F", 0]])

    def test_custom_errors(self):
        bad = [
            [("A", "90")],                          # only one letter
            [("A", "90"), ("B", "80")],             # no 0 floor
            [("A", "90"), ("a", "0")],              # duplicate letter
            [("A", "90"), ("B", "90"), ("F", "0")],  # duplicate minimum
            [("A", "120"), ("F", "0")],             # out of range
            [("A", "x"), ("F", "0")],               # not a number
            [("ABCD", "90"), ("F", "0")],           # letter too long
            [("A", "90.123"), ("F", "0")],          # too many decimals
        ]
        for rows in bad:
            self.assertFalse(self._post("custom", rows).is_valid(), rows)


class LetterGradePagesTests(LMSTestCase):
    def setUp(self):
        a = self.data["a"]
        self.course, self.stu, self.inst = a["course"], a["stu"], a["inst"]
        Enrollment.objects.update_or_create(student=self.stu, course=self.course,
                                            defaults={"status": Enrollment.ACTIVE})
        self.asg = a["asg"]
        self.asg.points_possible = Decimal("100")
        self.asg.save()
        sub = Submission.objects.create(assignment=self.asg, student=self.stu, response_text="x")
        Grade.objects.create(submission=sub, points_earned=Decimal("85"), graded_by=self.inst)

    def test_student_pages_show_letter(self):
        self.login(self.stu)
        r = self.client.get(reverse("assignments:my_grades"))
        self.assertEqual(r.context["courses"][0]["letter"], "B")
        r = self.client.get(reverse("assignments:course_grades", args=[self.course.pk]))
        self.assertEqual(r.context["letter"], "B")

    def test_custom_scale_changes_letter(self):
        self.course.grading_scale = [["Pass", 80], ["Fail", 0]]
        self.course.save()
        self.login(self.stu)
        r = self.client.get(reverse("assignments:my_grades"))
        self.assertEqual(r.context["courses"][0]["letter"], "Pass")

    def test_gradebook_letter_and_class_stats(self):
        # second student scored 65 -> class avg 75, high 85, low 65
        from accounts.models import User
        s2 = User.objects.create_user("stu2", password="x", school=self.data["a"]["school"], role=User.STUDENT)
        Enrollment.objects.create(student=s2, course=self.course)
        sub2 = Submission.objects.create(assignment=self.asg, student=s2, response_text="y")
        Grade.objects.create(submission=sub2, points_earned=Decimal("65"), graded_by=self.inst)
        # a dropped student's grade must not count
        s3 = User.objects.create_user("stu3", password="x", school=self.data["a"]["school"], role=User.STUDENT)
        Enrollment.objects.create(student=s3, course=self.course, status=Enrollment.DROPPED)
        sub3 = Submission.objects.create(assignment=self.asg, student=s3, response_text="z")
        Grade.objects.create(submission=sub3, points_earned=Decimal("5"), graded_by=self.inst)

        self.login(self.inst)
        r = self.client.get(reverse("assignments:gradebook", args=[self.course.pk]))
        letters = sorted(row["letter"] for row in r.context["rows"])
        self.assertEqual(letters, ["B", "D"])
        i = r.context["assignments"].index(self.asg)
        st = r.context["class_stats"]["assignments"][i]
        self.assertEqual((st["avg"], st["high"], st["low"], st["count"]), (75, 85, 65, 2))
        self.assertEqual(r.context["class_stats"]["percent"], 75)
        self.assertEqual(r.context["class_stats"]["letter"], "C")

    def test_instructor_can_save_custom_scale(self):
        self.login(self.inst)
        c = self.course
        self.client.post(reverse("courses:course_edit", args=[c.pk]), {
            "code": c.code, "title": c.title, "term": c.term, "description": "",
            "scale_mode": "custom", "scale_letter": ["H", "P", "F"], "scale_min": ["90", "60", "0"]})
        c.refresh_from_db()
        self.assertEqual(c.grading_scale, [["H", 90], ["P", 60], ["F", 0]])


class CourseFormTemplateTests(SimpleTestCase):
    def test_scripts_only_in_content_block(self):
        with open("templates/courses/course_form.html", encoding="utf-8") as f:
            src = f.read()
        head = src[:src.index("{% block content %}")]
        self.assertNotIn("<script", head)  # title / extra_head stay clean
        self.assertEqual(src.count("<script"), 1)
