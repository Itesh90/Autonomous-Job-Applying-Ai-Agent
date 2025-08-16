"""
Greenhouse ATS platform adapter
"""
import asyncio
from typing import Dict, Any, List
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .base_adapter import BaseAdapter, AdapterResult
from utils.logger import get_logger

logger = get_logger(__name__)

class GreenhouseAdapter(BaseAdapter):
    """Adapter for Greenhouse ATS platform"""
    
    def __init__(self):
        super().__init__()
        self.platform_name = "Greenhouse"
        
        # Greenhouse-specific selectors
        self.field_selectors = {
            'first_name': [
                "input[name='job_application[first_name]']",
                "input[id='first_name']",
                "input[name='first_name']"
            ],
            'last_name': [
                "input[name='job_application[last_name]']",
                "input[id='last_name']",
                "input[name='last_name']"
            ],
            'email': [
                "input[name='job_application[email]']",
                "input[id='email']",
                "input[type='email']"
            ],
            'phone': [
                "input[name='job_application[phone]']",
                "input[id='phone']",
                "input[type='tel']"
            ],
            'resume': [
                "input[name='job_application[resume]']",
                "input[type='file'][accept*='pdf']",
                "input[type='file']"
            ],
            'cover_letter': [
                "textarea[name='job_application[cover_letter_text]']",
                "textarea[id='cover_letter']",
                "textarea[name='cover_letter']"
            ],
            'linkedin': [
                "input[name='job_application[linkedin_profile]']",
                "input[placeholder*='linkedin']"
            ],
            'website': [
                "input[name='job_application[website]']",
                "input[placeholder*='website']",
                "input[placeholder*='portfolio']"
            ]
        }
    
    async def detect_platform(self, driver: WebDriver, url: str) -> bool:
        """Detect if current page is Greenhouse"""
        try:
            # Check URL
            if 'greenhouse.io' in url or 'boards.greenhouse' in url:
                return True
            
            # Check page elements
            greenhouse_indicators = [
                "div[id*='greenhouse']",
                "div[class*='greenhouse']",
                "form[action*='greenhouse']",
                "script[src*='greenhouse']",
                "meta[content*='Greenhouse']"
            ]
            
            for indicator in greenhouse_indicators:
                elements = driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements:
                    logger.info(f"Greenhouse platform detected via: {indicator}")
                    return True
            
            # Check for Greenhouse-specific form structure
            form_elements = driver.find_elements(By.CSS_SELECTOR, "input[name^='job_application']")
            if len(form_elements) > 2:
                logger.info("Greenhouse platform detected via form structure")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting Greenhouse platform: {e}")
            return False
    
    async def get_form_fields(self, driver: WebDriver) -> Dict[str, Any]:
        """Extract form fields from Greenhouse page"""
        fields = {}
        
        try:
            # Find all input fields
            inputs = driver.find_elements(By.CSS_SELECTOR, "input, textarea, select")
            
            for element in inputs:
                field_info = await self.extract_field_info(driver, element)
                if field_info.get('name') or field_info.get('id'):
                    field_key = field_info.get('name') or field_info.get('id')
                    fields[field_key] = field_info
            
            # Look for custom questions
            custom_questions = driver.find_elements(By.CSS_SELECTOR, "div[class*='field']")
            for question in custom_questions:
                try:
                    label = question.find_element(By.TAG_NAME, "label").text
                    input_element = question.find_element(By.CSS_SELECTOR, "input, textarea, select")
                    field_info = await self.extract_field_info(driver, input_element)
                    field_info['label'] = label
                    fields[f"custom_{len(fields)}"] = field_info
                except:
                    continue
            
            logger.info(f"Found {len(fields)} form fields on Greenhouse page")
            
        except Exception as e:
            logger.error(f"Error extracting Greenhouse form fields: {e}")
        
        return fields
    
    async def fill_form(self, driver: WebDriver, candidate_data: Dict[str, Any], job_data: Dict[str, Any]) -> AdapterResult:
        """Fill Greenhouse application form"""
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
            
            # Fill basic fields
            field_mapping = {
                'first_name': candidate_data.get('first_name', ''),
                'last_name': candidate_data.get('last_name', ''),
                'email': candidate_data.get('email', ''),
                'phone': candidate_data.get('phone', ''),
                'linkedin': candidate_data.get('linkedin_url', ''),
                'website': candidate_data.get('portfolio_url', '')
            }
            
            for field_name, value in field_mapping.items():
                if not value:
                    continue
                
                selectors = self.field_selectors.get(field_name, [])
                filled = False
                
                for selector in selectors:
                    if await self.fill_field(driver, selector, value):
                        fields_filled.append(field_name)
                        filled = True
                        break
                
                if not filled:
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
                else:
                    fields_needs_review.append('cover_letter')
            
            # Handle custom questions
            await self._handle_custom_questions(driver, candidate_data, job_data, fields_needs_review)
            
            # Handle multi-step forms
            steps = await self.handle_multi_step_form(driver)
            if steps > 0:
                logger.info(f"Navigated through {steps} form steps")
            
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
                metadata={'steps_completed': steps}
            )
            
        except Exception as e:
            logger.error(f"Error filling Greenhouse form: {e}")
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
    
    async def _handle_custom_questions(self, driver: WebDriver, candidate_data: Dict[str, Any], 
                                      job_data: Dict[str, Any], fields_needs_review: List[str]):
        """Handle Greenhouse custom screening questions"""
        try:
            # Find custom question containers
            question_containers = driver.find_elements(By.CSS_SELECTOR, "div[class*='field']:has(label)")
            
            for container in question_containers:
                try:
                    label = container.find_element(By.TAG_NAME, "label").text.lower()
                    
                    # Common screening questions
                    if any(keyword in label for keyword in ['authorized', 'work', 'visa', 'sponsorship']):
                        # Work authorization questions
                        radio_yes = container.find_element(By.CSS_SELECTOR, "input[value='yes'], input[value='true']")
                        if radio_yes and not radio_yes.is_selected():
                            radio_yes.click()
                    
                    elif 'salary' in label or 'compensation' in label:
                        # Salary expectation
                        input_field = container.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                        if input_field:
                            salary = candidate_data.get('expected_salary', '')
                            if salary:
                                input_field.clear()
                                input_field.send_keys(str(salary))
                            else:
                                fields_needs_review.append('salary_expectation')
                    
                    elif 'start' in label and 'date' in label:
                        # Start date
                        date_input = container.find_element(By.CSS_SELECTOR, "input[type='date'], input[type='text']")
                        if date_input:
                            start_date = candidate_data.get('available_start_date', 'Immediately')
                            date_input.clear()
                            date_input.send_keys(start_date)
                    
                    elif 'years' in label and 'experience' in label:
                        # Years of experience
                        exp_input = container.find_element(By.CSS_SELECTOR, "input, select")
                        if exp_input:
                            years = str(candidate_data.get('years_experience', 0))
                            if exp_input.tag_name == 'select':
                                from selenium.webdriver.support.ui import Select
                                Select(exp_input).select_by_visible_text(years)
                            else:
                                exp_input.clear()
                                exp_input.send_keys(years)
                    
                    else:
                        # Unknown question - flag for review
                        fields_needs_review.append(f"custom_question_{label[:30]}")
                        
                except Exception as e:
                    logger.debug(f"Error handling custom question: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error handling Greenhouse custom questions: {e}")
