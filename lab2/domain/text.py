"""Unicode-предобработка: диакритика и короткие служебные слова сохраняются."""

import re
import unicodedata
from collections import Counter

WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
ALPHABET = "abcdefghijklmnopqrstuvwxyzáéíóúüñ"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-[ \t]*\n[ \t]*(?=\w)", "", text)
    return " ".join(text.split())


def words(text: str) -> list[str]:
    return WORD_RE.findall(unicodedata.normalize("NFC", text).casefold().replace("’", "'"))


def letter_counts(text: str) -> Counter[str]:
    return Counter(c for c in unicodedata.normalize("NFC", text).casefold() if c in ALPHABET)


def input_problem(text: str) -> str | None:
    letters = [c for c in unicodedata.normalize("NFC", text).casefold() if c.isalpha()]
    if len(letters) < 10:
        return "Слишком мало букв: требуется не менее 10."
    if sum(c not in ALPHABET for c in letters) / len(letters) > 0.2:
        return "Более 20% букв вне поддерживаемых алфавитов EN/ES."
    return None
