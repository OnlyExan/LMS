from unittest import mock

from django.test import SimpleTestCase

from accounts import db_security


class EnableRlsHookTests(SimpleTestCase):
    """Supabase RLS hook: runs on Postgres only, never on SQLite."""

    def test_skips_non_postgres(self):
        conn = mock.MagicMock(vendor="sqlite")
        with mock.patch.object(db_security, "connections", {"default": conn}):
            db_security.enable_rls()
        conn.cursor.assert_not_called()

    def test_runs_on_postgres(self):
        conn = mock.MagicMock(vendor="postgresql")
        with mock.patch.object(db_security, "connections", {"default": conn}):
            db_security.enable_rls()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.execute.assert_called_once_with(db_security.ENABLE_RLS_SQL)
        self.assertIn("ENABLE ROW LEVEL SECURITY", db_security.ENABLE_RLS_SQL)
