# llm/prompts/field_mapping.py
import json
from typing import Dict, Any

FIELD_MAPPING_SYSTEM_PROMPT = """You are a precise form field mapping assistant. Your job is to map HTML form fields to candidate profile data.

CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON with no additional text or explanations
2. Use exact field selectors from the provided HTML
3. If a field cannot be confidently mapped, set value to "NEEDS_REVIEW"
4. Never guess or invent data not present in the candidate profile
5. Follow the exact JSON schema provided

FIELD MAPPING RULES:
- Personal info: Map name, email, phone exactly as provided
- Experience: Use most recent or most relevant experience
- Skills: Match job requirements to candidate skills when possible
- Cover letter: Use "NEEDS_REVIEW" unless specifically requested
- File uploads: Always use "NEEDS_REVIEW" for manual handling
- Checkboxes: Map to boolean values (true/false)
- Dropdowns: Use exact option values from HTML, never approximate

JSON SCHEMA:
{
    "field_mappings": {
        "selector_string": "mapped_value_or_NEEDS_REVIEW",
        "another_selector": "another_value"
    },
    "confidence_score": 0.0-1.0,
    "needs_review_count": integer,
    "unmappable_fields": ["list", "of", "selectors"]
}
"""

FIELD_MAPPING_USER_PROMPT = """
CANDIDATE PROFILE:
{candidate_profile_json}

JOB POSTING:
{job_description}

HTML FORM FIELDS:
{form_fields_html}

Map the form fields to candidate data following the requirements. Return only the JSON mapping.
"""

# Model Settings for Field Mapping
FIELD_MAPPING_SETTINGS = {
    "temperature": 0,
    "max_tokens": 2000,
    "top_p": 1.0,
    "frequency_penalty": 0,
    "presence_penalty": 0
}

def validate_mapping_response(response: str) -> dict:
    """Validate and clean LLM mapping response"""
    try:
        data = json.loads(response.strip())
        
        # Required fields validation
        required_fields = ["field_mappings", "confidence_score", "needs_review_count"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Type validation
        if not isinstance(data["field_mappings"], dict):
            raise ValueError("field_mappings must be object")
        if not (0 <= data["confidence_score"] <= 1):
            raise ValueError("confidence_score must be 0-1")
        if not isinstance(data["needs_review_count"], int):
            raise ValueError("needs_review_count must be integer")
            
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response: {e}")
    except Exception as e:
        raise ValueError(f"Response validation failed: {e}")

def format_field_mapping_prompt(candidate_profile: Dict[str, Any], job_description: str, form_fields: Dict[str, Any]) -> str:
    """Format the field mapping prompt with actual data"""
    return FIELD_MAPPING_USER_PROMPT.format(
        candidate_profile_json=json.dumps(candidate_profile, indent=2),
        job_description=job_description,
        form_fields_html=json.dumps(form_fields, indent=2)
    )
