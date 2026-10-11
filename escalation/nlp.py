import re

try:
    from nltk.stem import PorterStemmer
    from nltk.tokenize import RegexpTokenizer
    _stem = PorterStemmer().stem
    _tok = RegexpTokenizer(r"[A-Za-z']+").tokenize     # needs no downloaded corpora
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    _tok = re.compile(r"[A-Za-z']+").findall

    def _stem(w):
        for suf in ("ing", "ed", "es", "s", "ly"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                return w[: -len(suf)]
        return w
def normalize(text: str) -> str:
    text = (text or "").replace("\u2019", "'")
    return re.sub(r"\s+", " ", text).strip()


def stems(text: str) -> set:
    return {_stem(t.lower()) for t in _tok(text)}


def stem_word(w: str) -> str:
    return _stem(w.lower())