from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from documents.models import Document, DocumentVersion, ProcessingJob


class DocumentModelConstraintTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.document = Document.objects.create(owner=self.owner, title="Runbook")

    def test_version_sequence_is_unique_per_document(self):
        DocumentVersion.objects.create(document=self.document, sequence=1, created_by_user_id=self.owner.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DocumentVersion.objects.create(document=self.document, sequence=1, created_by_user_id=self.owner.pk)

    def test_deleted_timestamp_must_match_visibility(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Document.objects.create(owner=self.owner, title="Invalid", visibility=Document.Visibility.DELETED)

    def test_only_one_nonterminal_job_per_version(self):
        version = DocumentVersion.objects.create(document=self.document, sequence=1, created_by_user_id=self.owner.pk)
        ProcessingJob.objects.create(document_version=version, available_at=timezone.now())
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProcessingJob.objects.create(document_version=version, available_at=timezone.now())

    def test_terminal_job_requires_null_nonterminal_slot(self):
        version = DocumentVersion.objects.create(document=self.document, sequence=1, created_by_user_id=self.owner.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProcessingJob.objects.create(
                document_version=version,
                state=ProcessingJob.State.SUCCEEDED,
                nonterminal_slot=True,
                available_at=timezone.now(),
            )

    def test_current_and_candidate_versions_must_belong_to_document(self):
        other = Document.objects.create(owner=self.owner, title="Other")
        own_version = DocumentVersion.objects.create(
            document=self.document,
            sequence=1,
            created_by_user_id=self.owner.pk,
        )
        foreign_version = DocumentVersion.objects.create(
            document=other,
            sequence=1,
            created_by_user_id=self.owner.pk,
        )

        self.document.current_version = own_version
        self.document.candidate_version = own_version
        self.document.save(update_fields=("current_version", "candidate_version"))

        for field_name in ("current_version", "candidate_version"):
            with self.subTest(field_name=field_name):
                setattr(self.document, field_name, foreign_version)
                with self.assertRaises(ValidationError) as raised:
                    self.document.save(update_fields=(field_name,))
                self.assertIn(field_name, raised.exception.message_dict)
                self.document.refresh_from_db()
