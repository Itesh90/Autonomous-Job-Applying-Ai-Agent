"""
Adapter registry for managing and selecting platform adapters
"""
from typing import Dict, List, Optional, Type
import asyncio
from selenium.webdriver.remote.webdriver import WebDriver

from .base_adapter import BaseAdapter, AdapterResult
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .workable import WorkableAdapter
from .generic_ai import GenericAIAdapter
from utils.logger import get_logger
from models.database import get_session, PlatformMetrics

logger = get_logger(__name__)

class AdapterRegistry:
    """Registry for managing platform adapters"""
    
    def __init__(self):
        self.adapters: Dict[str, Type[BaseAdapter]] = {}
        self.adapter_instances: Dict[str, BaseAdapter] = {}
        self.platform_metrics: Dict[str, Dict] = {}
        self._register_default_adapters()
    
    def _register_default_adapters(self):
        """Register all default platform adapters"""
        self.register_adapter("greenhouse", GreenhouseAdapter, priority=1)
        self.register_adapter("lever", LeverAdapter, priority=2)
        self.register_adapter("workable", WorkableAdapter, priority=3)
        self.register_adapter("generic", GenericAIAdapter, priority=99)  # Lowest priority fallback
        
        logger.info(f"Registered {len(self.adapters)} platform adapters")
    
    def register_adapter(self, name: str, adapter_class: Type[BaseAdapter], priority: int = 10):
        """Register a new adapter"""
        self.adapters[name] = {
            'class': adapter_class,
            'priority': priority,
            'enabled': True
        }
        logger.info(f"Registered adapter: {name} with priority {priority}")
    
    def get_adapter(self, name: str) -> Optional[BaseAdapter]:
        """Get adapter instance by name"""
        if name not in self.adapter_instances:
            if name in self.adapters and self.adapters[name]['enabled']:
                adapter_class = self.adapters[name]['class']
                self.adapter_instances[name] = adapter_class()
        
        return self.adapter_instances.get(name)
    
    async def detect_platform(self, driver: WebDriver, url: str) -> Optional[str]:
        """Detect which platform the current page belongs to"""
        # Sort adapters by priority
        sorted_adapters = sorted(
            self.adapters.items(),
            key=lambda x: x[1]['priority']
        )
        
        for adapter_name, adapter_info in sorted_adapters:
            if not adapter_info['enabled']:
                continue
            
            # Skip generic adapter in detection phase
            if adapter_name == 'generic':
                continue
            
            try:
                adapter = self.get_adapter(adapter_name)
                if adapter and await adapter.detect_platform(driver, url):
                    logger.info(f"Platform detected: {adapter_name}")
                    self._record_detection(adapter_name, url)
                    return adapter_name
            except Exception as e:
                logger.error(f"Error detecting platform with {adapter_name}: {e}")
                continue
        
        logger.info("No specific platform detected, will use generic AI adapter")
        return 'generic'  # Fallback to generic AI adapter
    
    async def fill_application(self, driver: WebDriver, url: str, 
                              candidate_data: Dict, job_data: Dict) -> AdapterResult:
        """Fill application form with automatic platform detection"""
        
        # Detect platform
        platform = await self.detect_platform(driver, url)
        
        if not platform:
            return AdapterResult(
                success=False,
                platform="unknown",
                fields_filled=[],
                fields_failed=[],
                fields_needs_review=[],
                screenshots=[],
                confidence_score=0.0,
                error_message="Could not detect platform or adapter"
            )
        
        # Get appropriate adapter
        adapter = self.get_adapter(platform)
        
        if not adapter:
            return AdapterResult(
                success=False,
                platform=platform,
                fields_filled=[],
                fields_failed=[],
                fields_needs_review=[],
                screenshots=[],
                confidence_score=0.0,
                error_message=f"No adapter available for platform: {platform}"
            )
        
        # Fill form using adapter
        logger.info(f"Using {platform} adapter to fill application form")
        
        try:
            result = await adapter.fill_form(driver, candidate_data, job_data)
            
            # Record metrics
            self._record_application_result(platform, result)
            
            # If primary adapter fails with low confidence, try generic AI adapter
            if not result.success and result.confidence_score < 0.5 and platform != 'generic':
                logger.info(f"{platform} adapter failed with low confidence, trying generic AI adapter")
                generic_adapter = self.get_adapter('generic')
                if generic_adapter:
                    generic_result = await generic_adapter.fill_form(driver, candidate_data, job_data)
                    if generic_result.confidence_score > result.confidence_score:
                        logger.info("Generic AI adapter performed better, using its results")
                        self._record_application_result('generic', generic_result)
                        return generic_result
            
            return result
            
        except Exception as e:
            logger.error(f"Error filling form with {platform} adapter: {e}")
            
            # Try fallback to generic adapter
            if platform != 'generic':
                logger.info("Attempting fallback to generic AI adapter")
                generic_adapter = self.get_adapter('generic')
                if generic_adapter:
                    try:
                        return await generic_adapter.fill_form(driver, candidate_data, job_data)
                    except Exception as fallback_error:
                        logger.error(f"Generic adapter also failed: {fallback_error}")
            
            return AdapterResult(
                success=False,
                platform=platform,
                fields_filled=[],
                fields_failed=[],
                fields_needs_review=[],
                screenshots=[],
                confidence_score=0.0,
                error_message=str(e)
            )
    
    def _record_detection(self, platform: str, url: str):
        """Record platform detection for metrics"""
        if platform not in self.platform_metrics:
            self.platform_metrics[platform] = {
                'detections': 0,
                'successful_applications': 0,
                'failed_applications': 0,
                'total_confidence': 0.0,
                'urls': []
            }
        
        self.platform_metrics[platform]['detections'] += 1
        if url not in self.platform_metrics[platform]['urls']:
            self.platform_metrics[platform]['urls'].append(url)
    
    def _record_application_result(self, platform: str, result: AdapterResult):
        """Record application result for metrics"""
        if platform not in self.platform_metrics:
            self.platform_metrics[platform] = {
                'detections': 0,
                'successful_applications': 0,
                'failed_applications': 0,
                'total_confidence': 0.0,
                'urls': []
            }
        
        if result.success:
            self.platform_metrics[platform]['successful_applications'] += 1
        else:
            self.platform_metrics[platform]['failed_applications'] += 1
        
        self.platform_metrics[platform]['total_confidence'] += result.confidence_score
        
        # Save to database
        try:
            session = get_session()
            metric = PlatformMetrics(
                platform=platform,
                success=result.success,
                confidence_score=result.confidence_score,
                fields_filled=len(result.fields_filled),
                fields_failed=len(result.fields_failed),
                fields_needs_review=len(result.fields_needs_review),
                captcha_detected=result.captcha_detected
            )
            session.add(metric)
            session.commit()
            session.close()
        except Exception as e:
            logger.error(f"Error saving platform metrics: {e}")
    
    def get_platform_stats(self, platform: str = None) -> Dict:
        """Get statistics for platform(s)"""
        if platform:
            return self.platform_metrics.get(platform, {})
        return self.platform_metrics
    
    def get_best_adapter_for_url(self, url: str) -> Optional[str]:
        """Get the best performing adapter for a specific URL pattern"""
        # Check if we've seen this URL before
        for platform, metrics in self.platform_metrics.items():
            if any(url.startswith(known_url) for known_url in metrics.get('urls', [])):
                # Calculate success rate
                total_apps = metrics['successful_applications'] + metrics['failed_applications']
                if total_apps > 0:
                    success_rate = metrics['successful_applications'] / total_apps
                    avg_confidence = metrics['total_confidence'] / total_apps
                    
                    # Return if good performance
                    if success_rate > 0.7 and avg_confidence > 0.7:
                        logger.info(f"Using {platform} adapter based on past performance for URL pattern")
                        return platform
        
        return None
    
    def disable_adapter(self, name: str):
        """Disable an adapter"""
        if name in self.adapters:
            self.adapters[name]['enabled'] = False
            logger.info(f"Disabled adapter: {name}")
    
    def enable_adapter(self, name: str):
        """Enable an adapter"""
        if name in self.adapters:
            self.adapters[name]['enabled'] = True
            logger.info(f"Enabled adapter: {name}")
    
    def list_adapters(self) -> List[Dict]:
        """List all registered adapters with their status"""
        adapter_list = []
        for name, info in self.adapters.items():
            metrics = self.platform_metrics.get(name, {})
            total_apps = metrics.get('successful_applications', 0) + metrics.get('failed_applications', 0)
            
            adapter_info = {
                'name': name,
                'priority': info['priority'],
                'enabled': info['enabled'],
                'detections': metrics.get('detections', 0),
                'successful_applications': metrics.get('successful_applications', 0),
                'failed_applications': metrics.get('failed_applications', 0),
                'success_rate': metrics.get('successful_applications', 0) / total_apps if total_apps > 0 else 0,
                'avg_confidence': metrics.get('total_confidence', 0) / total_apps if total_apps > 0 else 0
            }
            adapter_list.append(adapter_info)
        
        return sorted(adapter_list, key=lambda x: x['priority'])

# Global registry instance
adapter_registry = AdapterRegistry()
