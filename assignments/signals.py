"""Remove uploaded files from storage when their rows are deleted."""
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Submission, SubmissionVersion


def _delete_file(field):
    if field:
        storage, name = field.storage, field.name
        # after commit, so a rolled-back delete doesn't lose the file
        transaction.on_commit(lambda: storage.delete(name))  # missing file = no-op


# fire for cascades too (assignment/course/school/user deletes).
# resubmits keep old files — versions still reference them.
@receiver(post_delete, sender=Submission)
def delete_submission_file(sender, instance, **kwargs):
    _delete_file(instance.file_upload)


@receiver(post_delete, sender=SubmissionVersion)
def delete_version_file(sender, instance, **kwargs):
    _delete_file(instance.file_upload)
