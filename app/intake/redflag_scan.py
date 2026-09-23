"""
Deterministic Keyword Scanner for Emergency Clinical Red Flags.

Operates directly and independently on raw_transcript (unmodified patient words).
Never relies on LLM judgment or paraphrasing, guaranteeing that critical red flags
are always flagged for downstream Person B triage.

Categories scanned:
- Chest pain & acute cardiac symptoms
- Shortness of breath & acute respiratory distress
- Acute neurological deficit & stroke symptoms
- Syncope & loss of consciousness
- Severe hemorrhage
- Severe injury & traumatic emergency (trauma/accidents/fractures/burns)
- Seizure & convulsions
- Anaphylaxis & severe allergic reaction
- Thunderclap headache

DOES NOT classify priority (emergency/same-day/routine), preserving strict boundary.
"""

import re
from typing import NamedTuple


class RedFlagRule(NamedTuple):
    key: str
    canonical_symptom: str
    regex: re.Pattern


# Bilingual clinical red-flag definitions (English + Tamil Script + Transliterated Tamil)
_RAW_RULES: list[tuple[str, str, list[str]]] = [
    (
        "chest_pain",
        "Chest pain / discomfort",
        [
            r"\bchest\s+pain\b",
            r"\bchest\s+pressure\b",
            r"\bchest\s+tightness\b",
            r"\bpressure\s+in\s+chest\b",
            r"\bpain\s+radiat(?:ing|es)\s+to\s+(?:left\s+)?arm\b",
            r"\bpain\s+radiat(?:ing|es)\s+to\s+jaw\b",
            r"மார்பு\s*வலி",
            r"நெஞ்சு\s*வலி",
            r"மார்பு\s*பாரம்",
            r"\bmarbu\s+vali\b",
            r"\bnenju\s+vali\b",
            r"\bnenjil\s+vali\b",
        ],
    ),
    (
        "shortness_of_breath",
        "Shortness of breath / respiratory distress",
        [
            r"\bshort(?:ness)?\s+of\s+breath\b",
            r"\bdifficulty\s+breathing\b",
            r"\btrouble\s+breathing\b",
            r"\bcannot\s+breathe\b",
            r"\bgasping\s+for\s+(?:air|breath)\b",
            r"\bbreathless(?:ness)?\b",
            r"\bstridor\b",
            r"மூச்சுத்\s*திணறல்",
            r"மூச்சு\s*திணறல்",
            r"மூச்சு\s*விட\s*முடியவில்லை",
            r"மூச்சு\s*வாங்குகிறது",
            r"\bmoochu\s+thinaral\b",
            r"\bmoochu\s+vida\s+mudiyavillai\b",
            r"\bmoochu\s+vanguthu\b",
        ],
    ),
    (
        "stroke_symptoms",
        "Acute neurological deficit (facial droop / slurred speech / hemiparesis)",
        [
            r"\bfacial\s+droop(?:y|ing)?\b",
            r"\bface\s+(?:just\s+)?(?:went\s+)?(?:all\s+)?droop(?:y|ing)?\b",
            r"\bslurr(?:ed|ing)\b",
            r"\bslurred\s+speech\b",
            r"\bsudden\s+weakness\b",
            r"\bone[- ]sided\s+weakness\b",
            r"\bunable\s+to\s+move\s+(?:arm|leg|side)\b",
            r"\bcould\s+only\s+lift\s+one\s+(?:arm)?\b",
            r"\bsudden\s+numbness\b",
            r"\barm\s+drift\b",
            r"பக்கவாதம்",
            r"திடீர்\s*பலவீனம்",
            r"வாய்\s*கோணுதல்",
            r"பேச்சு\s*குழறுதல்",
            r"ஒரு\s*பக்கம்\s*மரத்துப்போதல்",
            r"\bpakkavatham\b",
            r"\bpechu\s+kuzharudhal\b",
            r"\bvaai\s+konudhal\b",
        ],
    ),
    (
        "loss_of_consciousness",
        "Syncope / loss of consciousness",
        [
            r"\bloss\s+of\s+consciousness\b",
            r"\bpassed\s+out\b",
            r"\bfainted\b",
            r"\bsyncope\b",
            r"\bblacked\s+out\b",
            r"\bunresponsive\b",
            r"\bcollapsed\b",
            r"மயக்கம்",
            r"சுயநினைவு\s*இழப்பு",
            r"மயங்கி\s*விழுந்தார்",
            r"\bmayakkam\b",
            r"\bsuyaninaivu\s+izhappu\b",
            r"\bmayangi\s+vizhundhar\b",
        ],
    ),
    (
        "severe_hemorrhage",
        "Severe / acute hemorrhage",
        [
            r"\bsevere\s+bleeding\b",
            r"\buncontrolled\s+bleeding\b",
            r"\bvomit(?:ing)?\s+blood\b",
            r"\bhematemesis\b",
            r"\bcough(?:ing)?\s+up\s+blood\b",
            r"\bhemoptysis\b",
            r"கடுமையான\s*ரத்தப்போக்கு",
            r"ரத்தம்\s*வாந்தி",
            r"ரத்தம்\s*கக்குதல்",
            r"\brathapokku\b",
            r"\bratham\s+vaandhi\b",
        ],
    ),
    (
        "severe_trauma",
        "Severe injury / traumatic emergency",
        [
            r"\baccident\b",
            r"\bfell\s+from\b",
            r"\bfall(?:en)?\s+(?:down|off)\b",
            r"\bhit\s+(?:by|my\s+head)\b",
            r"\bstruck\s+(?:by|in)\b",
            r"\bhead\s+injury\b",
            r"\bdeep\s+cut\b",
            r"\bopen\s+wound\b",
            r"\bpenetrating\s+wound\b",
            r"\bstab(?:bed|bing)?\b",
            r"\bgunshot\b",
            r"\bsevere\s+burn\b",
            r"\bcompound\s+fracture\b",
            r"\bbone\s+(?:sticking\s+out|exposed)\b",
            r"\bdeform(?:ed|ity)\b(?:\s+\w+){0,5}\s+(?:arm|leg|limb)\b",
            r"\bcannot\s+move\s+(?:my\s+)?(?:arm|leg)\b",
            r"\broad\s+traffic\s+accident\b",
            r"\brta\b",
            r"விபத்து",
            r"கீழே\s*விழுந்த(?:து|ார்)",
            r"தலையில்\s*அடி",
            r"தலைக்\s*காயம்",
            r"ஆழமான\s*காயம்",
            r"எலும்பு\s*முறிவு",
            r"கடுமையான\s*காயம்",
            r"தீக்காயம்",
            r"\bvibathu\b",
            r"\bkeezhe\s+vizhunthadhu\b",
            r"\bthalaikaayam\b",
            r"\belumbu\s+murivu\b",
            r"\bkaduveiana\s+kaayam\b",
        ],
    ),
    (
        "seizure",
        "Active or witnessed seizure / convulsions",
        [
            r"\bseizure\b",
            r"\bconvulsion(?:s)?\b",
            r"\bfit(?:s)?\b",
            r"வலிப்பு",
            r"ஜன்னி\s*வலிப்பு",
            r"\bvalippu\b",
            r"\bjanni\b",
        ],
    ),
    (
        "anaphylaxis",
        "Severe allergic reaction / anaphylaxis",
        [
            r"\banaphylaxis\b",
            r"\bswelling\s+of\s+(?:tongue|lips|throat|face)\b",
            r"\bthroat\s+(?:is\s+)?(?:starting\s+to\s+)?swell\b",
            r"\bthroat\s+closing\b",
            r"\blips?\s+(?:are\s+)?(?:getting\s+)?puffy\b",
            r"\bepipen\b",
            r"தொண்டை\s*வீக்கம்",
            r"நாக்கு\s*வீக்கம்",
            r"\bthondai\s+veekkam\b",
        ],
    ),
    (
        "severe_headache_thunderclap",
        "Thunderclap headache / sudden worst headache",
        [
            r"\bworst\s+headache\s+of\s+(?:my\s+)?life\b",
            r"\bthunderclap\s+headache\b",
            r"\bsudden\s+severe\s+headache\b",
            r"திடீர்\s*கடுமையான\s*தலைவலி",
            r"\bthideer\s+kaduveiana\s+thalai\s*vali\b",
        ],
    ),
]

