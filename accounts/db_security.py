"""Turn on Row Level Security for every table in Supabase's public schema.

Supabase exposes `public` over its REST API; tables without RLS are readable
with the anon key. Django connects as the table owner, which bypasses RLS,
so enabling it (with no policies) closes the API and leaves the app working.
"""
from django.db import connections

ENABLE_RLS_SQL = """
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.relname FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.relname);
  END LOOP;
END $$;
"""


def enable_rls(using="default", **kwargs):
    conn = connections[using]
    if conn.vendor != "postgresql":  # SQLite (dev/tests) has no RLS
        return
    with conn.cursor() as cur:
        cur.execute(ENABLE_RLS_SQL)
