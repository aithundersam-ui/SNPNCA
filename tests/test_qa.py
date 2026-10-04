"""The Q&A assistant may only answer from the uploaded PDFs."""

import shutil
import unittest
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from accounts.models import Role
from qa import assistant, processing, search
from qa.llm import LLMError
from qa.models import Chunk, Document, QAMessage

from .helpers import make_pdf, make_user, media_settings

FRENCH_PAGE = (
    "Article 12 - Congé annuel. Le personnel navigant commercial bénéficie d'un congé annuel "
    "de trente jours calendaires. La demande de congé est déposée deux mois à l'avance."
)
FRENCH_PAGE_2 = "Article 20 - Repos. Après un vol long-courrier, le repos minimal est de quarante-huit heures."


class FakeLLM:
    """Stands in for Claude. Records calls so tests can assert what was (not) asked."""

    def __init__(self, plan=None, answer=None, fail=False):
        self.plan_result = plan or {"language": "en", "keywords_fr": ["congé", "annuel"], "keywords_en": ["annual", "leave"], "keywords_ar": []}
        self.answer_result = answer
        self.fail = fail
        self.answer_calls = []

    def plan(self, question):
        if self.fail:
            raise LLMError("down")
        return self.plan_result

    def answer(self, question, passages, language):
        self.answer_calls.append((question, passages, language))
        return self.answer_result


@media_settings()
class QATestCase(TestCase):
    def add_document(self, title, pages, scanned=()):
        doc = Document(title=title, original_filename=f"{title}.pdf")
        doc.file.save("x.pdf", ContentFile(make_pdf(pages, scanned).getvalue()), save=False)
        doc.save()
        processing.process_document(doc)
        doc.refresh_from_db()
        return doc


class ProcessingTests(QATestCase):
    def test_text_layer_is_extracted_chunked_and_indexed(self):
        doc = self.add_document("Convention", [FRENCH_PAGE, FRENCH_PAGE_2])
        self.assertEqual(doc.status, Document.Status.READY)
        self.assertEqual(doc.page_count, 2)
        self.assertEqual(doc.ocr_page_count, 0)
        self.assertEqual(sorted(set(doc.chunks.values_list("page", flat=True))), [1, 2])
        self.assertFalse(Chunk.objects.filter(vec_fr__isnull=True).exists())

    @unittest.skipUnless(shutil.which("tesseract"), "tesseract is not installed")
    def test_scanned_pages_are_read_with_ocr(self):
        doc = self.add_document("Scan", ["Le repos minimal est de quarante-huit heures après un vol."], scanned=(0,))
        self.assertEqual(doc.ocr_page_count, 1)
        self.assertIn("repos", doc.chunks.first().text.lower())

    def test_cross_language_retrieval_finds_french_passage_from_english_keywords(self):
        self.add_document("Convention", [FRENCH_PAGE, FRENCH_PAGE_2])
        # An English question about leave, expanded to French keywords (accents omitted on purpose).
        results = search.retrieve(["conge", "annuel"], ["annual", "leave"], [])
        self.assertTrue(results)
        self.assertEqual(results[0].page, 1)

    def test_deleting_a_document_removes_its_text_index_and_file(self):
        doc = self.add_document("Convention", [FRENCH_PAGE])
        storage, name = doc.file.storage, doc.file.name
        self.assertTrue(storage.exists(name))
        doc.delete()
        self.assertEqual(Chunk.objects.count(), 0)
        self.assertFalse(storage.exists(name))
        self.assertEqual(search.retrieve(["conge"], ["leave"], []), [])

    def test_non_pdf_upload_is_rejected_on_the_server(self):
        admin = make_user("admin@example.com", Role.ADMIN)
        self.client.force_login(admin)
        fake = ContentFile(b"<html>not a pdf</html>", name="evil.pdf")
        response = self.client.post(reverse("panel:documents"), {"title": "x", "file": fake})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Document.objects.count(), 0)


    def test_admin_upload_queues_pdf_for_processing(self):
        self.client.force_login(make_user("admin@example.com", Role.ADMIN))
        pdf = ContentFile(make_pdf([FRENCH_PAGE]).getvalue(), name="Statuts SNPNCA.pdf")
        self.client.post(reverse("panel:documents"), {"title": "", "file": pdf})
        doc = Document.objects.get()
        self.assertEqual(doc.title, "Statuts SNPNCA")
        self.assertEqual(doc.status, Document.Status.PENDING)
        self.assertGreater(doc.size_bytes, 0)
        self.assertTrue(processing.run_once())
        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.READY)


