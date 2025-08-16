# automation/captcha_detector.py
import re
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CaptchaDetectionResult:
    detected: bool
    captcha_type: Optional[str] = None
    confidence: float = 0.0
    selectors: list = None
    description: str = ""

class CaptchaDetector:
    """Detect CAPTCHA challenges on web pages"""
    
    def __init__(self):
        # Common CAPTCHA indicators
        self.captcha_indicators = {
            'recaptcha': [
                'div[class*="recaptcha"]',
                'div[class*="g-recaptcha"]',
                'iframe[src*="recaptcha"]',
                'script[src*="recaptcha"]',
                'data-sitekey',
                'g-recaptcha-response'
            ],
            'hcaptcha': [
                'div[class*="h-captcha"]',
                'iframe[src*="hcaptcha"]',
                'script[src*="hcaptcha"]',
                'data-sitekey',
                'h-captcha-response'
            ],
            'turnstile': [
                'div[class*="cf-turnstile"]',
                'iframe[src*="turnstile"]',
                'script[src*="turnstile"]',
                'data-sitekey'
            ],
            'image_captcha': [
                'img[src*="captcha"]',
                'input[name*="captcha"]',
                'div[class*="captcha"]',
                'span[class*="captcha"]'
            ],
            'text_captcha': [
                'input[name*="captcha"]',
                'div[class*="captcha"]',
                'span[class*="captcha"]',
                'label[for*="captcha"]'
            ]
        }
        
        # Text patterns that indicate CAPTCHA
        self.captcha_text_patterns = [
            r'captcha',
            r'verify.*human',
            r'prove.*robot',
            r'security.*check',
            r'human.*verification',
            r'robot.*check',
            r'please.*verify',
            r'enter.*code',
            r'type.*characters'
        ]
    
    async def detect_captcha(self, page) -> CaptchaDetectionResult:
        """Detect CAPTCHA on the current page"""
        try:
            # Get page content
            content = await page.content()
            url = await page.url()
            
            # Check for CAPTCHA indicators
            detected_types = []
            confidence_scores = []
            
            for captcha_type, selectors in self.captcha_indicators.items():
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            detected_types.append(captcha_type)
                            confidence_scores.append(0.9)  # High confidence for selector match
                            break
                    except Exception as e:
                        logger.debug(f"Error checking selector {selector}: {e}")
                        continue
            
            # Check for text patterns
            text_confidence = self._check_text_patterns(content)
            if text_confidence > 0.5:
                detected_types.append('text_captcha')
                confidence_scores.append(text_confidence)
            
            # Check URL for CAPTCHA indicators
            url_confidence = self._check_url_patterns(url)
            if url_confidence > 0.5:
                detected_types.append('url_captcha')
                confidence_scores.append(url_confidence)
            
            if detected_types:
                # Get the highest confidence type
                max_confidence_idx = confidence_scores.index(max(confidence_scores))
                captcha_type = detected_types[max_confidence_idx]
                confidence = confidence_scores[max_confidence_idx]
                
                return CaptchaDetectionResult(
                    detected=True,
                    captcha_type=captcha_type,
                    confidence=confidence,
                    selectors=self.captcha_indicators.get(captcha_type, []),
                    description=f"Detected {captcha_type} CAPTCHA with {confidence:.2f} confidence"
                )
            
            return CaptchaDetectionResult(detected=False)
            
        except Exception as e:
            logger.error(f"Error detecting CAPTCHA: {e}")
            return CaptchaDetectionResult(detected=False)
    
    def _check_text_patterns(self, content: str) -> float:
        """Check for CAPTCHA-related text patterns"""
        content_lower = content.lower()
        matches = 0
        
        for pattern in self.captcha_text_patterns:
            if re.search(pattern, content_lower):
                matches += 1
        
        # Return confidence based on number of matches
        if matches == 0:
            return 0.0
        elif matches == 1:
            return 0.3
        elif matches == 2:
            return 0.6
        else:
            return 0.8
    
    def _check_url_patterns(self, url: str) -> float:
        """Check URL for CAPTCHA indicators"""
        url_lower = url.lower()
        
        if 'captcha' in url_lower:
            return 0.7
        elif 'verify' in url_lower:
            return 0.5
        elif 'security' in url_lower:
            return 0.3
        
        return 0.0
    
    def calculate_confidence(self, indicators: list) -> float:
        """Calculate confidence score based on indicators"""
        if not indicators:
            return 0.0
        
        # Weight different types of indicators
        weights = {
            'recaptcha': 0.9,
            'hcaptcha': 0.9,
            'turnstile': 0.9,
            'image_captcha': 0.8,
            'text_captcha': 0.6,
            'url_captcha': 0.5
        }
        
        total_weight = 0
        for indicator in indicators:
            weight = weights.get(indicator, 0.5)
            total_weight += weight
        
        return min(total_weight / len(indicators), 1.0)
    
    async def wait_for_captcha_solution(self, page, timeout: int = 300) -> bool:
        """Wait for CAPTCHA to be solved (for manual intervention)"""
        try:
            # Wait for CAPTCHA to be completed
            # This would need to be customized based on the specific CAPTCHA type
            await page.wait_for_function(
                '() => { return !document.querySelector("[class*=\\"recaptcha\\"]") || document.querySelector("[class*=\\"recaptcha\\"]").style.display === "none"; }',
                timeout=timeout * 1000
            )
            return True
        except Exception as e:
            logger.error(f"Error waiting for CAPTCHA solution: {e}")
            return False

# Global CAPTCHA detector instance
captcha_detector = CaptchaDetector()
