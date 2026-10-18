"""
Canonical symptom tags and the deterministic keyword patterns that produce
them (English, Tamil script, and Tamil transliterated in Latin script).

Used by: the intake (to fill IntakeResult.symptom_tags), the triage rules
(which also scan the raw transcript directly so an extractor miss can never
hide a red flag), and the department mapping.

PROTOTYPE vocabulary. Needs review by a clinician and a Tamil speaker.
"""

from __future__ import annotations

import re

# Words that negate a following English symptom phrase in the same clause.
_NEGATORS = {
    "no", "not", "without", "denies", "deny", "never", "nor", "dont", "don't", "doesnt", "doesn't",
    "didnt", "didn't", "hasnt", "hasn't", "havent", "haven't", "isnt", "isn't", "wasnt", "wasn't",
}
_CLAUSE_BREAK = re.compile(r"[.,;:!?\n]|\bbut\b|\band\b|\bhowever\b|\bthough\b|\balthough\b", re.IGNORECASE)

# tag -> (english patterns, tamil-script patterns, transliterated patterns)
_VOCAB: dict[str, tuple[list[str], list[str], list[str]]] = {
    "chest_pain": (
        [r"chest\s*(?:pain|pressure|tightness|discomfort|ache|is\s+hurting|hurts)", r"pain\s+in\s+(?:my\s+|the\s+)?chest",
         r"pressure\s+(?:in|on)\s+(?:my\s+)?chest", r"heart\s+pain", r"pain\s+radiat\w*\s+to\s+(?:the\s+|my\s+)?(?:left\s+)?(?:arm|jaw)"],
        [r"மார்பு\s*வலி", r"நெஞ்சு\s*வலி", r"நெஞ்சுவலி", r"மார்பு\s*பாரம்", r"நெஞ்சில்\s*வலி", r"மார்பில்\s*வலி"],
        [r"nenju\s*vali", r"nenjil\s+vali", r"marbu\s+vali", r"nenju\s+valikuthu"],
    ),
    "severe_breathing_difficulty": (
        [r"difficulty\s+(?:in\s+)?breathing", r"trouble\s+breathing", r"struggling\s+to\s+breathe", r"(?:can'?t|cannot|can\s+not|unable\s+to|not\s+able\s+to)\s+breathe",
         r"gasping", r"choking", r"breathing\s+(?:is\s+)?(?:very\s+)?(?:hard|difficult)", r"respiratory\s+distress", r"airway\s+compromise"],
        [r"மூச்சுத்\s*திணறல்", r"மூச்சு\s*திணறல்", r"மூச்சு\s*விட\s*முடிய", r"மூச்சுவிட\s*முடிய", r"சுவாசிக்க\s*முடிய"],
        [r"moochu\s*thinaral", r"moochu\s+vida\s+mudiya", r"swasikka\s+mudiya"],
    ),
    "breathlessness": (
        [r"short(?:ness)?\s+of\s+breath", r"breathless", r"out\s+of\s+breath", r"breathing\s+problem", r"wheez"],
        [r"மூச்சு\s*வாங்கு", r"மூச்சிரைப்பு", r"மூச்சு\s*இரைப்பு"],
        [r"moochu\s+vang", r"moochirappu"],
    ),
    "fainting": (
        [r"faint(?:ed|ing|s)?\b", r"passed\s+out", r"black(?:ed)?\s*out", r"collapsed", r"syncope", r"lost\s+consciousness", r"loss\s+of\s+consciousness"],
        [r"மயக்கம்", r"மயங்கி", r"மயங்கினேன்", r"மயங்கிவிட்ட"],
        [r"mayakkam", r"mayangi"],
    ),
    "repeated_fainting": (
        [r"(?:faint(?:ed|ing)?|passed\s+out|black(?:ed)?\s*out)\s+(?:\w+\s+){0,3}(?:twice|again|repeatedly|several\s+times|many\s+times|more\s+than\s+once|two\s+times|three\s+times|multiple\s+times|\d+\s+times)",
         r"(?:keep|keeps|kept)\s+(?:on\s+)?(?:fainting|passing\s+out|blacking\s+out)", r"repeated(?:ly)?\s+faint", r"fainting\s+spells", r"(?:twice|again)\s+(?:\w+\s+){0,2}faint"],
        [r"(?:பலமுறை|அடிக்கடி|மீண்டும்\s*மீண்டும்|இரண்டு\s*முறை|ரெண்டு\s*தடவை|இரண்டு\s*தடவை)\s*மயக்க", r"மயக்கம்\s*(?:அடிக்கடி|மீண்டும்|பலமுறை)"],
        [r"adikkadi\s+mayakkam", r"rendu\s+thadava\s+mayakkam"],
    ),
    "unconscious": (
        [r"unconscious", r"unresponsive", r"not\s+waking\s+up", r"won'?t\s+wake\s+up", r"not\s+responding"],
        [r"சுயநினைவு\s*(?:இல்லை|இழ)", r"நினைவு\s*இழந்", r"எழுப்ப\s*முடியவில்லை"],
        [r"suyaninaivu\s+(?:illai|izha)", r"ninaivu\s+illa"],
    ),
    "seizure": (
        [r"seiz(?:ure|ing)", r"convuls", r"\bfits\b", r"having\s+a\s+fit", r"epilep"],
        [r"வலிப்பு", r"ஜன்னி"],
        [r"valippu", r"janni"],
    ),
    "seizure_now": (
        [r"(?:having|is\s+having)\s+a\s+(?:seizure|fit)\s+(?:right\s+)?now", r"still\s+(?:seizing|convulsing|fitting|shaking)", r"seizure\s+(?:is\s+)?(?:ongoing|right\s+now|won'?t\s+stop|not\s+stopping)",
         r"currently\s+(?:seizing|convulsing)", r"seizing\s+right\s+now", r"\bongoing\s+seizure"],
        [r"இப்போது\s*வலிப்பு", r"வலிப்பு\s*நிற்கவில்லை", r"வலிப்பு\s*நிக்கல"],
        [r"valippu\s+nikkala", r"ippo\s+valippu"],
    ),
    "one_sided_weakness": (
        [r"one[- ]sided\s+weakness", r"weak(?:ness)?\s+(?:on|in)\s+one\s+side", r"sudden\s+(?:weakness|numbness)", r"numb(?:ness)?\s+on\s+one\s+side",
         r"(?:could|can)\s+only\s+(?:lift|move)\s+one", r"(?:can'?t|cannot|unable\s+to)\s+(?:lift|move)\s+(?:my\s+|his\s+|her\s+)?(?:left|right)\s+(?:arm|leg|side)",
         r"arm\s+weakness\s*\(unilateral\)", r"hemiparesis", r"one\s+side\s+of\s+(?:my\s+|his\s+|her\s+)?(?:body|face)\s+(?:is\s+)?(?:weak|numb)"],
        [r"ஒரு\s*பக்கம்\s*(?:பலவீன|மரத்து|செயலிழ)", r"திடீர்\s*பலவீனம்", r"பக்கவாதம்", r"கை\s*கால்\s*செயலிழ"],
        [r"pakkavatham", r"oru\s+pakkam\s+(?:balaveenam|marathu)"],
    ),
    "facial_droop": (
        [r"fac(?:e|ial)\s+(?:\w+\s+){0,3}droop", r"droop\w*\s+(?:on\s+one\s+side|face)", r"mouth\s+(?:is\s+)?(?:drooping|twisted|crooked)"],
        [r"வாய்\s*கோண", r"முகம்\s*கோண"],
        [r"vaai\s+kon", r"mugam\s+kon"],
    ),
    "slurred_speech": (
        [r"slurr", r"(?:can'?t|cannot)\s+speak\s+properly", r"speech\s+(?:is\s+)?(?:not\s+clear|unclear|garbled)", r"trouble\s+speaking", r"words?\s+(?:are\s+|is\s+)?not\s+coming\s+out"],
        [r"பேச்சு\s*குழற", r"பேச\s*முடியவில்லை", r"வார்த்தை\s*வரவில்லை"],
        [r"pechu\s+kuzhar", r"pesa\s+mudiyala"],
    ),
    "confusion": (
        [r"confus(?:ed|ion)", r"disoriented", r"not\s+making\s+sense", r"doesn'?t\s+know\s+where"],
        [r"குழப்ப", r"குழம்பி"],
        [r"kuzhappam", r"kuzhambi"],
    ),
    "severe_bleeding": (
        [r"(?:severe|heavy|uncontrolled|profuse|massive|a\s+lot\s+of|lots\s+of)\s+bleeding", r"bleeding\s+(?:very\s+)?(?:heavily|a\s+lot|badly|non-?stop|won'?t\s+stop|will\s+not\s+stop|does\s*n'?t\s+stop|not\s+stopping|everywhere)",
         r"blood\s+(?:is\s+)?(?:gushing|pouring|spurting)", r"(?:can'?t|cannot)\s+stop\s+(?:the\s+)?bleeding", r"\bhaemorrhag|\bhemorrhag"],
        [r"கடுமையான\s*ரத்தப்போக்கு", r"அதிக\s*ரத்தப்போக்கு", r"அதிகமா(?:ன|க)?\s*ரத்தம்", r"ரத்தம்\s*நிற்கவில்லை", r"ரத்தம்\s*நிக்கல", r"இரத்தம்\s*நிற்கவில்லை"],
        [r"ratham\s+nikkala", r"athiga\s+ratham", r"rathapokku"],
    ),
    "bleeding": (
        [r"bleed", r"\bblood\b"],
        [r"ரத்த", r"இரத்த"],
        [r"\bratham\b"],
    ),
    "vomiting_blood": (
        [r"vomit\w*\s+(?:up\s+)?blood", r"blood\s+in\s+(?:my\s+|the\s+)?vomit", r"throw(?:ing)?\s+up\s+blood", r"threw\s+up\s+blood", r"haematemesis|hematemesis"],
        [r"ரத்த\s*வாந்தி", r"ரத்தம்\s*வாந்தி", r"வாந்தியில்\s*ரத்தம்", r"இரத்த\s*வாந்தி"],
        [r"ratha\s+vaanthi", r"ratham\s+vaanthi"],
    ),
    "black_stool": (
        [r"black\s+(?:stool|stools|poop|motion|motions|tarry)", r"tarry\s+stool", r"mela?ena", r"stools?\s+(?:is\s+|are\s+)?black"],
        [r"கருப்பு\s*மலம்", r"கறுப்பு\s*மலம்", r"கருப்பா\s*மலம்"],
        [r"karuppu\s+malam"],
    ),
    "head_injury": (
        [r"head\s+(?:injury|trauma|wound)", r"(?:hit|banged|bumped|hurt|injured|struck)\s+(?:my\s+|his\s+|her\s+|the\s+)?head", r"head\s+(?:got\s+)?(?:hit|banged|struck)", r"fell\s+on\s+(?:my\s+|his\s+|her\s+)?head"],
        [r"தலையில்\s*அடி", r"தலைக்?\s*காயம்", r"தலையில்\s*காயம்"],
        [r"thalaiyil\s+adi", r"thalai\s+kaayam"],
    ),
    "face_lip_swelling": (
        [r"(?:face|lips?|tongue|throat|mouth)\s+(?:is\s+|are\s+)?(?:getting\s+|starting\s+to\s+|started\s+to\s+)?(?:swell|swelling|swollen|puffy)", r"swelling\s+(?:of|in)\s+(?:the\s+|my\s+)?(?:face|lips?|tongue|throat)",
         r"swollen\s+(?:face|lips?|tongue|throat)", r"angioedema", r"throat\s+(?:is\s+)?closing"],
        [r"(?:உதடு|முகம்|நாக்கு|தொண்டை)\s*(?:வீக்கம்|வீங்கி|வீங்கு)"],
        [r"(?:udhadu|mugam|naakku|thondai)\s+veek", r"(?:udhadu|mugam|naakku|thondai)\s+veeng"],
    ),
    "palpitations": (
        [r"palpitation", r"heart\s+(?:is\s+)?(?:racing|pounding|beating\s+(?:very\s+)?fast|fluttering)", r"racing\s+heart", r"fast\s+heart\s*beat"],
        [r"படபடப்பு", r"இதயம்\s*வேகமாக", r"நெஞ்சு\s*படபட"],
        [r"padapadappu", r"nenju\s+padapada"],
    ),
    "dizziness": (
        [r"dizz(?:y|iness)", r"giddy|giddiness", r"light-?\s?headed", r"vertigo", r"room\s+(?:is\s+)?spinning"],
        [r"தலை\s*சுற்று", r"தலைசுற்ற", r"கிறுகிறுப்பு", r"தலை\s*சுத்து"],
        [r"thalai\s+su(?:th|tr)", r"kirukiruppu"],
    ),
    "sudden_severe_headache": (
        [r"worst\s+headache", r"thunderclap", r"sudden(?:ly)?\s+(?:and\s+)?(?:very\s+)?(?:severe|terrible|intense|excruciating)\s+headache", r"(?:severe|terrible)\s+headache\s+(?:came\s+on\s+|started\s+)?suddenly"],
        [r"திடீ(?:ர்|ரென)\s*(?:கடுமையான|பயங்கர)\s*தலைவலி", r"திடீ(?:ர்|ரென)\s*(?:கடுமையான|பயங்கர)\s*தலை\s*வலி"],
        [r"thideer(?:nu)?\s+(?:kadumaiyana\s+)?thalai\s*vali"],
    ),
    "headache": (
        [r"head\s*ache", r"head\s+pain", r"migraine"],
        [r"தலைவலி", r"தலை\s*வலி"],
        [r"thalai\s*vali"],
    ),
    "fever": (
        [r"fever", r"temperature", r"\bchills\b", r"febrile"],
        [r"காய்ச்சல்", r"ஜுரம்", r"ஜ்வரம்", r"சுரம்"],
        [r"kaichal", r"juram"],
    ),
    "high_fever": (
        [r"(?:very\s+)?high\s+(?:fever|temperature|temp)", r"fever\s+(?:of\s+)?(?:10[3-6]|39(?:\.\d)?|4[01](?:\.\d)?)", r"burning\s+(?:up\s+)?with\s+fever", r"raging\s+fever"],
        [r"(?:அதிக|அதிகமான|கடுமையான|கடும்|பயங்கர)\s*(?:காய்ச்சல்|ஜுரம்|ஜ்வரம்|சுரம்)"],
        [r"(?:adhiga|athiga|romba)\s+(?:kaichal|juram)"],
    ),
    "pregnant": (
        [r"pregnan", r"expecting\s+a\s+baby", r"months?\s+pregnant", r"gestation"],
        [r"கர்ப்ப"],
        [r"karppam", r"garbam", r"karbam"],
    ),
    "poisoning": (
        [r"poison", r"overdose", r"swallowed\s+(?:\w+\s+){0,2}(?:pills|tablets|bleach|kerosene|pesticide|acid)", r"drank\s+(?:\w+\s+){0,2}(?:pesticide|poison|kerosene|bleach|acid)", r"pesticide"],
        [r"விஷம்", r"பூச்சிக்கொல்லி", r"பூச்சி\s*மருந்து"],
        [r"visham", r"poochi\s+marundhu"],
    ),
    "abdominal_pain": (
        [r"(?:abdominal|stomach|tummy|belly)\s*(?:pain|ache|cramp)", r"pain\s+in\s+(?:my\s+|the\s+)?(?:stomach|abdomen|belly|tummy)",
         r"pain\s+(?:on|in)\s+(?:my\s+|the\s+)?(?:lower|upper)?\s*(?:right|left)\s+(?:side|lower|abdomen)", r"(?:right|left)\s+(?:lower|upper)\s+quadrant", r"(?:lower|upper)\s+(?:right|left)\s+(?:side\s+)?pain"],
        [r"வயிற்று\s*வலி", r"வயிறு\s*வலி", r"வயிற்றில்\s*வலி"],
        [r"vayi(?:ru|tru)\s+vali"],
    ),
    "vomiting": (
        [r"vomit", r"throwing\s+up", r"threw\s+up", r"nausea", r"nauseous"],
        [r"வாந்தி", r"குமட்டல்"],
        [r"vaa?nthi", r"kumattal"],
    ),
    "diarrhoea": (
        [r"diarrh?oea|diarrhea", r"loose\s+(?:motions?|stools?)", r"watery\s+stool"],
        [r"வயிற்றுப்போக்கு", r"பேதி"],
        [r"bedhi", r"vayitru\s+pokku"],
    ),
    "cough": (
        [r"cough"],
        [r"இருமல்"],
        [r"irumal"],
    ),
    "cold_symptoms": (
        [r"runny\s+nose", r"\bcold\b", r"sneez", r"blocked\s+nose", r"stuffy\s+nose", r"nasal\s+congestion"],
        [r"சளி", r"தும்மல்", r"மூக்கடைப்பு", r"மூக்கு\s*ஒழுகு"],
        [r"\bsali\b", r"thummal"],
    ),
    "sore_throat": (
        [r"sore\s+throat", r"throat\s+(?:pain|hurts|is\s+sore)", r"scratchy\s+throat"],
        [r"தொண்டை\s*வலி", r"தொண்டை\s*கரகரப்பு"],
        [r"thondai\s+vali"],
    ),
    "rash": (
        [r"\brash", r"hives", r"red\s+(?:spots|patches|bumps)", r"skin\s+(?:eruption|allergy)"],
        [r"தடிப்பு", r"சொறி", r"தோல்\s*அலர்ஜி", r"தோலில்\s*சிவப்பு"],
        [r"thadippu", r"thol\s+allergy"],
    ),
    "itching": (
        [r"itch"],
        [r"அரிப்பு"],
        [r"arippu"],
    ),
    "skin_problem": (
        [r"\bskin\b", r"pimple", r"acne", r"eczema", r"psoriasis", r"fungal", r"ringworm", r"dandruff", r"\bmole\b"],
        [r"தோல்", r"பரு", r"படை"],
        [r"\bthol\b"],
    ),
    "joint_pain": (
        [r"joint\s*(?:pain|ache|swelling)", r"(?:knee|shoulder|hip|ankle|wrist|elbow)\s+(?:pain|ache|hurts|swelling)", r"arthritis"],
        [r"மூட்டு\s*வலி", r"முழங்கால்\s*வலி", r"கட்டுறு\s*வலி", r"மூட்டு"],
        [r"moottu\s+vali"],
    ),
    "back_pain": (
        [r"back\s*(?:pain|ache)", r"lower\s+back", r"neck\s+pain", r"spine"],
        [r"முதுகு\s*வலி", r"கழுத்து\s*வலி", r"இடுப்பு\s*வலி"],
        [r"muthugu\s+vali", r"iduppu\s+vali"],
    ),
    "fracture_injury": (
        [r"fracture", r"broken\s+(?:bone|arm|leg|wrist|ankle|finger)", r"sprain", r"twisted\s+(?:my\s+)?(?:ankle|knee|wrist)", r"\bfell\b", r"\binjur", r"accident"],
        [r"எலும்பு\s*முறிவு", r"சுளுக்கு", r"விபத்து", r"விழுந்து"],
        [r"elumbu\s+murivu", r"sulukku", r"vibathu"],
    ),
    "wound": (
        [r"\bcut\b", r"laceration", r"wound", r"\bgash\b", r"stitches|sutures"],
        [r"வெட்டு", r"காயம்"],
        [r"kaayam", r"vettu"],
    ),
    "burn": (
        [r"\bburn(?:ed|t|s)?\b", r"scald"],
        [r"தீக்காயம்", r"சுட்டு"],
        [r"theekkaayam"],
    ),
    "ear_problem": (
        [r"ear\s*(?:pain|ache|discharge|infection)", r"hearing\s+(?:loss|problem)", r"(?:can'?t|cannot)\s+hear", r"ringing\s+in\s+(?:my\s+)?ears?", r"tinnitus"],
        [r"காது\s*வலி", r"காது\s*கேட்க", r"காதில்"],
        [r"kaathu\s+vali", r"kaadhu\s+vali"],
    ),
    "nose_problem": (
        [r"nose\s*bleed", r"sinus"],
        [r"மூக்கில்\s*ரத்தம்"],
        [r"mookku"],
    ),
    "eye_problem": (
        [r"eyes?\s+(?:pain|redness|red|itching|discharge|hurts?)", r"blurr(?:ed|y)\s+vision", r"vision\s+(?:loss|problem)"],
        [r"கண்\s*வலி", r"கண்\s*சிவப்பு", r"பார்வை\s*மங்க"],
        [r"kan\s+vali"],
    ),
    "urinary": (
        [r"(?:burning|pain)\s+(?:while|when)\s+(?:urinating|passing\s+urine|peeing)", r"urin", r"peeing"],
        [r"சிறுநீர்"],
        [r"siruneer"],
    ),
    "menstrual": (
        [r"periods?\s+(?:pain|problem|irregular|late|missed|heavy)", r"menstrua", r"white\s+discharge", r"vaginal\s+(?:bleeding|discharge)", r"missed\s+(?:my\s+)?period"],
        [r"மாதவிடாய்", r"மாதவிலக்கு"],
        [r"maadhavidai", r"mathavidai"],
    ),
    "numbness": (
        [r"numb", r"tingling", r"pins\s+and\s+needles"],
        [r"மரத்து", r"மரமர"],
        [r"marathu"],
    ),
    "fatigue": (
        [r"tired", r"fatigue", r"exhausted", r"no\s+energy", r"\bweak(?:ness)?\b"],
        [r"களைப்பு", r"களைப்பா", r"சோர்வு"],
        [r"sorvu", r"kalaippu"],
    ),
    "body_pain": (
        [r"body\s*(?:pain|aches?)", r"aching\s+all\s+over", r"myalgia"],
        [r"உடம்பு\s*வலி", r"உடல்\s*வலி"],
        [r"udambu\s+vali"],
    ),
}

