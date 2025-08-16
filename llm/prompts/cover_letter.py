# llm/prompts/cover_letter.py
import json
from typing import Dict, Any

COVER_LETTER_SYSTEM_PROMPT = """You are a professional cover letter and application response writer. Create compelling, personalized application materials that highlight candidate strengths relevant to the specific job.

REQUIREMENTS:
1. Return ONLY valid JSON with the specified structure
2. Cover letter should be 3-4 paragraphs, professional tone
3. Key points should be specific achievements that match job requirements
4. Avoid generic phrases and clichés
5. Maintain authenticity to candidate's actual experience
6. Customize for the specific company and role

WRITING GUIDELINES:
- Opening: Hook with relevant experience or passion for the role
- Body: 2-3 specific examples of relevant achievements with metrics
- Closing: Enthusiasm for the role and call to action
- Key points: Bullet-worthy achievements that directly address job requirements
- Tone: Professional but personable, confident without arrogance

JSON SCHEMA:
{
    "cover_letter": "Full cover letter text (3-4 paragraphs)",
    "key_points": [
        "Specific achievement 1 with metrics",
        "Relevant skill or experience 2", 
        "Leadership or impact example 3"
    ],
    "customization_notes": "Brief explanation of job-specific elements included",
    "confidence_score": 0.0-1.0
}
"""

COVER_LETTER_USER_PROMPT = """
CANDIDATE PROFILE:
Name: {candidate_name}
Current Role: {current_role}
Experience: {experience_summary}
Key Skills: {key_skills}
Notable Achievements: {achievements}

JOB DETAILS:
Company: {company_name}
Role: {job_title}
Job Description: {job_description}
Key Requirements: {job_requirements}

ADDITIONAL CONTEXT:
Application Questions: {application_questions}
Company Info: {company_info}

Create a tailored cover letter and key points that demonstrate fit for this specific role.
"""

# Model Settings for Cover Letter Generation
COVER_LETTER_SETTINGS = {
    "temperature": 0.7,
    "max_tokens": 1500,
    "top_p": 0.9,
    "frequency_penalty": 0.3,
    "presence_penalty": 0.1
}

def validate_cover_letter_response(response: str) -> dict:
    """Validate and clean LLM cover letter response"""
    try:
        data = json.loads(response.strip())
        
        # Required fields
        required_fields = ["cover_letter", "key_points", "confidence_score"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Content validation
        if len(data["cover_letter"]) < 200:
            raise ValueError("Cover letter too short")
        if not isinstance(data["key_points"], list) or len(data["key_points"]) < 2:
            raise ValueError("key_points must be array with 2+ items")
            
        return data
    except Exception as e:
        raise ValueError(f"Cover letter validation failed: {e}")

def format_cover_letter_prompt(candidate_data: Dict[str, Any], job_data: Dict[str, Any]) -> str:
    """Format the cover letter prompt with actual data"""
    return COVER_LETTER_USER_PROMPT.format(
        candidate_name=candidate_data.get('name', 'N/A'),
        current_role=candidate_data.get('current_role', 'N/A'),
        experience_summary=candidate_data.get('experience_summary', 'N/A'),
        key_skills=', '.join(candidate_data.get('skills', [])),
        achievements=candidate_data.get('achievements', 'N/A'),
        company_name=job_data.get('company', 'N/A'),
        job_title=job_data.get('title', 'N/A'),
        job_description=job_data.get('description', 'N/A'),
        job_requirements=job_data.get('requirements', 'N/A'),
        application_questions=job_data.get('questions', 'N/A'),
        company_info=job_data.get('company_info', 'N/A')
    )
