"""Syntax Role Quiz service."""
from __future__ import annotations

import random

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.sentence import Sentence
from backend.models.syntax import SyntaxResult

QUIZ_ROLES = ["subjects", "predicates", "objects"]
ALL_ROLES = ["subjects", "predicates", "objects", "modifiers"]


async def get_syntax_quiz(db: AsyncSession, doc_id: int | None = None) -> dict:
    """Return a random syntax role quiz question."""
    for _ in range(5):
        q = (
            select(SyntaxResult, Sentence)
            .join(Sentence, Sentence.id == SyntaxResult.sent_id)
            .where(SyntaxResult.roles.isnot(None))
            .order_by(func.random())
            .limit(1)
        )
        if doc_id is not None:
            q = q.where(Sentence.doc_id == doc_id)

        row = (await db.execute(q)).first()
        if row is None:
            return {"error": "no_data"}

        result, sentence = row

        roles = result.roles or {}
        non_empty = [r for r in QUIZ_ROLES if roles.get(r)]
        if not non_empty:
            continue

        question_role = random.choice(non_empty)
        question_type = random.choice(["click_word", "multiple_choice"])

        role_items = roles[question_role]
        correct_words = [item["text"] for item in role_items]

        # Build token list from dep_tree
        dep_tree = result.dep_tree or {}
        tokens = [{"i": t["i"], "text": t["text"]} for t in dep_tree.get("tokens", [])]
        if not tokens:
            # fallback: split sentence text
            tokens = [{"i": i, "text": w} for i, w in enumerate(sentence.text.split())]

        # Multiple-choice: pick one word, ask its role; wrong options = other roles
        target_word = None
        correct_answer = None
        options = None

        if question_type == "multiple_choice":
            target_item = random.choice(role_items)
            target_word = target_item["text"]
            correct_answer = question_role
            wrong_roles = [r for r in ALL_ROLES if r != question_role]
            random.shuffle(wrong_roles)
            opts = [question_role] + wrong_roles
            random.shuffle(opts)
            options = opts

        return {
            "sentence_id": result.sent_id,
            "sentence_text": sentence.text,
            "tokens": tokens,
            "question_type": question_type,
            "question_role": question_role,
            "correct_words": correct_words,
            "target_word": target_word,
            "correct_answer": correct_answer,
            "options": options,
        }

    return {"error": "no_data"}
