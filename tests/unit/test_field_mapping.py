# tests/unit/test_field_mapping.py
import pytest
import json
from platform_adapters.generic_mapper import GenericMapper
from llm.prompts.field_mapping import validate_mapping_response

class TestFieldMapping:
    
    @pytest.fixture
    def sample_form_fields(self):
        return {
            'input[name="first_name"]': {'type': 'text', 'required': True, 'label': 'First Name'},
            'input[name="email"]': {'type': 'email', 'required': True, 'label': 'Email Address'},
            'select[name="experience"]': {'type': 'select', 'options': ['0-2', '3-5', '6-10', '10+']},
            'textarea[name="cover_letter"]': {'type': 'textarea', 'label': 'Cover Letter'}
        }
    
    @pytest.fixture
    def sample_candidate_data(self):
        return {
            'first_name': 'John',
            'last_name': 'Doe', 
            'email': 'john.doe@example.com',
            'phone': '+1234567890',
            'years_experience': '3-5',
            'skills': ['Python', 'JavaScript', 'React']
        }
    
    def test_valid_mapping_response_validation(self):
        """Test validation of valid mapping response"""
        valid_response = json.dumps({
            'field_mappings': {
                'input[name="first_name"]': 'John',
                'input[name="email"]': 'john.doe@example.com',
                'select[name="experience"]': '3-5'
            },
            'confidence_score': 0.95,
            'needs_review_count': 0,
            'unmappable_fields': []
        })
        
        result = validate_mapping_response(valid_response)
        assert result['confidence_score'] == 0.95
        assert len(result['field_mappings']) == 3
    
    def test_invalid_json_response_validation(self):
        """Test validation fails for invalid JSON"""
        invalid_response = "This is not valid JSON {incomplete"
        
        with pytest.raises(ValueError, match="Invalid JSON response"):
            validate_mapping_response(invalid_response)
    
    def test_missing_required_fields_validation(self):
        """Test validation fails for missing required fields"""
        incomplete_response = json.dumps({
            'field_mappings': {'input[name="email"]': 'test@test.com'}
            # Missing confidence_score and needs_review_count
        })
        
        with pytest.raises(ValueError, match="Missing required field"):
            validate_mapping_response(incomplete_response)
    
    def test_needs_review_flagging(self):
        """Test NEEDS_REVIEW flagging for ambiguous fields"""
        response_with_review = json.dumps({
            'field_mappings': {
                'input[name="first_name"]': 'John',
                'input[name="salary"]': 'NEEDS_REVIEW'  # Ambiguous field
            },
            'confidence_score': 0.7,
            'needs_review_count': 1,
            'unmappable_fields': ['input[name="salary"]']
        })
        
        result = validate_mapping_response(response_with_review)
        assert result['needs_review_count'] == 1
        assert 'input[name="salary"]' in result['unmappable_fields']

# tests/unit/test_platform_adapters.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from platform_adapters.greenhouse import GreenhouseAdapter
from platform_adapters.lever import LeverAdapter

class TestGreenhouseAdapter:
    
    @pytest.fixture
    def greenhouse_adapter(self):
        return GreenhouseAdapter()
    
    @pytest.fixture
    def mock_page(self):
        page = AsyncMock()
        page.url.return_value = "https://jobs.greenhouse.io/company/123"
        page.query_selector = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])
        return page
    
    @pytest.mark.asyncio
    async def test_greenhouse_platform_detection(self, greenhouse_adapter, mock_page):
        """Test Greenhouse platform detection"""
        result = await greenhouse_adapter.detect_platform(mock_page)
        assert result is True
    
    @pytest.mark.asyncio 
    async def test_greenhouse_form_filling(self, greenhouse_adapter, mock_page):
        """Test Greenhouse form filling"""
        # Mock form elements
        mock_element = AsyncMock()
        mock_page.query_selector.return_value = mock_element
        
        candidate_data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane.smith@example.com'
        }
        
        result = await greenhouse_adapter.fill_form(mock_page, candidate_data)
        
        assert 'success' in result
        assert 'failed' in result
        assert 'needs_review' in result
        
        # Verify form elements were interacted with
        assert mock_page.query_selector.called

class TestLeverAdapter:
    
    @pytest.fixture
    def lever_adapter(self):
        return LeverAdapter()
    
    @pytest.mark.asyncio
    async def test_lever_platform_detection(self, lever_adapter):
        """Test Lever platform detection"""
        mock_page = AsyncMock()
        mock_page.url.return_value = "https://jobs.lever.co/company"
        mock_page.content.return_value = "<html>Powered by Lever</html>"
        
        result = await lever_adapter.detect_platform(mock_page)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_lever_dynamic_loading_retry(self, lever_adapter):
        """Test Lever's retry logic for dynamic content"""
        mock_page = AsyncMock()
        
        # First attempt fails, second succeeds
        mock_element = AsyncMock()
        mock_page.query_selector.side_effect = [None, mock_element]
        mock_page.wait_for_selector = AsyncMock()
        
        candidate_data = {'name': 'Test User'}
        
        result = await lever_adapter.fill_form(mock_page, candidate_data)
        
        # Should have retried and succeeded
        assert mock_page.query_selector.call_count >= 2

# tests/unit/test_encryption.py
class TestEncryption:
   
   @pytest.fixture
   def encryption_manager(self):
       from models.encryption import EncryptionManager
       return EncryptionManager()
   
   def test_api_key_encryption_decryption(self, encryption_manager):
       """Test API key encryption and decryption"""
       original_key = "sk-test-api-key-12345"
       
       # Encrypt
       encrypted = encryption_manager.encrypt(original_key)
       assert encrypted != original_key
       assert len(encrypted) > len(original_key)
       
       # Decrypt
       decrypted = encryption_manager.decrypt(encrypted)
       assert decrypted == original_key
   
   def test_pii_field_encryption(self, encryption_manager):
       """Test PII field encryption"""
       pii_data = {
           'email': 'john.doe@example.com',
           'phone': '+1234567890',
           'address': '123 Main St, City, State'
       }
       
       encrypted_data = encryption_manager.encrypt_sensitive_data(pii_data)
       
       # Verify encryption
       for field in pii_data:
           assert encrypted_data[field] != pii_data[field]
       
       # Verify decryption
       decrypted_data = encryption_manager.decrypt_sensitive_data(encrypted_data)
       assert decrypted_data == pii_data
