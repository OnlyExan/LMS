from decimal import Decimal

from django.test import SimpleTestCase
from django.urls import reverse

from accounts.models import User
from assignments.forms import AssignmentForm
from assignments.models import Assignment, Grade, Submission
from courses.grading import course_percent
from courses.models import AssignmentGroup, Enrollment
from tests.helpers import LMSTestCase

D = Decimal


class CoursePercentTests(SimpleTestCase):
    def test_points_mode(self):
        self.assertAlmostEqual(course_percent([(None, D(45), D(50)), (1, D(50), D(100))]), D(95) / D(150) * 100)
        self.assertIsNone(course_percent([]))

    def test_weighted(self):
        # HW 90% (w 40) + Exam 60% (w 60) = 36 + 36 = 72
        graded = [(1, D(9), D(10)), (2, D(60), D(100))]
        self.assertEqual(course_percent(graded, {1: D(40), 2: D(60)}), 72)

    def test_empty_groups_rescaled(self):
        # only HW graded -> HW counts as 100% of the grade so far
        self.assertEqual(course_percent([(1, D(9), D(10))], {1: D(40), 2: D(60)}), 90)

    def test_ungrouped_and_zero_weight_ignored(self):
        graded = [(1, D(8), D(10)), (None, D(0), D(100)), (3, D(0), D(10))]
        self.assertEqual(course_percent(graded, {1: D(50), 3: D(0)}), 80)
        self.assertIsNone(course_percent([(None, D(5), D(10))], {1: D(100)}))


class WeightedSetup(LMSTestCase):
    def setUp(self):
        a = self.data["a"]
        self.course, self.inst, self.stu = a["course"], a["inst"], a["stu"]
        Enrollment.objects.update_or_create(student=self.stu, course=self.course,
                                            defaults={"status": Enrollment.ACTIVE})
        self.hw = a["asg"]
        self.hw.points_possible = D(10)
        self.hw.save()
        self.exam = Assignment.objects.create(course=self.course, title="Exam", points_possible=100,
                                              due_date=self.hw.due_date)
        for asg, pts in ((self.hw, 9), (self.exam, 60)):
            sub = Submission.objects.create(assignment=asg, student=self.stu, response_text="x")
            Grade.objects.create(submission=sub, points_earned=D(pts), graded_by=self.inst)

    def post_settings(self, weighted, groups, picks):
        c = self.course
        data = {"code": c.code, "title": c.title, "term": c.term, "description": "",
                "groups_form": "1", "group_key": [], "group_name": [], "group_weight": []}
        if weighted:
            data["weighted_grading"] = "on"
        for key, name, w in groups:
            data["group_key"].append(key); data["group_name"].append(name); data["group_weight"].append(w)
        for asg, key in picks:
            data[f"asg_group_{asg.pk}"] = key
        self.login(self.inst)
        return self.client.post(reverse("courses:course_edit", args=[c.pk]), data)


