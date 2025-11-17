"""Voice profile management with YAML-based configuration.

Manages 32 Arabic voices across 16 dialects with Egyptian as default.
"""

import yaml
from pathlib import Path
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from loguru import logger


class GenderProfile(BaseModel):
    """Profile for a specific gender voice."""
    voice_id: str = Field(..., description="Edge TTS voice ID")
    display_name: str = Field(..., description="Human-readable voice name")
    rate: str = Field("+0%", description="Speech rate adjustment")
    pitch: str = Field("+0Hz", description="Pitch adjustment")
    volume: str = Field("+0%", description="Volume adjustment")
    description: Optional[str] = Field(None, description="Voice description")


class DialectProfile(BaseModel):
    """Profile for an Arabic dialect."""
    label: str = Field(..., description="Display label for dialect")
    lang: str = Field(..., description="BCP-47 language tag (e.g., 'ar-EG')")
    flag: str = Field(..., description="Flag emoji for dialect")
    region: str = Field(..., description="Geographic region")
    male: Optional[GenderProfile] = Field(None, description="Male voice profile")
    female: Optional[GenderProfile] = Field(None, description="Female voice profile")


class VoiceProfiles(BaseModel):
    """Container for all voice profiles."""
    dialects: Dict[str, DialectProfile] = Field(
        default_factory=dict,
        description="Mapping of dialect keys to profiles"
    )


# Global cache for loaded profiles
_profiles_cache: Optional[VoiceProfiles] = None


def load_voice_profiles() -> VoiceProfiles:
    """Load voice profiles from YAML file.

    Returns:
        VoiceProfiles object with all dialect configurations

    Raises:
        FileNotFoundError: If YAML file not found
        ValueError: If YAML parsing fails
    """
    global _profiles_cache

    if _profiles_cache is not None:
        return _profiles_cache

    yaml_path = Path("app/config/voice_profiles_arabic.yml")

    if not yaml_path.exists():
        logger.error(f"Voice profiles YAML not found: {yaml_path}")
        raise FileNotFoundError(f"Voice profiles not found: {yaml_path}")

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("Empty voice profiles YAML")

        profiles = VoiceProfiles(dialects=data)
        _profiles_cache = profiles

        logger.info(f"✅ Loaded {len(profiles.dialects)} Arabic dialect profiles from YAML")

        # Log Egyptian default
        if "arabic_egypt" in profiles.dialects:
            egypt = profiles.dialects["arabic_egypt"]
            logger.info(f"🇪🇬 Egyptian default: {egypt.female.voice_id if egypt.female else 'N/A'}")

        return profiles

    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error: {e}")
        raise ValueError(f"Failed to parse voice profiles YAML: {e}")
    except Exception as e:
        logger.error(f"Failed to load voice profiles: {e}")
        raise


def get_voice_profile(
    dialect: str = "arabic_egypt",
    gender: str = "female"
) -> GenderProfile:
    """Get voice profile for specified dialect and gender.

    Fallback logic:
    1. Try requested dialect + gender
    2. Try requested dialect + opposite gender
    3. Fall back to arabic_egypt + female (default)
    4. Fall back to arabic_egypt + male
    5. If all fail, raise error

    Args:
        dialect: Dialect key (e.g., "arabic_egypt")
        gender: Gender ("male" or "female")

    Returns:
        GenderProfile for the voice

    Raises:
        ValueError: If no valid voice profile found
    """
    profiles = load_voice_profiles()

    # Normalize inputs
    dialect = dialect.lower().strip()
    gender = gender.lower().strip()

    # Validate gender
    if gender not in ["male", "female"]:
        logger.warning(f"Invalid gender '{gender}', defaulting to 'female'")
        gender = "female"

    # Try requested dialect + gender
    if dialect in profiles.dialects:
        dialect_profile = profiles.dialects[dialect]
        voice_profile = getattr(dialect_profile, gender, None)

        if voice_profile:
            logger.debug(f"✓ Voice selected: {dialect} / {gender} = {voice_profile.voice_id}")
            return voice_profile

        # Try opposite gender
        opposite_gender = "male" if gender == "female" else "female"
        voice_profile = getattr(dialect_profile, opposite_gender, None)

        if voice_profile:
            logger.warning(
                f"⚠ Dialect '{dialect}' has no {gender} voice, using {opposite_gender}"
            )
            return voice_profile

    # Fall back to Egyptian default
    if dialect != "arabic_egypt":
        logger.warning(f"⚠ Dialect '{dialect}' not found, falling back to Egyptian Arabic")

    if "arabic_egypt" in profiles.dialects:
        egypt_profile = profiles.dialects["arabic_egypt"]

        # Try requested gender
        voice_profile = getattr(egypt_profile, gender, None)
        if voice_profile:
            logger.info(f"🇪🇬 Using Egyptian default: {gender} = {voice_profile.voice_id}")
            return voice_profile

        # Try opposite gender for Egyptian
        opposite_gender = "male" if gender == "female" else "female"
        voice_profile = getattr(egypt_profile, opposite_gender, None)

        if voice_profile:
            logger.info(f"🇪🇬 Using Egyptian default: {opposite_gender} = {voice_profile.voice_id}")
            return voice_profile

    # If we get here, configuration is broken
    logger.error("❌ No valid voice profiles found - check voice_profiles_arabic.yml")
    raise ValueError(
        "No valid voice profiles found. Ensure voice_profiles_arabic.yml contains "
        "at least 'arabic_egypt' with male or female voice."
    )


