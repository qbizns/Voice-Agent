"""SSML generation with Egyptian pronunciation support.

Provides dialect-specific pronunciation lexicons for natural-sounding
Arabic speech, with special focus on Egyptian colloquialisms and
military/technical terminology.
"""

import re
from typing import Dict, Optional
from loguru import logger
from .voice_profiles import GenderProfile, get_lang_for_dialect


# ==========================================
# EGYPTIAN ARABIC PRONUNCIATION LEXICON
# ==========================================
EGYPTIAN_LEXICON: Dict[str, str] = {
    # Military/Technical terms (M1A1 Abrams knowledge base)
    "M1A1": "<phoneme alphabet='ipa' ph='ɛm.wæn.eɪ.wæn'>M1A1</phoneme>",
    "M1A2": "<phoneme alphabet='ipa' ph='ɛm.wæn.eɪ.tuː'>M1A2</phoneme>",
    "أبرامز": "<emphasis level='moderate'>أبرامز</emphasis>",
    "توربيني": "<emphasis level='moderate'>توربيني</emphasis>",
    "كم/ساعة": "كيلومتر في الساعة",
    "ملم": "مليمتر",
    "مم": "مليمتر",
    "كم": "كيلومتر",

    # Religious/Respectful expressions (slow pronunciation)
    "إن شاء الله": "<prosody rate='slow'>إن شاء الله</prosody>",
    "الحمد لله": "<prosody rate='slow'>الحمد لله</prosody>",
    "بإذن الله": "<prosody rate='slow'>بإذن الله</prosody>",
    "سبحان الله": "<prosody rate='slow'>سبحان الله</prosody>",
    "ماشاء الله": "<prosody rate='slow'>ماشاء الله</prosody>",

    # Egyptian colloquialisms (add natural pauses)
    "يعني": "يعني<break time='200ms'/>",
    "طيب": "طيب<break time='150ms'/>",
    "ماشي": "ماشي<break time='150ms'/>",
    "تمام": "تمام<break time='150ms'/>",
    "أيوة": "أيوة<break time='100ms'/>",
    "لأ": "لأ<break time='100ms'/>",
    "خلاص": "خلاص<break time='150ms'/>",
    "يلا": "يلا<break time='100ms'/>",

    # Common Egyptian phrases
    "إزيك": "<emphasis level='moderate'>إزيك</emphasis>",
    "عامل إيه": "<emphasis level='moderate'>عامل إيه</emphasis>",
    "أهلا وسهلا": "أهلا وسهلا<break time='200ms'/>",

    # Numbers/Units clarity
    "١": "واحد",
    "٢": "اتنين",
    "٣": "تلاتة",
    "٤": "أربعة",
    "٥": "خمسة",
}

# ==========================================
# SAUDI ARABIC PRONUNCIATION LEXICON
# ==========================================
SAUDI_LEXICON: Dict[str, str] = {
    # Saudi colloquialisms
    "وش": "وش<break time='150ms'/>",
    "كيفك": "كيفك<break time='100ms'/>",
    "زين": "زين<break time='150ms'/>",
    "ماشي": "ماشي<break time='150ms'/>",

    # Religious expressions (same as Egyptian)
    "إن شاء الله": "<prosody rate='slow'>إن شاء الله</prosody>",
    "الحمد لله": "<prosody rate='slow'>الحمد لله</prosody>",
}

# ==========================================
# LEVANTINE ARABIC PRONUNCIATION LEXICON
# ==========================================
LEVANTINE_LEXICON: Dict[str, str] = {
    # Levantine colloquialisms
    "شو": "شو<break time='150ms'/>",
    "كيفك": "كيفك<break time='100ms'/>",
    "منيح": "منيح<break time='150ms'/>",
    "يلا": "يلا<break time='100ms'/>",

    # Religious expressions
    "إن شاء الله": "<prosody rate='slow'>إن شاء الله</prosody>",
}

# ==========================================
# DIALECT-SPECIFIC LEXICON MAPPING
# ==========================================
DIALECT_LEXICONS: Dict[str, Dict[str, str]] = {
    "arabic_egypt": EGYPTIAN_LEXICON,
    "arabic_saudi": SAUDI_LEXICON,
    "arabic_levantine": LEVANTINE_LEXICON,
    "arabic_gulf": SAUDI_LEXICON,  # Gulf uses similar to Saudi
    # Other dialects default to empty (no special pronunciation)
}


