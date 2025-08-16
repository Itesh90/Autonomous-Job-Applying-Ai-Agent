"""
Multi-provider LLM system with caching, fallback, and RAG integration
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib
import json
import time
import asyncio
from datetime import datetime, timedelta
import tiktoken
from functools import lru_cache

import openai
import anthropic
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from langchain.llms import OpenAI, Anthropic, HuggingFacePipeline
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings
from langchain.cache import SQLiteCache
from langchain.memory import ConversationSummaryBufferMemory

from config.settings import settings
from models.database import APIKey, get_session
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    provider: str
    model: str
    tokens_used: int
    cost: float
    cached: bool = False
    confidence: float = 1.0
    metadata: Dict[str, Any] = None

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        self.api_key = api_key
        self.model = model
        self.config = kwargs
        self.total_tokens = 0
        self.total_cost = 0.0
        
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate response from prompt"""
        pass
    
    @abstractmethod
    async def generate_structured(self, prompt: str, schema: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Generate structured JSON response"""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        pass
    
    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate API connection"""
        pass
    
    def calculate_cost(self, tokens: int) -> float:
        """Calculate cost for token usage"""
        # Default pricing per 1K tokens
        pricing = {
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.002,
            "claude-3": 0.025,
            "claude-2": 0.008,
            "llama": 0.0  # Free for local models
        }
        
        for model_prefix, price in pricing.items():
            if model_prefix in self.model.lower():
                return (tokens / 1000) * price
        return 0.0

class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider"""
    
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview", **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.encoding = tiktoken.encoding_for_model(model if "gpt" in model else "gpt-4")
        
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate response using OpenAI"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.0),
                max_tokens=kwargs.get("max_tokens", 2000),
                response_format={"type": kwargs.get("response_format", "text")}
            )
            
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens
            cost = self.calculate_cost(tokens)
            
            self.total_tokens += tokens
            self.total_cost += cost
            
            return LLMResponse(
                content=content,
                provider="openai",
                model=self.model,
                tokens_used=tokens,
                cost=cost,
                metadata={"finish_reason": response.choices[0].finish_reason}
            )
            
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise
    
    async def generate_structured(self, prompt: str, schema: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Generate structured JSON response"""
        system_prompt = f"""
        You must respond with valid JSON that matches this schema:
        {json.dumps(schema, indent=2)}
        
        Response must be parseable JSON only, no additional text.
        """
        
        response = await self.generate(
            f"{system_prompt}\n\n{prompt}",
            response_format="json_object",
            **kwargs
        )
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response.content}")
            raise ValueError("Invalid JSON response from model")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken"""
        return len(self.encoding.encode(text))
    
    def validate_connection(self) -> bool:
        """Validate OpenAI API connection"""
        try:
            # Synchronous test call
            client = openai.OpenAI(api_key=self.api_key)
            client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenAI connection validation failed: {e}")
            return False

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider"""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229", **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate response using Claude"""
        try:
            response = await self.client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", 2000),
                temperature=kwargs.get("temperature", 0.0)
            )
            
            content = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            cost = self.calculate_cost(tokens)
            
            self.total_tokens += tokens
            self.total_cost += cost
            
            return LLMResponse(
                content=content,
                provider="anthropic",
                model=self.model,
                tokens_used=tokens,
                cost=cost,
                metadata={"stop_reason": response.stop_reason}
            )
            
        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            raise
    
    async def generate_structured(self, prompt: str, schema: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Generate structured JSON response"""
        system_prompt = f"""
        You are a helpful assistant that always responds with valid JSON.
        The JSON must match this schema exactly:
        {json.dumps(schema, indent=2)}
        
        Respond only with the JSON object, no additional text or markdown.
        """
        
        response = await self.generate(f"{system_prompt}\n\n{prompt}", **kwargs)
        
        try:
            # Clean potential markdown formatting
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response.content}")
            raise ValueError("Invalid JSON response from model")
    
    def count_tokens(self, text: str) -> int:
        """Estimate token count for Claude"""
        # Rough estimation: 1 token ≈ 4 characters
        return len(text) // 4
    
    def validate_connection(self) -> bool:
        """Validate Anthropic API connection"""
        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            # Test with minimal request
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"Anthropic connection validation failed: {e}")
            return False

class LocalLLMProvider(BaseLLMProvider):
    """Local Hugging Face model provider"""
    
    def __init__(self, model_name: str = "microsoft/phi-2", **kwargs):
        super().__init__(api_key="", model=model_name, **kwargs)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map="auto"
        )
        
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate response using local model"""
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=kwargs.get("max_tokens", 500),
                    temperature=kwargs.get("temperature", 0.7),
                    do_sample=kwargs.get("temperature", 0.7) > 0
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Remove the prompt from response
            content = response[len(prompt):].strip()
            
            tokens = len(outputs[0])
            
            return LLMResponse(
                content=content,
                provider="local",
                model=self.model_name,
                tokens_used=tokens,
                cost=0.0,  # Local models are free
                metadata={"device": self.device}
            )
            
        except Exception as e:
            logger.error(f"Local LLM generation failed: {e}")
            raise
    
    async def generate_structured(self, prompt: str, schema: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Generate structured JSON response"""
        json_prompt = f"""
        Task: Generate a JSON object matching this schema:
        {json.dumps(schema, indent=2)}
        
        Instructions: Respond ONLY with valid JSON, no other text.
        
        Query: {prompt}
        
        JSON Response:
        """
        
        response = await self.generate(json_prompt, **kwargs)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from local model: {response.content}")
            raise ValueError("Invalid JSON response from local model")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using tokenizer"""
        return len(self.tokenizer.encode(text))
    
    def validate_connection(self) -> bool:
        """Validate local model is loaded"""
        return self.model is not None

class LLMProviderManager:
    """Manages multiple LLM providers with fallback and caching"""
    
    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
        self.cache = {}  # Simple in-memory cache
        self.session = get_session()
        self._initialize_providers()
        
    def _initialize_providers(self):
        """Initialize available providers from settings"""
        # OpenAI
        if settings.openai_api_key:
            self.providers["openai"] = OpenAIProvider(
                api_key=settings.openai_api_key,
                model="gpt-4-turbo-preview"
            )
            
        # Anthropic
        if settings.anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model="claude-3-opus-20240229"
            )
            
        # Local model as fallback
        try:
            self.providers["local"] = LocalLLMProvider(
                model_name="microsoft/phi-2"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize local model: {e}")
    
    def _get_cache_key(self, prompt: str, provider: str, **kwargs) -> str:
        """Generate cache key for prompt"""
        cache_data = {
            "prompt": prompt,
            "provider": provider,
            "temperature": kwargs.get("temperature", 0.0),
            "max_tokens": kwargs.get("max_tokens", 2000)
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()
    
    async def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        use_cache: bool = True,
        fallback: bool = True,
        **kwargs
    ) -> LLMResponse:
        """Generate response with caching and fallback"""
        
        # Check cache if temperature is 0 (deterministic)
        if use_cache and kwargs.get("temperature", 0.0) == 0.0:
            cache_key = self._get_cache_key(prompt, provider or "any", **kwargs)
            if cache_key in self.cache:
                cached_response = self.cache[cache_key]
                cached_response.cached = True
                logger.info(f"Using cached response for prompt (key: {cache_key[:8]}...)")
                return cached_response
        
        # Determine provider order
        if provider and provider in self.providers:
            provider_order = [provider]
        else:
            # Default fallback order
            provider_order = ["openai", "anthropic", "local"]
        
        # Try providers in order
        last_error = None
        for provider_name in provider_order:
            if provider_name not in self.providers:
                continue
                
            try:
                logger.info(f"Attempting generation with {provider_name}")
                provider_instance = self.providers[provider_name]
                response = await provider_instance.generate(prompt, **kwargs)
                
                # Cache if deterministic
                if use_cache and kwargs.get("temperature", 0.0) == 0.0:
                    cache_key = self._get_cache_key(prompt, provider_name, **kwargs)
                    self.cache[cache_key] = response
                
                # Log usage
                self._log_usage(provider_name, response)
                
                return response
                
            except Exception as e:
                logger.error(f"Provider {provider_name} failed: {e}")
                last_error = e
                
                if not fallback:
                    raise
                    
                continue
        
        # All providers failed
        raise Exception(f"All LLM providers failed. Last error: {last_error}")
    
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        provider: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        
        # Force temperature=0 for structured output
        kwargs["temperature"] = 0.0
        
        provider_order = [provider] if provider else ["openai", "anthropic"]
        
        for provider_name in provider_order:
            if provider_name not in self.providers:
                continue
                
            try:
                provider_instance = self.providers[provider_name]
                result = await provider_instance.generate_structured(prompt, schema, **kwargs)
                
                # Validate against schema
                self._validate_schema(result, schema)
                
                return result
                
            except Exception as e:
                logger.error(f"Structured generation with {provider_name} failed: {e}")
                continue
        
        raise Exception("Failed to generate valid structured output")
    
    def _validate_schema(self, data: Dict[str, Any], schema: Dict[str, Any]):
        """Basic schema validation"""
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
    
    def _log_usage(self, provider: str, response: LLMResponse):
        """Log API usage to database"""
        try:
            # Update API key usage
            api_key = self.session.query(APIKey).filter_by(
                provider_name=provider,
                is_active=True
            ).first()
            
            if api_key:
                api_key.usage_count += 1
                api_key.tokens_used_today += response.tokens_used
                api_key.total_cost_usd += response.cost
                api_key.last_used = datetime.utcnow()
                self.session.commit()
                
        except Exception as e:
            logger.error(f"Failed to log usage: {e}")
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        status = {}
        
        for name, provider in self.providers.items():
            status[name] = {
                "available": provider.validate_connection(),
                "model": provider.model,
                "total_tokens": provider.total_tokens,
                "total_cost": provider.total_cost
            }
        
        return status
    
    def clear_cache(self):
        """Clear response cache"""
        self.cache.clear()
        logger.info("LLM response cache cleared")

# Global instance
llm_manager = LLMProviderManager()

# Export main interface
async def generate_llm_response(prompt: str, **kwargs) -> str:
    """Simple interface for LLM generation"""
    response = await llm_manager.generate(prompt, **kwargs)
    return response.content

async def generate_structured_response(prompt: str, schema: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Simple interface for structured generation"""
    return await llm_manager.generate_structured(prompt, schema, **kwargs)
