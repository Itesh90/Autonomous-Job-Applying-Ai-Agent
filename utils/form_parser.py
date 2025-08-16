# utils/form_parser.py
import re
from typing import Dict, List, Any
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class FormFieldExtractor:
    """Extract form fields from HTML"""
    
    def __init__(self):
        self.field_patterns = {
            'text': ['input[type="text"]', 'input[type="email"]', 'input[type="tel"]', 'input[type="url"]'],
            'textarea': ['textarea'],
            'select': ['select'],
            'checkbox': ['input[type="checkbox"]'],
            'radio': ['input[type="radio"]'],
            'file': ['input[type="file"]'],
            'hidden': ['input[type="hidden"]']
        }
    
    def extract_fields(self, html_content: str) -> Dict[str, Dict[str, Any]]:
        """Extract form fields from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        fields = {}
        
        # Find all form elements
        forms = soup.find_all('form')
        
        for form in forms:
            form_fields = self._extract_form_fields(form)
            fields.update(form_fields)
        
        return fields
    
    def _extract_form_fields(self, form_element) -> Dict[str, Dict[str, Any]]:
        """Extract fields from a specific form element"""
        fields = {}
        
        # Extract input fields
        for field_type, selectors in self.field_patterns.items():
            for selector in selectors:
                elements = form_element.select(selector)
                
                for element in elements:
                    field_info = self._extract_field_info(element, field_type)
                    if field_info:
                        fields[field_info['selector']] = field_info
        
        return fields
    
    def _extract_field_info(self, element, field_type: str) -> Dict[str, Any]:
        """Extract information from a form field element"""
        try:
            # Generate unique selector
            selector = self._generate_selector(element)
            
            # Get field attributes
            field_info = {
                'selector': selector,
                'type': field_type,
                'name': element.get('name', ''),
                'id': element.get('id', ''),
                'placeholder': element.get('placeholder', ''),
                'required': element.get('required') is not None,
                'value': element.get('value', ''),
                'label': self._find_label(element),
                'options': self._extract_options(element) if field_type == 'select' else None
            }
            
            return field_info
            
        except Exception as e:
            logger.error(f"Error extracting field info: {e}")
            return None
    
    def _generate_selector(self, element) -> str:
        """Generate a unique CSS selector for an element"""
        # Try to use ID first
        if element.get('id'):
            return f"#{element['id']}"
        
        # Use name attribute
        if element.get('name'):
            return f"[name='{element['name']}']"
        
        # Generate a selector based on element type and attributes
        tag_name = element.name
        attributes = []
        
        for attr, value in element.attrs.items():
            if attr not in ['id', 'name'] and value:
                if isinstance(value, list):
                    value = value[0]
                attributes.append(f"[{attr}='{value}']")
        
        if attributes:
            return f"{tag_name}{''.join(attributes)}"
        
        # Fallback to a generic selector
        return f"{tag_name}[type='{element.get('type', '')}']"
    
    def _find_label(self, element) -> str:
        """Find the label associated with a form field"""
        # Check for explicit label association
        if element.get('id'):
            label = element.find_previous('label', attrs={'for': element['id']})
            if label:
                return label.get_text(strip=True)
        
        # Check for implicit label (label contains the input)
        parent_label = element.find_parent('label')
        if parent_label:
            return parent_label.get_text(strip=True)
        
        # Look for nearby label
        nearby_label = element.find_previous('label')
        if nearby_label:
            return nearby_label.get_text(strip=True)
        
        return ""
    
    def _extract_options(self, select_element) -> List[Dict[str, str]]:
        """Extract options from a select element"""
        options = []
        
        for option in select_element.find_all('option'):
            option_info = {
                'value': option.get('value', ''),
                'text': option.get_text(strip=True),
                'selected': option.get('selected') is not None
            }
            options.append(option_info)
        
        return options
    
    def validate_form_completeness(self, fields: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Validate form completeness and identify missing required fields"""
        validation_result = {
            'complete': True,
            'missing_required': [],
            'field_count': len(fields),
            'required_count': 0,
            'optional_count': 0
        }
        
        for field_id, field_info in fields.items():
            if field_info.get('required', False):
                validation_result['required_count'] += 1
                
                # Check if required field has a value
                if not field_info.get('value') and not field_info.get('placeholder'):
                    validation_result['missing_required'].append({
                        'field_id': field_id,
                        'name': field_info.get('name', ''),
                        'label': field_info.get('label', ''),
                        'type': field_info.get('type', '')
                    })
            else:
                validation_result['optional_count'] += 1
        
        validation_result['complete'] = len(validation_result['missing_required']) == 0
        
        return validation_result

# Global form field extractor instance
form_extractor = FormFieldExtractor()