ALL_TAGS: list[str] = list(_VOCAB.keys()) + ["other"]


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns]


_COMPILED = {tag: (_compile(en), _compile(ta), _compile(tr)) for tag, (en, ta, tr) in _VOCAB.items()}


def _negated(text: str, start: int) -> bool:
    """True if an English negator occurs in the same clause within 3 words before `start`."""
    before = text[:start]
    parts = _CLAUSE_BREAK.split(before)
    clause = parts[-1] if parts else before
    words = re.findall(r"[a-zA-Z']+", clause.lower())[-3:]
    return any(w in _NEGATORS for w in words)


def detect_tags(text: str, honour_negation: bool = True) -> list[str]:
    """Return canonical tags found in `text`, in vocabulary order (no 'other')."""
    if not text:
        return []
    found: list[str] = []
    for tag, (en, ta, tr) in _COMPILED.items():
        hit = False
        for rx in en + tr:
            for m in rx.finditer(text):
                if not honour_negation or not _negated(text, m.start()):
                    hit = True
                    break
            if hit:
                break
        if not hit:
            # Tamil script: post-position negation is not parsed (errs toward caution).
            hit = any(rx.search(text) for rx in ta)
        if hit:
            found.append(tag)
    return found


def normalise_tags(tags: list[str]) -> list[str]:
    """Map arbitrary tag strings to canonical tags; unknown -> 'other'."""
    out: list[str] = []
    for t in tags:
        key = (t or "").strip().lower().replace(" ", "_").replace("-", "_")
        canon = key if key in _VOCAB else "other"
        if canon not in out:
            out.append(canon)
    return out