class AnswerOnlyFromPdfTests(QATestCase):
    def setUp(self):
        self.doc = self.add_document("Convention collective", [FRENCH_PAGE, FRENCH_PAGE_2])

    def test_no_matching_passage_means_no_model_answer(self):
        llm = FakeLLM(plan={"language": "en", "keywords_fr": ["salaire", "pilote"], "keywords_en": ["pilot", "salary"], "keywords_ar": []},
                      answer={"answerable": True, "answer": "Pilots earn a lot.", "sources": [1]})
        result = assistant.ask("What is a pilot's salary?", "fr", llm=llm)
        self.assertFalse(result.answered)
        self.assertEqual(llm.answer_calls, [])  # the model was never asked to answer
        with translation.override("en"):
            self.assertEqual(result.text, assistant.not_found("en"))
        self.assertEqual(result.citations, [])

    def test_model_saying_unanswerable_gives_the_not_found_reply(self):
        llm = FakeLLM(answer={"answerable": False, "answer": "", "sources": []})
        result = assistant.ask("How many days of annual leave do I get?", "fr", llm=llm)
        self.assertFalse(result.answered)
        self.assertEqual(result.text, assistant.not_found("en"))

    def test_answer_without_valid_citation_is_discarded(self):
        for sources in ([], [99], [0]):
            llm = FakeLLM(answer={"answerable": True, "answer": "You get 45 days.", "sources": sources})
            result = assistant.ask("How many days of annual leave do I get?", "fr", llm=llm)
            self.assertFalse(result.answered, sources)
            self.assertNotIn("45", result.text)

    def test_grounded_answer_is_returned_with_document_and_page(self):
        llm = FakeLLM(answer={"answerable": True, "answer": "You are entitled to 30 calendar days of annual leave.", "sources": [1]})
        result = assistant.ask("How many days of annual leave do I get?", "fr", llm=llm)
        self.assertTrue(result.answered)
        self.assertEqual(result.language, "en")  # reply language follows the question, not the UI
        self.assertEqual(result.citations, [{"document_id": self.doc.pk, "title": "Convention collective", "page": 1}])
        _q, passages, language = llm.answer_calls[0]
        self.assertEqual(language, "en")
        self.assertTrue(all(p.document_id == self.doc.pk for p in passages))

    def test_assistant_outage_is_reported_not_guessed(self):
        result = assistant.ask("Combien de jours de congé ?", "fr", llm=FakeLLM(fail=True))
        self.assertFalse(result.answered)
        self.assertEqual(result.text, assistant.unavailable("fr"))

    def test_documents_still_processing_are_not_searched(self):
        Document.objects.filter(pk=self.doc.pk).update(status=Document.Status.PROCESSING)
        llm = FakeLLM(answer={"answerable": True, "answer": "30 days", "sources": [1]})
        self.assertFalse(assistant.ask("annual leave?", "fr", llm=llm).answered)

    def test_chat_view_stores_answer_with_citations(self):
        member = make_user("member@example.com")
        self.client.force_login(member)
        llm = FakeLLM(answer={"answerable": True, "answer": "30 jours calendaires.", "sources": [1]})
        with mock.patch.object(assistant, "get_llm", return_value=llm):
            response = self.client.post(reverse("qa:chat"), {"question": "Combien de jours de congé annuel ?"})
        self.assertEqual(response.status_code, 302)
        answer = QAMessage.objects.get(user=member, role="assistant")
        self.assertTrue(answer.answered)
        self.assertEqual(answer.citations[0]["page"], 1)
        page = self.client.get(reverse("qa:chat"))
        self.assertContains(page, "Convention collective")

    def test_members_can_open_ready_documents_but_not_anonymous_visitors(self):
        url = reverse("qa:document", args=[self.doc.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(make_user("member@example.com"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
