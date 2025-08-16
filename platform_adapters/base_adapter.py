"""
Base adapter class for platform-specific form filling
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio
import json

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class AdapterResult:
    """Result from adapter operation"""
    success: bool
    platform: str
    fields_filled: List[str]
    fields_failed: List[str]
    fields_needs_review: List[str]
    screenshots: List[str]
    confidence_score: float
    error_message: Optional[str] = None
    captcha_detected: bool = False
    metadata: Dict[str, Any] = None

class BaseAdapter(ABC):
    """Base class for all platform adapters"""
    
    def __init__(self):
        self.platform_name = self.__class__.__name__.replace('Adapter', '')
        self.wait_timeout = 10
        self.field_selectors = {}
        self.confidence_threshold = 0.7
        
    @abstractmethod
    async def detect_platform(self, driver: WebDriver, url: str) -> bool:
        """Detect if current page is this platform"""
        pass
    
    @abstractmethod
    async def get_form_fields(self, driver: WebDriver) -> Dict[str, Any]:
        """Extract form fields from page"""
        pass
    
    @abstractmethod
    async def fill_form(self, driver: WebDriver, candidate_data: Dict[str, Any], job_data: Dict[str, Any]) -> AdapterResult:
        """Fill application form with candidate data"""
        pass
    
    async def handle_multi_step_form(self, driver: WebDriver) -> int:
        """Handle multi-step forms"""
        steps_completed = 0
        max_steps = 10
        
        while steps_completed < max_steps:
            # Look for next/continue buttons
            next_selectors = [
                "button[type='submit']:not([disabled])",
                "button:contains('Next')",
                "button:contains('Continue')",
                "input[type='submit'][value*='Next']",
                "a.next-button"
            ]
            
            next_button = None
            for selector in next_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed() and elements[0].is_enabled():
                        next_button = elements[0]
                        break
                except:
                    continue
            
            if not next_button:
                break
            
            # Click next and wait for page change
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                await asyncio.sleep(0.5)
                next_button.click()
                await asyncio.sleep(2)  # Wait for page transition
                steps_completed += 1
            except Exception as e:
                logger.warning(f"Error navigating multi-step form: {e}")
                break
        
        return steps_completed
    
    async def detect_captcha(self, driver: WebDriver) -> bool:
        """Detect CAPTCHA presence on page"""
        captcha_indicators = [
            "div[class*='recaptcha']",
            "iframe[src*='recaptcha']",
            "div[class*='captcha']",
            "div[id*='captcha']",
            "img[src*='captcha']",
            "div.h-captcha",
            "iframe[src*='hcaptcha']"
        ]
        
        for indicator in captcha_indicators:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements and any(el.is_displayed() for el in elements):
                    logger.warning(f"CAPTCHA detected: {indicator}")
                    return True
            except:
                continue
        
        return False
    
    async def fill_field(self, driver: WebDriver, selector: str, value: str, field_type: str = "text") -> bool:
        """Fill a single form field"""
        try:
            # Find element
            element = WebDriverWait(driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            
            # Scroll to element
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            await asyncio.sleep(0.3)
            
            # Clear and fill based on type
            if field_type in ["text", "email", "tel", "number"]:
                element.clear()
                element.send_keys(value)
            elif field_type == "select":
                from selenium.webdriver.support.ui import Select
                Select(element).select_by_visible_text(value)
            elif field_type == "radio" or field_type == "checkbox":
                if not element.is_selected():
                    element.click()
            elif field_type == "file":
                element.send_keys(value)
            elif field_type == "textarea":
                element.clear()
                element.send_keys(value)
            
            return True
            
        except TimeoutException:
            logger.warning(f"Timeout waiting for field: {selector}")
            return False
        except Exception as e:
            logger.error(f"Error filling field {selector}: {e}")
            return False
    
    async def extract_field_info(self, driver: WebDriver, element) -> Dict[str, Any]:
        """Extract information about a form field"""
        try:
            field_info = {
                'id': element.get_attribute('id'),
                'name': element.get_attribute('name'),
                'type': element.get_attribute('type') or element.tag_name,
                'placeholder': element.get_attribute('placeholder'),
                'required': element.get_attribute('required') is not None,
                'value': element.get_attribute('value'),
                'label': self._find_label_for_element(driver, element),
                'visible': element.is_displayed(),
                'enabled': element.is_enabled()
            }
            
            # Get options for select elements
            if element.tag_name == 'select':
                options = element.find_elements(By.TAG_NAME, 'option')
                field_info['options'] = [opt.text for opt in options]
            
            return field_info
            
        except Exception as e:
            logger.error(f"Error extracting field info: {e}")
            return {}
    
    def _find_label_for_element(self, driver: WebDriver, element) -> str:
        """Find label text for form element"""
        try:
            # Try to find label by 'for' attribute
            element_id = element.get_attribute('id')
            if element_id:
                labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{element_id}']")
                if labels:
                    return labels[0].text
            
            # Try to find parent label
            parent = element.find_element(By.XPATH, "..")
            if parent.tag_name == 'label':
                return parent.text
            
            # Try to find preceding label sibling
            try:
                sibling = element.find_element(By.XPATH, "./preceding-sibling::label[1]")
                return sibling.text
            except:
                pass
            
            # Try aria-label
            aria_label = element.get_attribute('aria-label')
            if aria_label:
                return aria_label
            
            return ""
            
        except Exception:
            return ""
    
    async def take_screenshot(self, driver: WebDriver, name: str) -> str:
        """Take screenshot of current page"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{settings.screenshots_dir}/{self.platform_name}_{name}_{timestamp}.png"
            driver.save_screenshot(str(filename))
            logger.info(f"Screenshot saved: {filename}")
            return str(filename)
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return ""
    
    def calculate_confidence(self, filled: int, failed: int, total: int) -> float:
        """Calculate confidence score for form filling"""
        if total == 0:
            return 0.0
        
        success_rate = filled / total
        failure_penalty = (failed / total) * 0.5
        
        confidence = success_rate - failure_penalty
        return max(0.0, min(1.0, confidence))
