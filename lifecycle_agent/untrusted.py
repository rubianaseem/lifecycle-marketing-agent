"""Boundary for untrusted free text (contact notes, form messages, event detail).

Two deterministic checks run before any free text is used anywhere:
  1. opt_out_intent: a person asking to stop emails is a consent signal, so it SUPPRESSES.
  2. injection_markers: text that reads like instructions to a model or system is QUARANTINED.
     Quarantined text never reaches the model prompt, a draft or an import file.
Text that passes is still wrapped as data (see wrap_untrusted) and the model's output is
validated afterwards (see drafts.validate_generated). Pattern lists are a first layer, not a
guarantee; the hard controls do not read free text at all.
"""
from __future__ import annotations

import re

OPT_OUT_PATTERNS = [
    r"\bunsubscribe\b", r"\bstop (e-?mailing|sending|contacting)\b", r"\bremove me\b",
    r"\btake me off\b", r"\bno more (e-?mails|marketing)\b", r"\bdo not (e-?mail|contact)\b",
    r"\bdon'?t (e-?mail|contact) me\b", r"\bopt(ed)? me out\b", r"\bgdpr erasure\b",
]
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (the |all |any )?(previous|prior|above|system|rules|instructions)",
    r"\bsystem prompt\b", r"\byou are now\b", r"\bact as\b", r"\bnew instructions?\b",
    r"\b(set|change|update|mark) (this |the )?(contact|lifecycle|stage|record)\b.*\b(to|as)\b",
    r"\bremove (me |this contact |them )?from (the )?suppression\b",
    r"\b(approve|auto-?approve|bypass|override)\b.*\b(approval|review|consent|suppression|gate)\b",
    r"<\s*/?\s*(system|assistant|instructions?|untrusted[^>]*)\s*>",
    r"\bassistant\s*:", r"\bBEGIN (ADMIN|SYSTEM)\b",
    r"\bsend (this|an?) (e-?mail|message) to\b", r"\bexfiltrat", r"\bapi[_ ]?key\b",
]
_OPT = [re.compile(p, re.I) for p in OPT_OUT_PATTERNS]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]
EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL_IN_TEXT = re.compile(r"https?://\S+|www\.\S+", re.I)


def opt_out_intent(text: str) -> list[str]:
    return [p.pattern for p in _OPT if p.search(text or "")]


def injection_markers(text: str) -> list[str]:
    return [p.pattern for p in _INJ if p.search(text or "")]


def redact(text: str) -> str:
    text = EMAIL_IN_TEXT.sub("[email]", text or "")
    return URL_IN_TEXT.sub("[link]", text)


def screen(text: str, limit: int = 400) -> dict:
    """Classify one piece of free text. Returns status: empty | clean | opt_out | quarantined."""
    t = (text or "").strip()
    if not t:
        return {"status": "empty", "markers": [], "safe_text": ""}
    inj = injection_markers(t)
    opt = opt_out_intent(t)
    if inj:
        # Quarantine wins even if the text also asks to unsubscribe: a human checks it.
        return {"status": "quarantined", "markers": inj, "opt_out": bool(opt), "safe_text": ""}
    if opt:
        return {"status": "opt_out", "markers": opt, "opt_out": True, "safe_text": ""}
    return {"status": "clean", "markers": [], "opt_out": False, "safe_text": redact(t)[:limit]}


def wrap_untrusted(label: str, text: str) -> str:
    """Wrap screened text so the prompt treats it as quoted data, never as instructions."""
    cleaned = text.replace("<", "(").replace(">", ")")
    return f"<untrusted_{label}>\n{cleaned}\n</untrusted_{label}>"