_COMPILED_RULES: list[RedFlagRule] = [
    RedFlagRule(
        key=key,
        canonical_symptom=canonical,
        regex=re.compile(
            "|".join(patterns),
            re.IGNORECASE | re.UNICODE,
        ),
    )
    for key, canonical, patterns in _RAW_RULES
]


def scan_red_flags(raw_transcript: str) -> list[str]:
    """
    Deterministically scan raw transcript for presence of emergency red-flag indicators.

    :param raw_transcript: Unmodified transcript text.
    :return: List of matched red-flag keys (e.g. ['chest_pain', 'shortness_of_breath']).
    """
    if not raw_transcript or not raw_transcript.strip():
        return []

    matched_keys: list[str] = []
    text = raw_transcript.strip()

    for rule in _COMPILED_RULES:
        if rule.regex.search(text):
            if rule.key not in matched_keys:
                matched_keys.append(rule.key)

    return matched_keys


def get_canonical_red_flag_symptoms(matched_keys: list[str]) -> list[str]:
    """
    Convert matched red-flag keys to canonical clinical symptom descriptions.

    :param matched_keys: Keys returned by scan_red_flags.
    :return: List of canonical symptom strings suitable for inclusion in IntakeResult.symptoms.
    """
    key_to_canonical = {rule.key: rule.canonical_symptom for rule in _COMPILED_RULES}
    return [key_to_canonical[k] for k in matched_keys if k in key_to_canonical]
