from django.test import TestCase
from django.urls import reverse
from accounts.models import School, User
from accounts.views import USERS_PER_PAGE


class ManageUsersPaging(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Big U")
        self.adm = User.objects.create_user("aaa-admin", password="x", school=self.s, role="admin")
        User.objects.bulk_create([User(username=f"stu{i:03}", school=self.s, role="student") for i in range(60)])
        self.client.force_login(self.adm)
        self.url = reverse("accounts:manage_users")

    def test_first_page_limited(self):
        r = self.client.get(self.url)
        self.assertEqual(len(r.context["users"]), USERS_PER_PAGE)
        self.assertContains(r, "61 users")
        self.assertContains(r, "Page 1 of 3")

    def test_last_page_and_bad_page(self):
        self.assertEqual(len(self.client.get(self.url + "?page=3").context["users"]), 11)
        self.assertEqual(self.client.get(self.url + "?page=999").context["page"].number, 3)
        self.assertEqual(self.client.get(self.url + "?page=abc").context["page"].number, 1)

    def test_pager_keeps_filters(self):
        r = self.client.get(self.url + "?role=student&q=stu")
        self.assertContains(r, "60 users")
        self.assertContains(r, "?page=2&amp;role=student&amp;q=stu")

    def test_no_pager_when_one_page(self):
        r = self.client.get(self.url + "?role=admin")
        self.assertNotContains(r, 'class="pager"')
