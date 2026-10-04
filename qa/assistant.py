"""The Q&A pipeline. The "answers only from the PDFs" rule is enforced here, on
the server, not just requested in the prompt:

1. No retrieved passages -> fixed "not in the documents" reply; the model is never asked.
2. The model must cite excerpt numbers; an answer with no valid citation is discarded.
3. Citations shown to the member are built from our own database rows
   (document title + page), never from model-written text.
"""

import logging
from dataclasses import dataclass, field

from django.utils import translation
from django.utils.translation import gettext as _

from . import search
from .llm import ClaudeClient, LLMError

logger = logging.getLogger(__name__)


@dataclass
class Answer:
    text: str
    answered: bool
    language: str
    citations: list = field(default_factory=list)


def get_llm():
    return ClaudeClient()


def _ui_language(language, fallback):
    return language if language in ("fr", "en") else fallback


def not_found(language):
    with translation.override(language):
        return _("I could not find the answer to this question in the documents available. Please contact the union office for help.")


def unavailable(language):
    with translation.override(language):
        return _("The assistant is temporarily unavailable. Please try again in a few minutes.")


def ask(question, ui_language="fr", llm=None):
    question = question.strip()
    try:
        llm = llm or get_llm()
        plan = llm.plan(question)
    except LLMError:
        logger.warning("Q&A planning failed", exc_info=True)
        return Answer(unavailable(ui_language), False, ui_language)

    language = (plan.get("language") or ui_language).lower()[:2]
    reply_lang = _ui_language(language, ui_language)

    passages = search.retrieve(
        plan.get("keywords_fr", []) + [question],
        plan.get("keywords_en", []) + [question],
        plan.get("keywords_ar", []),
    )
    if not passages:
        return Answer(not_found(reply_lang), False, reply_lang)

    try:
        result = llm.answer(question, passages, language)
    except LLMError:
        logger.warning("Q&A answer failed", exc_info=True)
        return Answer(unavailable(reply_lang), False, reply_lang)

    text = (result.get("answer") or "").strip()
    cited = []
    for number in result.get("sources") or []:
        if isinstance(number, int) and 1 <= number <= len(passages):
            cited.append(passages[number - 1])

    if not result.get("answerable") or not text or not cited:
        return Answer(not_found(reply_lang), False, reply_lang)

    citations, seen = [], set()
    for p in cited:
        key = (p.document_id, p.page)
        if key not in seen:
            seen.add(key)
            citations.append({"document_id": p.document_id, "title": p.title, "page": p.page})
    citations.sort(key=lambda c: (c["title"], c["page"]))
    return Answer(text, True, reply_lang, citations)
