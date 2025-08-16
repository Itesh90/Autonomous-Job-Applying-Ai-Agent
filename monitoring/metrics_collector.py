# monitoring/metrics_collector.py
import time
import psutil
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime, timedelta
import json

from models.database import get_session, Application, Job, Candidate
from models.api_keys import UsageRecord

@dataclass
class ApplicationMetrics:
    timestamp: datetime
    applications_submitted: int
    applications_failed: int
    applications_in_queue: int
    applications_needs_review: int
    success_rate: float
    avg_processing_time: float
    captcha_encounters: int
    llm_api_calls: int
    total_tokens_used: int
    cost_usd: float

class MetricsCollector:
    def __init__(self):
        self.metrics_history = []
        
    def collect_current_metrics(self) -> ApplicationMetrics:
        """Collect current application metrics"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        session = get_session()
        try:
            # Application status counts
            submitted_today = session.query(Application).filter(
                Application.status == 'submitted',
                Application.submitted_at >= today_start
            ).count()
            
            failed_today = session.query(Application).filter(
                Application.status == 'failed',
                Application.updated_at >= today_start
            ).count()
            
            in_queue = session.query(Application).filter(
                Application.status == 'pending'
            ).count()
            
            needs_review = session.query(Application).filter(
                Application.status == 'needs_review'
            ).count()
            
            # Calculate success rate
            total_processed = session.query(Application).filter(
                Application.status.in_(['submitted', 'failed']),
                Application.updated_at >= today_start
            ).count()
            
            success_rate = (submitted_today / total_processed * 100) if total_processed > 0 else 0
            
            # Processing time metrics
            completed_apps = session.query(Application).filter(
                Application.status == 'submitted',
                Application.submitted_at >= today_start
            ).all()
            
            processing_times = []
            for app in completed_apps:
                if app.created_at and app.submitted_at:
                    duration = (app.submitted_at - app.created_at).total_seconds()
                    processing_times.append(duration)
            
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            # LLM usage metrics
            llm_usage = session.query(UsageRecord).filter(
                UsageRecord.timestamp >= today_start
            ).all()
            
            total_calls = len(llm_usage)
            total_tokens = sum(record.tokens_used for record in llm_usage if record.tokens_used)
            total_cost = sum(record.cost_usd / 100 for record in llm_usage if record.cost_usd)  # Convert from cents
            
            # CAPTCHA encounters (placeholder - would need CAPTCHA event table)
            captcha_count = 0
            
            return ApplicationMetrics(
                timestamp=now,
                applications_submitted=submitted_today,
                applications_failed=failed_today,
                applications_in_queue=in_queue,
                applications_needs_review=needs_review,
                success_rate=success_rate,
                avg_processing_time=avg_processing_time,
                captcha_encounters=captcha_count,
                llm_api_calls=total_calls,
                total_tokens_used=total_tokens,
                cost_usd=total_cost
            )
        finally:
            session.close()
    
    def collect_system_metrics(self) -> Dict:
        """Collect system resource metrics"""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage_percent': psutil.disk_usage('/').percent,
            'network_io': psutil.net_io_counters()._asdict(),
            'process_count': len(psutil.pids()),
            'browser_processes': self._count_browser_processes()
        }
    
    def _count_browser_processes(self) -> int:
        """Count active browser processes"""
        count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'chromium' in proc.info['name'].lower() or 'chrome' in proc.info['name'].lower():
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return count
    
    def store_metrics(self, metrics: ApplicationMetrics):
        """Store metrics in database"""
        # This would store metrics in a dedicated metrics table
        # For now, just append to history
        self.metrics_history.append(metrics)
        
        # Keep only last 1000 metrics
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]
    
    def get_metrics_trend(self, days: int = 7) -> List[ApplicationMetrics]:
        """Get metrics trend for specified number of days"""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Filter metrics from history
        recent_metrics = [
            metric for metric in self.metrics_history 
            if metric.timestamp >= since
        ]
        
        return recent_metrics
    
    def get_dashboard_data(self) -> Dict:
        """Get data for dashboard display"""
        current_metrics = self.collect_current_metrics()
        system_metrics = self.collect_system_metrics()
        
        # Get trend data
        trend_metrics = self.get_metrics_trend(7)
        
        # Calculate trends
        if len(trend_metrics) >= 2:
            latest = trend_metrics[-1]
            previous = trend_metrics[-2]
            
            success_rate_change = latest.success_rate - previous.success_rate
            applications_change = latest.applications_submitted - previous.applications_submitted
        else:
            success_rate_change = 0
            applications_change = 0
        
        return {
            'current_metrics': {
                'applications_submitted': current_metrics.applications_submitted,
                'applications_failed': current_metrics.applications_failed,
                'applications_in_queue': current_metrics.applications_in_queue,
                'applications_needs_review': current_metrics.applications_needs_review,
                'success_rate': current_metrics.success_rate,
                'avg_processing_time': current_metrics.avg_processing_time,
                'llm_api_calls': current_metrics.llm_api_calls,
                'total_tokens_used': current_metrics.total_tokens_used,
                'cost_usd': current_metrics.cost_usd
            },
            'system_metrics': system_metrics,
            'trends': {
                'success_rate_change': success_rate_change,
                'applications_change': applications_change
            },
            'trend_data': [
                {
                    'date': metric.timestamp.strftime('%Y-%m-%d'),
                    'applications_submitted': metric.applications_submitted,
                    'success_rate': metric.success_rate,
                    'cost_usd': metric.cost_usd
                }
                for metric in trend_metrics
            ]
        }

# Global metrics collector instance
metrics_collector = MetricsCollector()
