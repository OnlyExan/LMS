from django.template import Context, Template
from django.test import SimpleTestCase

from courses.grading import letter_tone
from tests.helpers import LMSTestCase


class LetterToneTests(SimpleTestCase):
    def test_tones(self):
        cases = {"A": "tone-a", "A+": "tone-a", "A-": "tone-a", "B+": "tone-b", "B-": "tone-b",
                 "C": "tone-c", "C+": "tone-c", "D": "tone-f", "D-": "tone-f", "F": "tone-f",
                 "Pass": "tone-x", "NP": "tone-x", "": "tone-x", None: "tone-x", " b ": "tone-b"}
        for letter, tone in cases.items():
            self.assertEqual(letter_tone(letter), tone, letter)

    def test_template_filter(self):
        out = Template("{% load grading_tags %}{{ l|letter_tone }}").render(Context({"l": "B+"}))
        self.assertEqual(out, "tone-b")

    def test_gradebook_js_matches_python(self):
        # the gradebook recolors live in JS; keep its map the same as letter_tone
        with open("templates/assignments/gradebook.html", encoding="utf-8") as f:
            src = f.read()
        self.assertIn('{A: "tone-a", B: "tone-b", C: "tone-c", D: "tone-f", F: "tone-f"}', src)
        self.assertIn('|| "tone-x"', src)


class LetterInFilterTests(LMSTestCase):
    def test_uses_course_scale(self):
        c = self.data["a"]["course"]
        t = Template("{% load grading_tags %}{{ p|letter_in:c }}")
        self.assertEqual(t.render(Context({"p": 85, "c": c})), "B")
        c.grading_scale = [["Pass", 60], ["Fail", 0]]
        self.assertEqual(t.render(Context({"p": 85, "c": c})), "Pass")
