"""NLP pipeline loader: spaCy (dep/pos/tokens) + standalone benepar (constituency)."""
import spacy

from backend.config import settings

_nlp = None
_benepar_parser = None
_benepar_available = False


def _patch_t5_tokenizer() -> None:
    """Monkey-patch T5Tokenizer for transformers >= 4.31 compatibility."""
    try:
        from transformers import T5Tokenizer
        if not hasattr(T5Tokenizer, "build_inputs_with_special_tokens"):
            def _build(self, token_ids_0, token_ids_1=None):
                return token_ids_0 if token_ids_1 is None else token_ids_0 + token_ids_1
            T5Tokenizer.build_inputs_with_special_tokens = _build
    except Exception:
        pass


def get_nlp():
    """Return spaCy pipeline (no benepar — avoids retokenization bugs)."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load(settings.spacy_model)
    return _nlp


def get_benepar_parser():
    """Return standalone benepar.Parser instance (or None if unavailable)."""
    global _benepar_parser, _benepar_available
    if _benepar_parser is not None or _benepar_available is False and _benepar_parser is None:
        # already tried
        return _benepar_parser

    _patch_t5_tokenizer()
    try:
        import benepar
        _benepar_parser = benepar.Parser(settings.benepar_model)
        _benepar_available = True
        print("benepar loaded successfully")
    except Exception as exc:
        print(f"Warning: benepar not available ({exc}). Constituency trees will be empty.")
        _benepar_available = False
        _benepar_parser = None

    return _benepar_parser


def preload() -> None:
    """Pre-load both models at startup."""
    get_nlp()
    get_benepar_parser()
