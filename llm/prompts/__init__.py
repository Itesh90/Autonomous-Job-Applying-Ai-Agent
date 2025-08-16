# llm/prompts/__init__.py
from .field_mapping import (
    FIELD_MAPPING_SYSTEM_PROMPT, 
    FIELD_MAPPING_USER_PROMPT, 
    FIELD_MAPPING_SETTINGS,
    validate_mapping_response,
    format_field_mapping_prompt
)
from .cover_letter import (
    COVER_LETTER_SYSTEM_PROMPT,
    COVER_LETTER_USER_PROMPT,
    COVER_LETTER_SETTINGS,
    validate_cover_letter_response,
    format_cover_letter_prompt
)

__all__ = [
    'FIELD_MAPPING_SYSTEM_PROMPT', 'FIELD_MAPPING_USER_PROMPT', 'FIELD_MAPPING_SETTINGS',
    'validate_mapping_response', 'format_field_mapping_prompt',
    'COVER_LETTER_SYSTEM_PROMPT', 'COVER_LETTER_USER_PROMPT', 'COVER_LETTER_SETTINGS',
    'validate_cover_letter_response', 'format_cover_letter_prompt'
]