class WeightedSettingsTests(WeightedSetup):
    def test_create_groups_and_assign(self):
        r = self.post_settings(True, [("new-1", "Homework", "40"), ("new-2", "Exams", "60")],
                               [(self.hw, "new-1"), (self.exam, "new-2")])
        self.assertEqual(r.status_code, 302)
        self.course.refresh_from_db()
        self.assertTrue(self.course.weighted_grading)
        groups = list(self.course.assignment_groups.values_list("name", "weight"))
        self.assertEqual(groups, [("Homework", 40), ("Exams", 60)])
        self.hw.refresh_from_db(); self.exam.refresh_from_db()
        self.assertEqual((self.hw.group.name, self.exam.group.name), ("Homework", "Exams"))

    def test_rename_and_remove_group(self):
        self.post_settings(True, [("new-1", "Homework", "40"), ("new-2", "Exams", "60")],
                           [(self.hw, "new-1"), (self.exam, "new-2")])
        hw_g, ex_g = self.course.assignment_groups.all()
        self.post_settings(True, [(str(hw_g.pk), "Labs", "100")], [(self.hw, str(hw_g.pk)), (self.exam, str(ex_g.pk))])
        self.assertEqual(list(self.course.assignment_groups.values_list("pk", "name")), [(hw_g.pk, "Labs")])
        self.exam.refresh_from_db()
        self.assertIsNone(self.exam.group)  # its group was removed

    def test_weights_must_total_100(self):
        r = self.post_settings(True, [("new-1", "Homework", "40"), ("new-2", "Exams", "50")], [])
        self.assertEqual(r.status_code, 200)
        self.assertIn("add up to 100", str(r.context["form"].non_field_errors()))
        self.assertFalse(self.course.assignment_groups.exists())

    def test_bad_rows_rejected(self):
        for groups in ([("new-1", "", "100")], [("new-1", "HW", "x")], [("new-1", "HW", "50"), ("new-2", "hw", "50")],
                       [("new-1", "HW", "150")]):
            r = self.post_settings(True, groups, [])
            self.assertEqual(r.status_code, 200, groups)

    def test_off_with_groups_is_fine(self):
        r = self.post_settings(False, [("new-1", "Homework", "30")], [(self.hw, "new-1")])
        self.assertEqual(r.status_code, 302)
        self.course.refresh_from_db()
        self.assertFalse(self.course.weighted_grading)

    def test_other_courses_group_keys_ignored(self):
        other = AssignmentGroup.objects.create(course=self.data["b"]["course"], name="X", weight=100)
        self.post_settings(True, [(str(other.pk), "Stolen", "100")], [(self.hw, str(other.pk))])
        other.refresh_from_db()
        self.assertEqual(other.name, "X")  # untouched
        self.hw.refresh_from_db()
        self.assertIsNone(self.hw.group)

    def test_form_without_groups_section_keeps_groups(self):
        self.post_settings(True, [("new-1", "All", "100")], [(self.hw, "new-1"), (self.exam, "new-1")])
        c = self.course
        self.client.post(reverse("courses:course_edit", args=[c.pk]),
                         {"code": c.code, "title": "Renamed", "term": c.term, "description": ""})
        c.refresh_from_db()
        self.assertTrue(c.weighted_grading)
        self.assertEqual(c.assignment_groups.count(), 1)

    def test_assignment_form_group_only_when_posted(self):
        g = AssignmentGroup.objects.create(course=self.course, name="HW", weight=100)
        self.hw.group = g
        self.hw.save()
        form = AssignmentForm({"title": "HW", "description": "", "due_date": "2030-01-01T10:00",
                               "points_possible": "10", "text_only": "on"}, instance=self.hw)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().group_id, g.pk)  # page without a picker doesn't clear it
        other = AssignmentGroup.objects.create(course=self.data["b"]["course"], name="X", weight=1)
        form = AssignmentForm({"title": "HW", "description": "", "due_date": "2030-01-01T10:00",
                               "points_possible": "10", "text_only": "on", "group": other.pk}, instance=self.hw)
        self.assertFalse(form.is_valid())  # another course's group isn't a choice


class WeightedPagesTests(WeightedSetup):
    def setUp(self):
        super().setUp()
        self.post_settings(True, [("new-1", "Homework", "40"), ("new-2", "Exams", "60")],
                           [(self.hw, "new-1"), (self.exam, "new-2")])

    def test_student_pages_use_weights(self):
        self.login(self.stu)
        r = self.client.get(reverse("assignments:my_grades"))
        self.assertEqual(r.context["courses"][0]["percent"], 72)  # points would be 69/110 = 62.7
        r = self.client.get(reverse("assignments:course_grades", args=[self.course.pk]))
        self.assertEqual(r.context["score"]["percent"], 72)
        self.assertEqual([(b["group"].name, b["percent"]) for b in r.context["breakdown"]],
                         [("Homework", 90), ("Exams", 60)])

    def test_gradebook_uses_weights(self):
        self.login(self.inst)
        r = self.client.get(reverse("assignments:gradebook", args=[self.course.pk]))
        row = [x for x in r.context["rows"] if x["student"] == self.stu][0]
        self.assertEqual(row["percent"], 72)
        self.assertEqual(row["letter"], "C")
        self.assertEqual(r.context["grade_js"]["weights"], {str(g.pk): float(g.weight)
                                                            for g in self.course.assignment_groups.all()})
        self.assertEqual(r.context["ungrouped"], [])

    def test_ungrouped_warning(self):
        Assignment.objects.create(course=self.course, title="Bonus", points_possible=5, due_date=self.hw.due_date)
        self.login(self.inst)
        r = self.client.get(reverse("assignments:gradebook", args=[self.course.pk]))
        self.assertEqual([a.title for a in r.context["ungrouped"]], ["Bonus"])

    def test_turning_off_goes_back_to_points(self):
        self.course.weighted_grading = False
        self.course.save()
        self.login(self.stu)
        r = self.client.get(reverse("assignments:my_grades"))
        self.assertAlmostEqual(float(r.context["courses"][0]["percent"]), 69 / 110 * 100, places=5)
