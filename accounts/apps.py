from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from .db_security import enable_rls
        # after every migrate, so new tables (e.g. from new apps) get RLS too
        post_migrate.connect(enable_rls, dispatch_uid="accounts.enable_rls")
