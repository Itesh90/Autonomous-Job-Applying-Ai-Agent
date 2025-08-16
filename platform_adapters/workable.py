"""
Workable ATS platform adapter
"""
import asyncio
from typing import Dict, Any, List
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from .base_adapter import BaseAdapter, AdapterResult
from utils.logger import get_logger

logger = get_logger(__name__)

class WorkableAdapter(BaseAdapter):
    """Adapter for Workable ATS platform"""
    
    def __init__(self):
        super().__init__()
        self.platform_name = "Workable"
        
        # Workable-specific selectors  
        self.field_selectors = {
            'firstname': [
                "input[name='firstname']",
                "input[id='candidate_firstname']",
                "input[placeholder*='First']"
            ],
            'lastname': [
                "input[name='lastname']",
                "input[id='candidate_lastname']",
                "input[placeholder*='Last']"
            ],
            'email': [
                "input[name='email']",
                "input[id='candidate_email']",
                "input[type='email']"
            ],
            'phone': [
                "input[name='phone']",
                "input[id='candidate_phone']",
                "input[type='tel']"
            ],
            'resume': [
                "input[name='resume']",
                "input[type='file']",
                "input[accept*='pdf']"
            ],
            'cover_letter': [
                "textarea[name='cover_letter']",
                "textarea[id='cover_letter']",
                "textarea[name='message']"
            ],
            'summary': [
                "textarea[name='summary']",
                "textarea[id='candidate_summary']",
                "textarea[placeholder*='summary']"
            ],
            'linkedin': [
                "input[name='linkedin']",
                "input[placeholder*='LinkedIn']"
            ]
        }
    
    async def detect_platform(self, driver: WebDriver, url: str) -> bool:
        """Detect if current page is Workable"""
        try:
            # Check URL
            if 'workable.com' in url or 'apply.workable' in url:
                return True
            
            # Check page elements
            workable_indicators = [
                "div[class*='workable']",
                "form[action*='workable']",
                "script[src*='workable']",
                "meta[content*='Workable']",
                "div[data-ui='application-form']",
                "div.careers-form"
            ]
            
            for indicator in workable_indicators:
                elements = driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements:
                    logger.info(f"Workable platform detected via: {indicator}")
                    return True
            
            # Check for Workable-specific form structure
            form_elements = driver.find_elements(By.CSS_SELECTOR, "input[id^='candidate_']")
            if len(form_elements) > 2:
                logger.info("Workable platform detected via form structure")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting Workable platform: {e}")
            return False
    
    async def get_form_fields(self, driver: WebDriver) -> Dict[str, Any]:
        """Extract form fields from Workable page"""
        fields = {}
        
        try:
            # Detect form language
            lang = await self._detect_form_language(driver)
            logger.info(f"Detected form language: {lang}")
            
            # Find all input fields
            inputs = driver.find_elements(By.CSS_SELECTOR, "input, textarea, select")
            
            for element in inputs:
                field_info = await self.extract_field_info(driver, element)
                if field_info.get('name') or field_info.get('id'):
                    field_key = field_info.get('name') or field_info.get('id')
                    field_info['language'] = lang
                    fields[field_key] = field_info
            
            # Look for Workable's screening questions
            questions = driver.find_elements(By.CSS_SELECTOR, "div[data-ui='question'], .question-field")
            for question in questions:
                try:
                    label = question.find_element(By.CSS_SELECTOR, "label, .question-label").text
                    input_element = question.find_element(By.CSS_SELECTOR, "input, textarea, select")
                    field_info = await self.extract_field_info(driver, input_element)
                    field_info['label'] = label
                    field_info['type'] = 'screening_question'
                    fields[f"question_{len(fields)}"] = field_info
                except:
                    continue
            
            logger.info(f"Found {len(fields)} form fields on Workable page")
            
        except Exception as e:
            logger.error(f"Error extracting Workable form fields: {e}")
        
        return fields
    
    async def fill_form(self, driver: WebDriver, candidate_data: Dict[str, Any], job_data: Dict[str, Any]) -> AdapterResult:
        """Fill Workable application form"""
        screenshots = []
        fields_filled = []
        fields_failed = []
        fields_needs_review = []
        
        try:
            # Take initial screenshot
            initial_screenshot = await self.take_screenshot(driver, "initial")
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
            
            # Detect language for international applications
            form_language = await self._detect_form_language(driver)
            
            # Fill basic fields
            field_mapping = {
                'firstname': candidate_data.get('first_name', ''),
                'lastname': candidate_data.get('last_name', ''),
                'email': candidate_data.get('email', ''),
                'phone': candidate_data.get('phone', ''),
                'linkedin': candidate_data.get('linkedin_url', '')
            }
            
            for field_name, value in field_mapping.items():
                if not value:
                    continue
                
                # Localize value if needed
                if form_language != 'en' and field_name in ['firstname', 'lastname']:
                    value = self._localize_value(value, form_language)
                
                selectors = self.field_selectors.get(field_name, [])
                filled = False
                
                for selector in selectors:
                    if await self.fill_field(driver, selector, value):
                        fields_filled.append(field_name)
                        filled = True
                        break
                
                if not filled and field_name in ['firstname', 'lastname', 'email']:
                    fields_failed.append(field_name)
            
            # Handle resume upload
            if candidate_data.get('resume_file_path'):
                resume_selectors = self.field_selectors.get('resume', [])
                for selector in resume_selectors:
                    if await self.fill_field(driver, selector, candidate_data['resume_file_path'], 'file'):
                        fields_filled.append('resume')
                        break
                else:
                    fields_needs_review.append('resume')
            
            # Handle cover letter
            cover_letter = job_data.get('generated_cover_letter', '')
            if cover_letter:
                cl_selectors = self.field_selectors.get('cover_letter', [])
                for selector in cl_selectors:
                    if await self.fill_field(driver, selector, cover_letter, 'textarea'):
                        fields_filled.append('cover_letter')
                        break
            
            # Handle summary field (Workable specific)
            if candidate_data.get('profile_summary'):
                summary_selectors = self.field_selectors.get('summary', [])
                for selector in summary_selectors:
                    if await self.fill_field(driver, selector, candidate_data['profile_summary'], 'textarea'):
                        fields_filled.append('summary')
                        break
            
            # Handle Workable screening questions
            await self._handle_workable_questions(driver, candidate_data, job_data, fields_needs_review)
            
            # Handle education and experience sections if present
            await self._handle_education_section(driver, candidate_data, fields_filled, fields_needs_review)
            await self._handle_experience_section(driver, candidate_data, fields_filled, fields_needs_review)
            
            # Take final screenshot
            final_screenshot = await self.take_screenshot(driver, "final")
            if final_screenshot:
                screenshots.append(final_screenshot)
            
            # Calculate confidence
            total_fields = len(fields_filled) + len(fields_failed) + len(fields_needs_review)
            confidence = self.calculate_confidence(len(fields_filled), len(fields_failed), total_fields)
            
            return AdapterResult(
                success=confidence >= self.confidence_threshold,
                platform=self.platform_name,
                fields_filled=fields_filled,
                fields_failed=fields_failed,
                fields_needs_review=fields_needs_review,
                screenshots=screenshots,
                confidence_score=confidence,
                metadata={'form_language': form_language}
            )
            
        except Exception as e:
            logger.error(f"Error filling Workable form: {e}")
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
    
    async def _detect_form_language(self, driver: WebDriver) -> str:
        """Detect form language from HTML lang attribute or content"""
        try:
            # Check HTML lang attribute
            html_element = driver.find_element(By.TAG_NAME, "html")
            lang_attr = html_element.get_attribute('lang')
            if lang_attr:
                return lang_attr[:2].lower()
            
            # Check for language indicators in text
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            
            # Common non-English indicators
            if any(word in page_text for word in ['nom', 'prénom', 'courriel']):
                return 'fr'
            elif any(word in page_text for word in ['nombre', 'apellido', 'correo']):
                return 'es'
            elif any(word in page_text for word in ['nome', 'cognome', 'email']):
                return 'it'
            elif any(word in page_text for word in ['vorname', 'nachname', 'e-mail']):
                return 'de'
                
        except Exception as e:
            logger.debug(f"Error detecting language: {e}")
        
        return 'en'  # Default to English
    
    def _localize_value(self, value: str, language: str) -> str:
        """Localize value for different languages if needed"""
        # This is a placeholder - in production, you'd want proper localization
        return value
    
    async def _handle_workable_questions(self, driver: WebDriver, candidate_data: Dict[str, Any],
                                        job_data: Dict[str, Any], fields_needs_review: List[str]):
        """Handle Workable screening questions"""
        try:
            questions = driver.find_elements(By.CSS_SELECTOR, "div[data-ui='question']")
            
            for question in questions:
                try:
                    question_text = question.text.lower()
                    
                    # Yes/No questions
                    if any(phrase in question_text for phrase in ['willing to relocate', 'available to start', 'authorized to work']):
                        yes_option = question.find_element(By.CSS_SELECTOR, "input[value='yes'], input[value='true']")
                        if yes_option and not yes_option.is_selected():
                            yes_option.click()
                    
                    # Salary expectation
                    elif 'salary' in question_text or 'compensation' in question_text:
                        salary_input = question.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                        if salary_input:
                            expected_salary = candidate_data.get('expected_salary', '')
                            if expected_salary:
                                salary_input.clear()
                                salary_input.send_keys(str(expected_salary))
                            else:
                                fields_needs_review.append('salary_expectation')
                    
                    # Notice period
                    elif 'notice period' in question_text:
                        notice_input = question.find_element(By.CSS_SELECTOR, "input[type='text']")
                        notice_input.clear()
                        notice_input.send_keys(candidate_data.get('notice_period', '2 weeks'))
                    
                    else:
                        fields_needs_review.append(f"question_{question_text[:30]}")
                        
                except Exception as e:
                    logger.debug(f"Error handling question: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error handling Workable questions: {e}")
    
    async def _handle_education_section(self, driver: WebDriver, candidate_data: Dict[str, Any],
                                       fields_filled: List[str], fields_needs_review: List[str]):
        """Handle Workable education section if present"""
        try:
            education_section = driver.find_elements(By.CSS_SELECTOR, "div[data-ui='education'], .education-section")
            if not education_section:
                return
            
            education_data = candidate_data.get('education', [])
            if education_data and len(education_data) > 0:
                # Fill first education entry
                edu = education_data[0]
                
                # School name
                school_input = driver.find_element(By.CSS_SELECTOR, "input[name*='school'], input[placeholder*='School']")
                school_input.clear()
                school_input.send_keys(edu.get('school', ''))
                
                # Degree
                degree_input = driver.find_element(By.CSS_SELECTOR, "input[name*='degree'], input[placeholder*='Degree']")
                degree_input.clear()
                degree_input.send_keys(edu.get('degree', ''))
                
                # Field of study
                field_input = driver.find_element(By.CSS_SELECTOR, "input[name*='field'], input[placeholder*='Field']")
                field_input.clear()
                field_input.send_keys(edu.get('field', ''))
                
                fields_filled.append('education')
            else:
                fields_needs_review.append('education')
                
        except Exception as e:
            logger.debug(f"Error handling education section: {e}")
    
    async def _handle_experience_section(self, driver: WebDriver, candidate_data: Dict[str, Any],
                                        fields_filled: List[str], fields_needs_review: List[str]):
        """Handle Workable experience section if present"""
        try:
            experience_section = driver.find_elements(By.CSS_SELECTOR, "div[data-ui='experience'], .experience-section")
            if not experience_section:
                return
            
            experiences = candidate_data.get('experiences', [])
            if experiences and len(experiences) > 0:
                # Fill first experience entry
                exp = experiences[0]
                
                # Job title
                title_input = driver.find_element(By.CSS_SELECTOR, "input[name*='title'], input[placeholder*='Title']")
                title_input.clear()
                title_input.send_keys(exp.get('title', ''))
                
                # Company
                company_input = driver.find_element(By.CSS_SELECTOR, "input[name*='company'], input[placeholder*='Company']")
                company_input.clear()
                company_input.send_keys(exp.get('company', ''))
                
                # Description
                desc_textarea = driver.find_element(By.CSS_SELECTOR, "textarea[name*='description']")
                desc_textarea.clear()
                desc_textarea.send_keys(exp.get('description', ''))
                
                fields_filled.append('experience')
            else:
                fields_needs_review.append('experience')
                
        except Exception as e:
            logger.debug(f"Error handling experience section: {e}")
