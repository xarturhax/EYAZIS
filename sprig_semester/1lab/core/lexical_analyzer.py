
import re
from collections import defaultdict

import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet


def _get_wordnet_pos(treebank_tag: str) -> str:
    if treebank_tag.startswith("J"):
        return wordnet.ADJ
    elif treebank_tag.startswith("V"):
        return wordnet.VERB
    elif treebank_tag.startswith("N"):
        return wordnet.NOUN
    elif treebank_tag.startswith("R"):
        return wordnet.ADV
    return wordnet.NOUN


def analyze(text: str) -> dict:
    """
    Tokenize, lemmatize and count frequencies for English text.

    Returns:
        dict: {lemma: {wordform: frequency}}
    """
    lemmatizer = WordNetLemmatizer()

    tokens = nltk.word_tokenize(text)
    # Keep only alphabetic tokens
    tokens = [t for t in tokens if re.match(r"^[A-Za-z]+$", t)]
    tokens_lower = [t.lower() for t in tokens]

    # POS tagging for better lemmatization
    pos_tags = nltk.pos_tag(tokens_lower)

    # Count wordform frequencies
    freq: dict[str, int] = defaultdict(int)
    for word, _ in pos_tags:
        freq[word] += 1

    # Build lemma -> wordforms structure
    result: dict[str, dict[str, int]] = defaultdict(dict)
    seen_wordforms: set[str] = set()

    for word, tag in pos_tags:
        if word in seen_wordforms:
            continue
        seen_wordforms.add(word)

        wn_pos = _get_wordnet_pos(tag)
        lemma = lemmatizer.lemmatize(word, pos=wn_pos)

        if word not in result[lemma]:
            result[lemma][word] = freq[word]

    return dict(result)
