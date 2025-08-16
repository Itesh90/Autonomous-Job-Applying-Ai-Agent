"""
System monitoring and alerting module
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import get_logger
from core.enhanced_agent import EnhancedAutonomousAgent

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """System alert"""
    id: str
    type: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_percent: float
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    agent_running: bool
    rag_enabled: bool
    web_automation_enabled: bool
    cache_enabled: bool
    database_enabled: bool


class MonitoringModule:
    """System monitoring and alerting module"""
    
    def __init__(self, agent: EnhancedAutonomousAgent):
        self.agent = agent
        self.metrics = {}
        self.alerts = []
        self.monitoring_active = False
        self.monitor_thread = None
        self.alert_handlers = {}
        
        # Alert thresholds
        self.thresholds = {
            'cpu_warning': 80.0,
            'cpu_critical': 95.0,
            'memory_warning': 85.0,
            'memory_critical': 95.0,
            'disk_warning': 90.0,
            'disk_critical': 95.0,
            'task_queue_warning': 100,
            'task_queue_critical': 500
        }
    
    def start_monitoring(self):
        """Start system monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, name="MonitoringThread")
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Collect metrics
                metrics = self._collect_metrics()
                self.metrics[datetime.now()] = metrics
                
                # Check for alerts
                self._check_alerts(metrics)
                
                # Cleanup old metrics (keep last 1000 entries)
                if len(self.metrics) > 1000:
                    oldest_key = min(self.metrics.keys())
                    del self.metrics[oldest_key]
                
                time.sleep(10)  # Monitor every 10 seconds
            
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(10)
    
    def _collect_metrics(self) -> SystemMetrics:
        """Collect system metrics"""
        try:
            import psutil
        except ImportError:
            logger.warning("psutil not available, using basic metrics")
            return self._collect_basic_metrics()
        
        # System metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Agent metrics
        status = self.agent.get_status()
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / 1024 / 1024,
            disk_percent=disk.percent,
            pending_tasks=status['pending_tasks'],
            running_tasks=status['running_tasks'],
            completed_tasks=status['completed_tasks'],
            agent_running=status['is_running'],
            rag_enabled=status['modules']['rag_enabled'],
            web_automation_enabled=status['modules']['web_automation_enabled'],
            cache_enabled=status['modules']['cache_enabled'],
            database_enabled=status['modules']['database_enabled']
        )
    
    def _collect_basic_metrics(self) -> SystemMetrics:
        """Collect basic metrics when psutil is not available"""
        status = self.agent.get_status()
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=0.0,
            memory_percent=0.0,
            memory_used_mb=0.0,
            disk_percent=0.0,
            pending_tasks=status['pending_tasks'],
            running_tasks=status['running_tasks'],
            completed_tasks=status['completed_tasks'],
            agent_running=status['is_running'],
            rag_enabled=status['modules']['rag_enabled'],
            web_automation_enabled=status['modules']['web_automation_enabled'],
            cache_enabled=status['modules']['cache_enabled'],
            database_enabled=status['modules']['database_enabled']
        )
    
    def _check_alerts(self, metrics: SystemMetrics):
        """Check for alert conditions"""
        alerts = []
        
        # CPU alerts
        if metrics.cpu_percent > self.thresholds['cpu_critical']:
            alerts.append(Alert(
                id=f"cpu_critical_{metrics.timestamp.timestamp()}",
                type='high_cpu',
                message=f"Critical CPU usage: {metrics.cpu_percent:.1f}%",
                severity=AlertSeverity.CRITICAL,
                timestamp=metrics.timestamp,
                metadata={'cpu_percent': metrics.cpu_percent}
            ))
        elif metrics.cpu_percent > self.thresholds['cpu_warning']:
            alerts.append(Alert(
                id=f"cpu_warning_{metrics.timestamp.timestamp()}",
                type='high_cpu',
                message=f"High CPU usage: {metrics.cpu_percent:.1f}%",
                severity=AlertSeverity.WARNING,
                timestamp=metrics.timestamp,
                metadata={'cpu_percent': metrics.cpu_percent}
            ))
        
        # Memory alerts
        if metrics.memory_percent > self.thresholds['memory_critical']:
            alerts.append(Alert(
                id=f"memory_critical_{metrics.timestamp.timestamp()}",
                type='high_memory',
                message=f"Critical memory usage: {metrics.memory_percent:.1f}%",
                severity=AlertSeverity.CRITICAL,
                timestamp=metrics.timestamp,
                metadata={'memory_percent': metrics.memory_percent}
            ))
        elif metrics.memory_percent > self.thresholds['memory_warning']:
            alerts.append(Alert(
                id=f"memory_warning_{metrics.timestamp.timestamp()}",
                type='high_memory',
                message=f"High memory usage: {metrics.memory_percent:.1f}%",
                severity=AlertSeverity.WARNING,
                timestamp=metrics.timestamp,
                metadata={'memory_percent': metrics.memory_percent}
            ))
        
        # Disk alerts
        if metrics.disk_percent > self.thresholds['disk_critical']:
            alerts.append(Alert(
                id=f"disk_critical_{metrics.timestamp.timestamp()}",
                type='high_disk',
                message=f"Critical disk usage: {metrics.disk_percent:.1f}%",
                severity=AlertSeverity.CRITICAL,
                timestamp=metrics.timestamp,
                metadata={'disk_percent': metrics.disk_percent}
            ))
        elif metrics.disk_percent > self.thresholds['disk_warning']:
            alerts.append(Alert(
                id=f"disk_warning_{metrics.timestamp.timestamp()}",
                type='high_disk',
                message=f"High disk usage: {metrics.disk_percent:.1f}%",
                severity=AlertSeverity.WARNING,
                timestamp=metrics.timestamp,
                metadata={'disk_percent': metrics.disk_percent}
            ))
        
        # Task queue alerts
        if metrics.pending_tasks > self.thresholds['task_queue_critical']:
            alerts.append(Alert(
                id=f"task_queue_critical_{metrics.timestamp.timestamp()}",
                type='task_queue_full',
                message=f"Critical task queue size: {metrics.pending_tasks} tasks",
                severity=AlertSeverity.CRITICAL,
                timestamp=metrics.timestamp,
                metadata={'pending_tasks': metrics.pending_tasks}
            ))
        elif metrics.pending_tasks > self.thresholds['task_queue_warning']:
            alerts.append(Alert(
                id=f"task_queue_warning_{metrics.timestamp.timestamp()}",
                type='task_queue_full',
                message=f"Task queue is getting full: {metrics.pending_tasks} tasks",
                severity=AlertSeverity.WARNING,
                timestamp=metrics.timestamp,
                metadata={'pending_tasks': metrics.pending_tasks}
            ))
        
        # Agent status alerts
        if not metrics.agent_running:
            alerts.append(Alert(
                id=f"agent_stopped_{metrics.timestamp.timestamp()}",
                type='agent_stopped',
                message="Agent is not running",
                severity=AlertSeverity.ERROR,
                timestamp=metrics.timestamp
            ))
        
        # Add new alerts
        for alert in alerts:
            self.alerts.append(alert)
            self._trigger_alert_handlers(alert)
            logger.warning(f"ALERT: {alert.message}")
        
        # Cleanup old alerts (keep last 100)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def _trigger_alert_handlers(self, alert: Alert):
        """Trigger registered alert handlers"""
        for handler_name, handler_func in self.alert_handlers.items():
            try:
                handler_func(alert)
            except Exception as e:
                logger.error(f"Error in alert handler {handler_name}: {e}")
    
    def register_alert_handler(self, name: str, handler_func):
        """Register an alert handler function"""
        self.alert_handlers[name] = handler_func
        logger.info(f"Registered alert handler: {name}")
    
    def unregister_alert_handler(self, name: str):
        """Unregister an alert handler"""
        if name in self.alert_handlers:
            del self.alert_handlers[name]
            logger.info(f"Unregistered alert handler: {name}")
    
    def get_metrics(self, last_n: int = 10) -> List[Dict[str, Any]]:
        """Get recent metrics"""
        sorted_times = sorted(self.metrics.keys(), reverse=True)
        recent_times = sorted_times[:last_n]
        
        return [
            {
                'timestamp': t.isoformat(),
                'cpu_percent': self.metrics[t].cpu_percent,
                'memory_percent': self.metrics[t].memory_percent,
                'memory_used_mb': self.metrics[t].memory_used_mb,
                'disk_percent': self.metrics[t].disk_percent,
                'pending_tasks': self.metrics[t].pending_tasks,
                'running_tasks': self.metrics[t].running_tasks,
                'completed_tasks': self.metrics[t].completed_tasks,
                'agent_running': self.metrics[t].agent_running
            }
            for t in reversed(recent_times)
        ]
    
    def get_alerts(self, severity: AlertSeverity = None, acknowledged: bool = None) -> List[Dict[str, Any]]:
        """Get recent alerts with optional filtering"""
        filtered_alerts = self.alerts
        
        if severity:
            filtered_alerts = [a for a in filtered_alerts if a.severity == severity]
        
        if acknowledged is not None:
            filtered_alerts = [a for a in filtered_alerts if a.acknowledged == acknowledged]
        
        return [
            {
                'id': alert.id,
                'type': alert.type,
                'message': alert.message,
                'severity': alert.severity.value,
                'timestamp': alert.timestamp.isoformat(),
                'acknowledged': alert.acknowledged,
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                'acknowledged_by': alert.acknowledged_by,
                'metadata': alert.metadata
            }
            for alert in filtered_alerts
        ]
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.id == alert_id and not alert.acknowledged:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now()
                alert.acknowledged_by = acknowledged_by
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
        return False
    
    def set_threshold(self, metric: str, value: float):
        """Set alert threshold"""
        if metric in self.thresholds:
            self.thresholds[metric] = value
            logger.info(f"Updated threshold for {metric}: {value}")
        else:
            logger.warning(f"Unknown threshold metric: {metric}")
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get current alert thresholds"""
        return self.thresholds.copy()
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        if not self.metrics:
            return {'status': 'unknown', 'message': 'No metrics available'}
        
        latest_metrics = max(self.metrics.values(), key=lambda m: m.timestamp)
        
        # Determine overall health
        health_issues = []
        
        if latest_metrics.cpu_percent > self.thresholds['cpu_critical']:
            health_issues.append('Critical CPU usage')
        elif latest_metrics.cpu_percent > self.thresholds['cpu_warning']:
            health_issues.append('High CPU usage')
        
        if latest_metrics.memory_percent > self.thresholds['memory_critical']:
            health_issues.append('Critical memory usage')
        elif latest_metrics.memory_percent > self.thresholds['memory_warning']:
            health_issues.append('High memory usage')
        
        if latest_metrics.disk_percent > self.thresholds['disk_critical']:
            health_issues.append('Critical disk usage')
        elif latest_metrics.disk_percent > self.thresholds['disk_warning']:
            health_issues.append('High disk usage')
        
        if not latest_metrics.agent_running:
            health_issues.append('Agent not running')
        
        if latest_metrics.pending_tasks > self.thresholds['task_queue_critical']:
            health_issues.append('Task queue overloaded')
        
        # Determine status
        if any('Critical' in issue for issue in health_issues):
            status = 'critical'
        elif health_issues:
            status = 'warning'
        else:
            status = 'healthy'
        
        return {
            'status': status,
            'issues': health_issues,
            'last_check': latest_metrics.timestamp.isoformat(),
            'metrics': {
                'cpu_percent': latest_metrics.cpu_percent,
                'memory_percent': latest_metrics.memory_percent,
                'disk_percent': latest_metrics.disk_percent,
                'pending_tasks': latest_metrics.pending_tasks,
                'agent_running': latest_metrics.agent_running
            }
        }


# Example alert handlers
def log_alert_handler(alert: Alert):
    """Log alert to file"""
    logger.warning(f"ALERT [{alert.severity.value.upper()}]: {alert.message}")


def email_alert_handler(alert: Alert):
    """Send email alert (placeholder)"""
    if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.ERROR]:
        logger.info(f"Would send email alert: {alert.message}")
        # In production, implement actual email sending


def slack_alert_handler(alert: Alert):
    """Send Slack alert (placeholder)"""
    if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.ERROR]:
        logger.info(f"Would send Slack alert: {alert.message}")
        # In production, implement actual Slack integration
