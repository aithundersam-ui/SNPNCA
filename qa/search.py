"""Cross-language retrieval over extracted PDF text using PostgreSQL full-text search.

The question is first expanded into French, English and Arabic keywords (see
assistant.plan_query), so an English question can match a French passage. Each
keyword list is matched against the vector built for that language.
"""

import re
from dataclasses import dataclass

from django.conf import settings
from django.db import connection

WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class Passage:
    chunk_id: int
    document_id: int
    title: str
    page: int
    text: str
    score: float


def to_or_query(terms):
    """Turn free-text keywords into a safe `a | b | c` tsquery string."""
    words, seen = [], set()
    for term in terms:
        for word in WORD_RE.findall(term or ""):
            w = word.lower()
            if len(w) < 2 or w in seen:
                continue
            seen.add(w)
            words.append(w)
    return " | ".join(words[:40])


def retrieve(keywords_fr, keywords_en, keywords_other, limit=None):
    limit = limit or settings.QA_MAX_CHUNKS
    q_fr = to_or_query(keywords_fr)
    q_en = to_or_query(keywords_en)
    q_simple = to_or_query(list(keywords_fr) + list(keywords_en) + list(keywords_other))
    if not (q_fr or q_en or q_simple):
        return []
    sql = """
        WITH q AS (
          SELECT to_tsquery('snpnca_fr', %s) AS qfr,
                 to_tsquery('snpnca_en', %s) AS qen,
                 to_tsquery('snpnca_simple', %s) AS qs
        )
        SELECT c.id, d.id, d.title, c.page, c.text,
               ts_rank_cd(c.vec_fr, q.qfr) + ts_rank_cd(c.vec_en, q.qen) + 0.5 * ts_rank_cd(c.vec_simple, q.qs) AS score
        FROM qa_chunk c
        JOIN qa_document d ON d.id = c.document_id, q
        WHERE d.status = 'ready'
          AND (c.vec_fr @@ q.qfr OR c.vec_en @@ q.qen OR c.vec_simple @@ q.qs)
        ORDER BY score DESC, c.id
        LIMIT %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [q_fr, q_en, q_simple, limit])
        return [Passage(*row) for row in cursor.fetchall()]
