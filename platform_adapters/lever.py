"""
Lever ATS platform adapter
"""
import asyncio
from typing import Dict, Any, List
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .base_adapter import BaseAdapter, AdapterResult
from utils.logger import get_logger

logger = get_logger(__name__)

class LeverAdapter(BaseAdapter):
    """Adapter for Lever ATS platform"""
    
    def __init__(self):
        super().__init__()
        self.platform_name = "Lever"
        
        # Lever-specific selectors
        self.field_selectors = {
            'name': [
                "input[name='name']",
                "input[name='fullname']",
                "input[placeholder*='Full name']",
                "input[placeholder*='Name']"
            ],
            'email': [
                "input[name='email']",
                "input[type='email']",
                "input[placeholder*='Email']"
            ],
            'phone': [
                "input[name='phone']",
                "input[type='tel']",
                "input[placeholder*='Phone']"
            ],
            'resume': [
                "input[name='resume']",
                "input[type='file']",
                "input[accept*='.pdf']"
            ],
            'cover_letter': [
                "textarea[name='comments']",
                "textarea[name='cover_letter']",
                "textarea[placeholder*='cover']",
                "textarea[placeholder*='message']"
            ],
            'linkedin': [
                "input[name='urls[LinkedIn]']",
                "input[placeholder*='linkedin']",
                "input[name='linkedin']"
            ],
            'website': [
                "input[name='urls[Website]']",
                "input[name='urls[Portfolio]']",
                "input[placeholder*='website']",
                "input[placeholder*='portfolio']"
            ],
            'github': [
                "input[name='urls[GitHub]']",
                "input[placeholder*='github']"
            ]
        }
    
    async def detect_platform(self, driver: WebDriver, url: str) -> bool:
        """Detect if current page is Lever"""
        try:
            # Check URL
            if 'lever.co' in url or 'jobs.lever' in url:
                return True
            
            # Check page elements
            lever_indicators = [
                "div[class*='lever']",
                "form[action*='lever']",
                "script[src*='lever']",
                "meta[content*='Lever']",
                "div.application-form",
                "div[data-qa='application-form']"
            ]
            
            for indicator in lever_indicators:
                elements = driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements:
                    logger.info(f"Lever platform detected via: {indicator}")
                    return True
            
            # Check for Lever-specific form structure
            form_elements = driver.find_elements(By.CSS_SELECTOR, "input[name='urls[LinkedIn]'], input[name='urls[Website]']")
            if form_elements:
                logger.info("Lever platform detected via URL fields structure")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting Lever platform: {e}")
            return False
    
    async def get_form_fields(self, driver: WebDriver) -> Dict[str, Any]:
        """Extract form fields from Lever page"""
        fields = {}
        
        try:
            # Wait for form to load (Lever often uses dynamic loading)
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "form, .application-form"))
                )
                await asyncio.sleep(2)  # Additional wait for AJAX content
            except TimeoutException:
                logger.warning("Timeout waiting for Lever form to load")
            
            # Find all input fields
            inputs = driver.find_elements(By.CSS_SELECTOR, "input, textarea, select")
            
            for element in inputs:
                field_info = await self.extract_field_info(driver, element)
                if field_info.get('name') or field_info.get('id'):
                    field_key = field_info.get('name') or field_info.get('id')
                    fields[field_key] = field_info
            
            # Look for custom fields in Lever's structure
            field_groups = driver.find_elements(By.CSS_SELECTOR, "div[class*='field'], .postings-group")
            for group in field_groups:
                try:
                    label_elem = group.find_element(By.CSS_SELECTOR, "label, .posting-field-label")
                    label = label_elem.text
                    input_element = group.find_element(By.CSS_SELECTOR, "input, textarea, select")
                    field_info = await self.extract_field_info(driver, input_element)
                    field_info['label'] = label
                    fields[f"field_{len(fields)}"] = field_info
                except:
                    continue
            
            logger.info(f"Found {len(fields)} form fields on Lever page")
            
        except Exception as e:
            logger.error(f"Error extracting Lever form fields: {e}")
        
        return fields
    
    async def fill_form(self, driver: WebDriver, candidate_data: Dict[str, Any], job_data: Dict[str, Any]) -> AdapterResult:
        """Fill Lever application form"""
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
            
            # Lever often combines first and last name
            full_name = f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip()
            
            # Fill basic fields
            field_mapping = {
                'name': full_name,
                'email': candidate_data.get('email', ''),
                'phone': candidate_data.get('phone', ''),
                'linkedin': candidate_data.get('linkedin_url', ''),
                'website': candidate_data.get('portfolio_url', ''),
                'github': candidate_data.get('github_url', '')
            }
            
            for field_name, value in field_mapping.items():
                if not value:
                    continue
                
                selectors = self.field_selectors.get(field_name, [])
                filled = False
                
                for selector in selectors:
                    if await self.fill_field_with_retry(driver, selector, value):
                        fields_filled.append(field_name)
                        filled = True
                        break
                
                if not filled and field_name in ['name', 'email']:  # Critical fields
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
            
            # Handle cover letter / additional information
            cover_letter = job_data.get('generated_cover_letter', '')
            if cover_letter:
                cl_selectors = self.field_selectors.get('cover_letter', [])
                for selector in cl_selectors:
                    if await self.fill_field(driver, selector, cover_letter, 'textarea'):
                        fields_filled.append('cover_letter')
                        break
            
            # Handle Lever's dropdown fields
            await self._handle_lever_dropdowns(driver, candidate_data, fields_filled, fields_needs_review)
            
            # Handle custom questions
            await self._handle_custom_questions(driver, candidate_data, job_data, fields_needs_review)
            
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
                confidence_score=confidence
            )
            
        except Exception as e:
            logger.error(f"Error filling Lever form: {e}")
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
    
    async def fill_field_with_retry(self, driver: WebDriver, selector: str, value: str, max_retries: int = 3) -> bool:
        """Fill field with retry logic for dynamic content"""
        for attempt in range(max_retries):
            try:
                # Wait for element to be present
                element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                # Scroll to element
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                await asyncio.sleep(0.5)
                
                # Clear and fill
                element.clear()
                element.send_keys(value)
                return True
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.debug(f"Failed to fill field {selector} after {max_retries} attempts: {e}")
                else:
                    await asyncio.sleep(1)  # Wait before retry
                    
        return False
    
    async def _handle_lever_dropdowns(self, driver: WebDriver, candidate_data: Dict[str, Any], 
                                     fields_filled: List[str], fields_needs_review: List[str]):
        """Handle Lever's custom dropdown components"""
        try:
            # Look for custom dropdowns (Lever often uses div-based dropdowns)
            dropdowns = driver.find_elements(By.CSS_SELECTOR, "div[role='button'][aria-haspopup='listbox'], select")
            
            for dropdown in dropdowns:
                try:
                    # Get dropdown label
                    dropdown_label = dropdown.get_attribute('aria-label') or ''
                    
                    if not dropdown_label:
                        # Try to find associated label
                        parent = dropdown.find_element(By.XPATH, "..")
                        label_elem = parent.find_element(By.CSS_SELECTOR, "label, .label")
                        dropdown_label = label_elem.text if label_elem else ''
                    
                    dropdown_label = dropdown_label.lower()
                    
                    # Handle common dropdown fields
                    if 'hear' in dropdown_label or 'source' in dropdown_label:
                        # "How did you hear about us" field
                        if dropdown.tag_name == 'select':
                            Select(dropdown).select_by_index(1)  # Select first real option
                        else:
                            dropdown.click()
                            await asyncio.sleep(0.5)
                            # Select first option or "Other"
                            options = driver.find_elements(By.CSS_SELECTOR, "li[role='option']")
                            if options:
                                for opt in options:
                                    if 'other' in opt.text.lower():
                                        opt.click()
                                        break
                                else:
                                    options[0].click()
                        fields_filled.append('referral_source')
                        
                    elif 'location' in dropdown_label or 'office' in dropdown_label:
                        # Location preference
                        preferred_location = candidate_data.get('preferred_location', 'Remote')
                        if dropdown.tag_name == 'select':
                            try:
                                Select(dropdown).select_by_visible_text(preferred_location)
                            except:
                                Select(dropdown).select_by_index(1)
                        fields_filled.append('location_preference')
                        
                    else:
                        fields_needs_review.append(f"dropdown_{dropdown_label[:30]}")
                        
                except Exception as e:
                    logger.debug(f"Error handling dropdown: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error handling Lever dropdowns: {e}")
    
    async def _handle_custom_questions(self, driver: WebDriver, candidate_data: Dict[str, Any],
                                      job_data: Dict[str, Any], fields_needs_review: List[str]):
        """Handle Lever custom questions"""
        try:
            # Find question containers
            question_containers = driver.find_elements(By.CSS_SELECTOR, ".posting-question, div[class*='question']")
            
            for container in question_containers:
                try:
                    # Get question text
                    question_text = container.text.lower()
                    
                    # Handle common questions
                    if any(keyword in question_text for keyword in ['visa', 'authorized', 'sponsorship']):
                        # Work authorization
                        inputs = container.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                        for inp in inputs:
                            if 'yes' in inp.get_attribute('value').lower():
                                if not inp.is_selected():
                                    inp.click()
                                break
                    
                    elif 'experience' in question_text and ('years' in question_text or 'year' in question_text):
                        # Years of experience
                        text_input = container.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                        text_input.clear()
                        text_input.send_keys(str(candidate_data.get('years_experience', 0)))
                    
                    else:
                        fields_needs_review.append(f"question_{question_text[:30]}")
                        
                except Exception as e:
                    logger.debug(f"Error handling custom question: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error handling Lever custom questions: {e}")