# ---------------------------------------------------------------------------
# Fixed safety screen (asked at every booking; never chosen by the LLM)
# ---------------------------------------------------------------------------

SAFETY_SCREEN_CHIPS: dict[str, str] = {
    "chest_pain": "chest_pain",
    "trouble_breathing": "severe_breathing_difficulty",
    "fainting": "fainting",
    "severe_bleeding": "severe_bleeding",
    "sudden_weakness": "one_sided_weakness",
    "confusion": "confusion",
    "seizure": "seizure_now",
}


def safety_screen_tags(chips: list[str]) -> list[str]:
    return [SAFETY_SCREEN_CHIPS[c] for c in chips if c in SAFETY_SCREEN_CHIPS]


# ---------------------------------------------------------------------------
# Deterministic department mapping (wording: "usually seen by", never a diagnosis)
# ---------------------------------------------------------------------------

SPECIALTIES = [
    "General Medicine", "Cardiology", "Neurology", "Orthopaedics", "ENT", "Paediatrics", "Gynaecology", "Dermatology",
]

_DEPT_ORDER: list[tuple[set[str], str]] = [
    ({"pregnant", "menstrual"}, "Gynaecology"),
    ({"chest_pain", "palpitations"}, "Cardiology"),
    ({"one_sided_weakness", "facial_droop", "slurred_speech", "seizure", "seizure_now", "sudden_severe_headache", "numbness"}, "Neurology"),
    ({"fracture_injury", "joint_pain", "back_pain"}, "Orthopaedics"),
    ({"rash", "itching", "skin_problem", "burn"}, "Dermatology"),
    ({"ear_problem", "nose_problem"}, "ENT"),
    ({"cold_symptoms", "cough", "fever", "high_fever"}, "General Medicine"),
    ({"sore_throat"}, "ENT"),
]


def department_for(tags: list[str], age: int | None = None) -> str:
    if age is not None and age < 14:
        return "Paediatrics"
    s = set(tags)
    for keys, dept in _DEPT_ORDER:
        if s & keys:
            return dept
    return "General Medicine"
