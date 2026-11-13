from django.test import TestCase
from django.urls import reverse
from accounts.models import School, User


class BulkUsers(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.adm = User.objects.create_user("adm", password="x", school=self.s, role="admin")
        self.a = User.objects.create_user("a", password="x", school=self.s, role="student")
        self.b = User.objects.create_user("b", password="x", school=self.s, role="student")
        self.out = User.objects.create_user("out", password="x", school=School.objects.create(name="X"), role="student")
        self.url = reverse("accounts:bulk_users")
        self.client.force_login(self.adm)

    def post(self, action, ids, **extra):
        return self.client.post(self.url, {"action": action, "ids": [u.pk for u in ids], **extra})

    def refresh(self):
        for u in (self.adm, self.a, self.b, self.out):
            u.refresh_from_db()

    def test_bulk_role_change(self):
        self.post("role_instructor", [self.a, self.b]); self.refresh()
        self.assertEqual((self.a.role, self.b.role), ("instructor", "instructor"))

    def test_bulk_deactivate_and_reactivate(self):
        self.post("deactivate", [self.a, self.b]); self.refresh()
        self.assertFalse(self.a.is_active or self.b.is_active)
        self.post("reactivate", [self.a]); self.refresh()
        self.assertTrue(self.a.is_active); self.assertFalse(self.b.is_active)

    def test_never_touches_self_or_other_school(self):
        self.post("deactivate", [self.adm, self.a, self.out]); self.refresh()
        self.assertTrue(self.adm.is_active)
        self.assertTrue(self.out.is_active)
        self.assertFalse(self.a.is_active)

    def test_rejects_bad_action_and_platform_role(self):
        self.post("role_platform", [self.a]); self.post("delete", [self.a]); self.refresh()
        self.assertEqual(self.a.role, "student"); self.assertTrue(self.a.is_active)

    def test_redirect_keeps_filters(self):
        r = self.post("role_admin", [self.a], next="/accounts/admin/users/?role=student&page=2")
        self.assertRedirects(r, "/accounts/admin/users/?role=student&page=2", fetch_redirect_response=False)

    def test_non_admin_forbidden(self):
        self.client.force_login(self.a)
        self.assertEqual(self.post("role_admin", [self.a]).status_code, 403)
        self.refresh(); self.assertEqual(self.a.role, "student")

    def test_page_has_checkboxes_but_not_for_self(self):
        r = self.client.get(reverse("accounts:manage_users"))
        self.assertContains(r, f'value="{self.a.pk}" form="bulkForm"')
        self.assertNotContains(r, f'value="{self.adm.pk}" form="bulkForm"')
        self.assertContains(r, 'id="selectAll"')
