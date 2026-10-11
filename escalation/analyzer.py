import re
from dataclasses import dataclass, field, asdict
from . import config as C
from .nlp import normalize, stems, stem_word, NLTK_AVAILABLE

@dataclass
class RiskResult:
    score: float
    level: str
    escalate: bool
    reasons: list = field(default_factory=list)
    categories: dict = field(default_factory=dict)
    primary_category: str = "general"

    def to_dict(self):
        return asdict(self)

class ComplaintAnalyzer:
    def __init__(self, categories=None):
        self.categories = categories or C.CATEGORIES
        self._compiled = {
            name: [re.compile(p) for p in spec["patterns"]] for name, spec in self.categories.items()
        }
        self._kw = {name: {stem_word(k) for k in spec["keywords"]} for name, spec in self.categories.items()}


    def detect(self, text: str) -> dict:
        """Return {category: [matched snippets]} (one snippet per matching pattern)."""
        low = normalize(text).lower()
        tokens = stems(low)
        found = {}
        for name, regs in self._compiled.items():
            hits = []
            for rx in regs:
                m = rx.search(low)
                if m:
                    hits.append(m.group(0))
            hits += [f"<{k}>" for k in self._kw[name] if k in tokens]
            if hits:
                found[name] = hits
        return found

    def analyze(self, text: str, prior_contacts: int = 0, tier: str = "standard") -> RiskResult:
        if text is None:
            text = ""
        clean = normalize(text)
        low = clean.lower()
        found = self.detect(clean)
        reasons, score = [], 0.0

        # strongest category gets full weight; others are discounted
        ranked = sorted(found, key=lambda n: self.categories[n]["weight"], reverse=True)
        for i, name in enumerate(ranked):
            w = self.categories[name]["weight"]
            hits = found[name]
            pts = w * (1 if i == 0 else C.SECONDARY_CATEGORY_FACTOR)
            pts += w * C.EXTRA_HIT_FACTOR * min(len(hits) - 1, 2)
            score += pts
            reasons.append(f"{name}: +{pts:.1f} (matched: {', '.join(hits[:3])})")

        def has_any(pats):
            return any(re.search(p, low) for p in pats)

        if has_any(C.URGENCY_PATTERNS):
            score += C.URGENCY_POINTS
            reasons.append(f"urgency language: +{C.URGENCY_POINTS}")

        if has_any(C.REPEAT_TEXT_PATTERNS):
            score += C.REPEAT_TEXT_POINTS
            reasons.append(f"repeat-contact language: +{C.REPEAT_TEXT_POINTS}")

        letters = [c for c in clean if c.isalpha()]
        if len(letters) >= 15 and sum(c.isupper() for c in letters) / len(letters) >= C.CAPS_RATIO_THRESHOLD:
            score += C.CAPS_POINTS
            reasons.append(f"shouting (ALL CAPS): +{C.CAPS_POINTS}")
        if clean.count("!") >= C.EXCLAMATION_THRESHOLD:
            score += C.EXCLAMATION_POINTS
            reasons.append(f"excessive '!': +{C.EXCLAMATION_POINTS}")
        if prior_contacts >= C.PRIOR_CONTACTS_THRESHOLD:
            score += C.PRIOR_CONTACTS_POINTS
            reasons.append(f"{prior_contacts} prior contacts (CRM): +{C.PRIOR_CONTACTS_POINTS}")
        tier_pts = C.TIER_POINTS.get((tier or "standard").lower(), 0)
        if tier_pts:
            score += tier_pts
            reasons.append(f"{tier} customer: +{tier_pts}")

        if has_any(C.DEESCALATION_PATTERNS) and not any(self.categories[n]["auto_escalate"] for n in found):
            score += C.DEESCALATION_POINTS
            reasons.append(f"de-escalation language: {C.DEESCALATION_POINTS}")

        score = max(0.0, round(score, 1))
        level = next(lbl for lbl, thr in C.LEVELS if score >= thr)
        auto = [n for n in found if self.categories[n]["auto_escalate"]]
        escalate = bool(auto) or score >= C.ESCALATION_THRESHOLD
        if auto:
            reasons.append(f"AUTO-ESCALATE: {', '.join(auto)}")
            if level in ("LOW", "MEDIUM"):
                level = "HIGH"
        return RiskResult(score, level, escalate, reasons, found, ranked[0] if ranked else "general")


    __all__ = ["ComplaintAnalyzer", "RiskResult", "NLTK_AVAILABLE"]