"""
Generic AI-powered adapter for unknown ATS platforms
"""
import asyncio
import json
from typing import Dict, Any, List, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from .base_adapter import BaseAdapter, AdapterResult
from llm.provider_manager import ProviderManager
from rag.vector_store import VectorStore
from utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

class GenericAIAdapter(BaseAdapter):
    """AI-powered adapter for any unknown platform"""
    
    def __init__(self):
        super().__init__()
        self.platform_name = "Generic AI"
        self.llm_manager = ProviderManager()
        self.vector_store = VectorStore()
        self.confidence_threshold = 0.6  # Lower threshold for AI mapping
        
    async def detect_platform(self, driver: WebDriver, url: str) -> bool:
        """Generic adapter can handle any platform as fallback"""
        # This adapter is used when no specific adapter matches
        return True
    
    async def get_form_fields(self, driver: WebDriver) -> Dict[str, Any]:
        """Extract and analyze form fields using AI"""
        fields = {}
        
        try:
            # Get page HTML
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Find all form elements
            form_elements = soup.find_all(['input', 'textarea', 'select'])
            
            # Extract field information
            field_data = []
            for element in form_elements:
                field_info = {
                    'tag': element.name,
                    'type': element.get('type', 'text'),
                    'name': element.get('name', ''),
                    'id': element.get('id', ''),
                    'placeholder': element.get('placeholder', ''),
                    'required': element.get('required') is not None,
                    'label': self._find_label_text(soup, element),
                    'classes': ' '.join(element.get('class', [])),
                    'aria_label': element.get('aria-label', ''),
                    'value': element.get('value', '')
                }
                
                # Get options for select elements
                if element.name == 'select':
                    options = [opt.text for opt in element.find_all('option')]
                    field_info['options'] = options
                
                field_data.append(field_info)
            
            # Use AI to analyze fields
            field_analysis = await self._analyze_fields_with_ai(field_data)
            
            # Map analyzed fields
            for i, field in enumerate(field_data):
                field_key = field.get('name') or field.get('id') or f"field_{i}"
                field['ai_analysis'] = field_analysis.get(field_key, {})
                field['mapped_type'] = field_analysis.get(field_key, {}).get('type', 'unknown')
                fields[field_key] = field
            
            logger.info(f"AI analyzed {len(fields)} form fields")
            
        except Exception as e:
            logger.error(f"Error extracting form fields with AI: {e}")
        
        return fields
    
    async def fill_form(self, driver: WebDriver, candidate_data: Dict[str, Any], job_data: Dict[str, Any]) -> AdapterResult:
        """Fill form using AI-powered field mapping"""
        screenshots = []
        fields_filled = []
        fields_failed = []
        fields_needs_review = []
        
        try:
            # Take initial screenshot
            initial_screenshot = await self.take_screenshot(driver, "ai_initial")
            if initial_screenshot:
                screenshots.append(initial_screenshot)
            
            # Check for CAPTCHA
            captcha_detected = await self.detect_captcha(driver)
            if captcha_detected:
                return AdapterResult(
                    success=False,
                    platform=self.platform_name,
                    fields_filled=[],
                    fields_failed=[],
                    fields_needs_review=[],
                    screenshots=screenshots,
                    confidence_score=0.0,
                    captcha_detected=True,
                    error_message="CAPTCHA detected - manual intervention required"
                )
            
            # Get form fields
            form_fields = await self.get_form_fields(driver)
            
            # Get AI mapping for fields
            field_mappings = await self._get_ai_field_mappings(
                form_fields, candidate_data, job_data
            )
            
            # Apply mappings
            for field_key, mapping in field_mappings.items():
                if mapping['confidence'] < 0.5:
                    fields_needs_review.append(field_key)
                    continue
                
                field_info = form_fields.get(field_key, {})
                value = mapping.get('value', '')
                
                if not value or value == 'NEEDS_REVIEW':
                    fields_needs_review.append(field_key)
                    continue
                
                # Try to fill the field
                success = await self._fill_field_by_info(driver, field_info, value)
                
                if success:
                    fields_filled.append(f"{field_key}:{mapping['field_type']}")
                else:
                    fields_failed.append(field_key)
            
            # Search for similar successful applications in vector store
            similar_apps = await self._find_similar_applications(job_data)
            if similar_apps:
                logger.info(f"Found {len(similar_apps)} similar successful applications for reference")
            
            # Take final screenshot
            final_screenshot = await self.take_screenshot(driver, "ai_final")
            if final_screenshot:
                screenshots.append(final_screenshot)
            
            # Calculate confidence
            total_fields = len(fields_filled) + len(fields_failed) + len(fields_needs_review)
            confidence = self.calculate_confidence(len(fields_filled), len(fields_failed), total_fields)
            
            # Adjust confidence based on AI mapping quality
            avg_mapping_confidence = sum(m['confidence'] for m in field_mappings.values()) / len(field_mappings) if field_mappings else 0
            final_confidence = (confidence + avg_mapping_confidence) / 2
            
            return AdapterResult(
                success=final_confidence >= self.confidence_threshold,
                platform=self.platform_name,
                fields_filled=fields_filled,
                fields_failed=fields_failed,
                fields_needs_review=fields_needs_review,
                screenshots=screenshots,
                confidence_score=final_confidence,
                metadata={
                    'ai_mapping_confidence': avg_mapping_confidence,
                    'total_fields_analyzed': len(form_fields)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in AI form filling: {e}")
            return AdapterResult(
                success=False,
                platform=self.platform_name,
                fields_filled=fields_filled,
                fields_failed=fields_failed,
                fields_needs_review=fields_needs_review,
                screenshots=screenshots,
                confidence_score=0.0,
                error_message=str(e)
            )
    
    async def _analyze_fields_with_ai(self, field_data: List[Dict]) -> Dict[str, Any]:
        """Use AI to analyze and categorize form fields"""
        
        prompt = f"""
        Analyze these HTML form fields and identify their purpose.
        Return a JSON object mapping each field to its likely purpose.
        
        Common field types to identify:
        - first_name, last_name, full_name
        - email, phone
        - resume (file upload)
        - cover_letter
        - linkedin_url, portfolio_url, github_url
        - work_authorization
        - salary_expectation
        - years_experience
        - start_date
        - location_preference
        - custom_question
        
        Form fields:
        {json.dumps(field_data, indent=2)}
        
        Return JSON in this format:
        {{
            "field_name_or_id": {{
                "type": "identified_field_type",
                "confidence": 0.0-1.0,
                "reasoning": "brief explanation"
            }}
        }}
        """
        
        try:
            response = await self.llm_manager.generate_structured(
                prompt=prompt,
                temperature=0,
                response_format="json"
            )
            
            return response.get('content', {})
            
        except Exception as e:
            logger.error(f"Error analyzing fields with AI: {e}")
            return {}
    
    async def _get_ai_field_mappings(self, form_fields: Dict[str, Any], 
                                    candidate_data: Dict[str, Any], 
                                    job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI-powered field mappings"""
        
        # Prepare context from RAG
        relevant_context = await self._get_relevant_context(job_data)
        
        prompt = f"""
        Map the candidate data to the form fields.
        Use the candidate information to fill appropriate values.
        If a field cannot be confidently mapped, use "NEEDS_REVIEW".
        
        Candidate Data:
        {json.dumps(candidate_data, indent=2)}
        
        Job Information:
        {json.dumps({
            'title': job_data.get('title', ''),
            'company': job_data.get('company', ''),
            'requirements': job_data.get('requirements', '')
        }, indent=2)}
        
        Form Fields to Map:
        {json.dumps(form_fields, indent=2)}
        
        Previous Successful Applications Context:
        {relevant_context}
        
        Return JSON mapping each field to its value:
        {{
            "field_key": {{
                "value": "value_to_fill",
                "field_type": "identified_type",
                "confidence": 0.0-1.0
            }}
        }}
        
        Guidelines:
        - Use exact values from candidate data
        - For yes/no questions about work authorization, use "yes" if candidate is authorized
        - For file uploads, use the file path from candidate data
        - For salary, use candidate's expected salary if available
        - Mark uncertain fields as NEEDS_REVIEW
        """
        
        try:
            response = await self.llm_manager.generate_structured(
                prompt=prompt,
                temperature=0,
                response_format="json"
            )
            
            return response.get('content', {})
            
        except Exception as e:
            logger.error(f"Error getting AI field mappings: {e}")
            return {}
    
    async def _fill_field_by_info(self, driver: WebDriver, field_info: Dict[str, Any], value: str) -> bool:
        """Fill a field based on its information"""
        try:
            # Build selector
            selectors = []
            if field_info.get('id'):
                selectors.append(f"#{field_info['id']}")
            if field_info.get('name'):
                selectors.append(f"[name='{field_info['name']}']")
            
            if not selectors:
                return False
            
            for selector in selectors:
                try:
                    element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    
                    # Determine field type
                    field_type = field_info.get('type', 'text')
                    
                    if field_type == 'file':
                        element.send_keys(value)
                    elif field_info.get('tag') == 'select':
                        from selenium.webdriver.support.ui import Select
                        select = Select(element)
                        # Try to select by visible text or value
                        try:
                            select.select_by_visible_text(value)
                        except:
                            select.select_by_value(value)
                    elif field_info.get('tag') == 'textarea':
                        element.clear()
                        element.send_keys(value)
                    elif field_type in ['checkbox', 'radio']:
                        if value.lower() in ['true', 'yes', '1']:
                            if not element.is_selected():
                                element.click()
                    else:
                        element.clear()
                        element.send_keys(value)
                    
                    return True
                    
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error filling field: {e}")
        
        return False
    
    def _find_label_text(self, soup, element) -> str:
        """Find label text for an element in BeautifulSoup"""
        # Try to find label by 'for' attribute
        if element.get('id'):
            label = soup.find('label', {'for': element.get('id')})
            if label:
                return label.get_text(strip=True)
        
        # Try to find parent label
        parent = element.parent
        if parent and parent.name == 'label':
            return parent.get_text(strip=True)
        
        # Try aria-label
        if element.get('aria-label'):
            return element.get('aria-label')
        
        # Try placeholder as last resort
        if element.get('placeholder'):
            return element.get('placeholder')
        
        return ""
    
    async def _get_relevant_context(self, job_data: Dict[str, Any]) -> str:
        """Get relevant context from vector store"""
        try:
            # Search for similar jobs and successful applications
            query = f"{job_data.get('title', '')} {job_data.get('company', '')} application form filling"
            results = self.vector_store.search_similar(query, k=3)
            
            if results:
                context = "\n".join([r.content for r in results])
                return context[:1000]  # Limit context size
            
        except Exception as e:
            logger.debug(f"Error getting RAG context: {e}")
        
        return "No previous context available"
    
    async def _find_similar_applications(self, job_data: Dict[str, Any]) -> List[Dict]:
        """Find similar successful applications from vector store"""
        try:
            query = f"{job_data.get('title', '')} {job_data.get('company', '')} successful application"
            results = self.vector_store.search_applications(query, k=5)
            return results
        except Exception as e:
            logger.debug(f"Error finding similar applications: {e}")
            return []