def apply_pronunciation_lexicon(text: str, dialect: str) -> str:
    """Apply dialect-specific pronunciation rules.

    Replaces special terms with SSML pronunciation hints for
    more natural-sounding speech.

    Args:
        text: Input text
        dialect: Dialect key (e.g., "arabic_egypt")

    Returns:
        Text with SSML pronunciation hints
    """
    lexicon = DIALECT_LEXICONS.get(dialect, {})

    if not lexicon:
        return text

    # Sort by length (longest first) to avoid partial replacements
    sorted_terms = sorted(lexicon.keys(), key=len, reverse=True)

    modified_text = text

    for term in sorted_terms:
        replacement = lexicon[term]
        # Use word boundaries to avoid partial matches
        # For Arabic, we need to be careful with word boundaries
        pattern = r'(?<!\w)' + re.escape(term) + r'(?!\w)'
        modified_text = re.sub(pattern, replacement, modified_text, flags=re.UNICODE)

    if modified_text != text:
        logger.debug(f"Applied pronunciation lexicon ({dialect}): {len(sorted_terms)} rules")

    return modified_text


def generate_ssml(
    text: str,
    voice_profile: GenderProfile,
    dialect: str,
    use_lexicon: bool = True
) -> str:
    """Generate SSML markup for enhanced pronunciation.

    Creates proper SSML structure with:
    - Correct xml:lang for dialect
    - Voice selection
    - Prosody (rate, pitch)
    - Pronunciation lexicon (if enabled)

    Args:
        text: Plain text to convert
        voice_profile: Voice configuration
        dialect: Dialect key
        use_lexicon: Apply pronunciation lexicon

    Returns:
        SSML markup string
    """
    # Get language code for dialect
    lang = get_lang_for_dialect(dialect)

    # Apply pronunciation lexicon
    if use_lexicon:
        text = apply_pronunciation_lexicon(text, dialect)

    # Generate SSML
    ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang}">
    <voice name="{voice_profile.voice_id}">
        <prosody rate="{voice_profile.rate}" pitch="{voice_profile.pitch}">
            {text}
        </prosody>
    </voice>
</speak>"""

    logger.debug(f"Generated SSML for {dialect} ({lang})")
    return ssml


def normalize_arabic_text(text: str) -> str:
    """Normalize Arabic text for better TTS.

    Performs text cleanup:
    - Remove Tatweel (ـ)
    - Normalize Arabic punctuation
    - Normalize spaces
    - Remove diacritics (optional)

    Args:
        text: Input Arabic text

    Returns:
        Normalized text
    """
    if not text:
        return text

    # Remove Tatweel (Arabic text decoration character)
    text = text.replace('\u0640', '')

    # Normalize Arabic punctuation to Latin equivalents
    text = text.replace('،', ',')    # Arabic comma
    text = text.replace('؛', ';')    # Arabic semicolon
    text = text.replace('؟', '?')    # Arabic question mark

    # Normalize various quote styles
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Normalize line breaks
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')

    return text


def add_pauses_for_punctuation(text: str) -> str:
    """Add SSML break tags for natural pauses at punctuation.

    Args:
        text: Input text

    Returns:
        Text with SSML break tags
    """
    # Add pauses after sentence-ending punctuation
    text = re.sub(r'([.!؟۔])\s+', r'\1<break time="500ms"/>', text)

    # Add shorter pauses after commas
    text = re.sub(r'([,،؛])\s+', r'\1<break time="250ms"/>', text)

    return text


def emphasize_keywords(text: str, keywords: list[str]) -> str:
    """Add emphasis to specific keywords.

    Useful for highlighting important terms in responses.

    Args:
        text: Input text
        keywords: List of keywords to emphasize

    Returns:
        Text with SSML emphasis tags
    """
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        replacement = f'<emphasis level="moderate">{keyword}</emphasis>'
        text = re.sub(pattern, replacement, text, flags=re.UNICODE)

    return text


def adjust_speaking_rate_for_technical_content(text: str) -> str:
    """Slow down speech for technical/complex content.

    Detects technical terms and wraps them in slower prosody.

    Args:
        text: Input text

    Returns:
        Text with adjusted prosody
    """
    # Detect if text contains technical terms (numbers, English, etc.)
    has_numbers = bool(re.search(r'\d+', text))
    has_english = bool(re.search(r'[A-Za-z]{3,}', text))

    if has_numbers or has_english:
        # Wrap entire text in slightly slower prosody
        return f'<prosody rate="-10%">{text}</prosody>'

    return text