def list_available_dialects() -> List[Dict[str, str]]:
    """List all available Arabic dialects.

    Returns:
        List of dialect info dictionaries with keys:
        - key: dialect key (e.g., "arabic_egypt")
        - label: display label (e.g., "Egyptian / مصري")
        - lang: BCP-47 tag (e.g., "ar-EG")
        - flag: emoji flag
        - region: geographic region
    """
    profiles = load_voice_profiles()

    dialects = [
        {
            "key": key,
            "label": profile.label,
            "lang": profile.lang,
            "flag": profile.flag,
            "region": profile.region
        }
        for key, profile in profiles.dialects.items()
    ]

    # Sort: Egyptian first, then alphabetically
    dialects.sort(key=lambda x: (x["key"] != "arabic_egypt", x["key"]))

    return dialects


def list_voices_for_dialect(dialect: str) -> Dict[str, Optional[GenderProfile]]:
    """Get male/female voices for specific dialect.

    Args:
        dialect: Dialect key

    Returns:
        Dictionary with "male" and "female" keys (values may be None)
    """
    profiles = load_voice_profiles()

    if dialect not in profiles.dialects:
        logger.warning(f"Dialect '{dialect}' not found")
        return {"male": None, "female": None}

    dialect_profile = profiles.dialects[dialect]

    return {
        "male": dialect_profile.male,
        "female": dialect_profile.female
    }


def get_lang_for_dialect(dialect: str) -> str:
    """Get BCP-47 language tag for dialect.

    Used for SSML xml:lang attribute.

    Args:
        dialect: Dialect key

    Returns:
        Language tag (e.g., "ar-EG")
    """
    profiles = load_voice_profiles()

    if dialect in profiles.dialects:
        return profiles.dialects[dialect].lang

    # Fallback to Egyptian
    logger.warning(f"Dialect '{dialect}' not found, returning 'ar-EG'")
    return "ar-EG"


def get_all_voice_ids() -> List[str]:
    """Get list of all available voice IDs.

    Useful for testing and validation.

    Returns:
        List of Edge TTS voice IDs
    """
    profiles = load_voice_profiles()
    voice_ids = []

    for dialect_profile in profiles.dialects.values():
        if dialect_profile.male:
            voice_ids.append(dialect_profile.male.voice_id)
        if dialect_profile.female:
            voice_ids.append(dialect_profile.female.voice_id)

    return voice_ids


def get_dialect_count() -> int:
    """Get total number of dialects.

    Returns:
        Number of dialect profiles
    """
    profiles = load_voice_profiles()
    return len(profiles.dialects)


def get_voice_count() -> int:
    """Get total number of voices (male + female).

    Returns:
        Total voice count
    """
    return len(get_all_voice_ids())


def reload_profiles() -> None:
    """Reload voice profiles from YAML (clear cache).

    Useful for development when YAML is updated.
    """
    global _profiles_cache
    _profiles_cache = None
    load_voice_profiles()
    logger.info("Voice profiles reloaded from YAML")


# Preload on module import
try:
    load_voice_profiles()
except Exception as e:
    logger.error(f"Failed to preload voice profiles: {e}")
    # Don't raise - allow app to start, will fail on first TTS request
