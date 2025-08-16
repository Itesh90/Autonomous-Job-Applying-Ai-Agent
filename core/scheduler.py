"""
Advanced task scheduler with cron-like functionality
"""

import hashlib
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import get_logger
from core.enhanced_agent import EnhancedAutonomousAgent, Task, TaskPriority

logger = get_logger(__name__)


class ScheduleType(Enum):
    """Schedule types"""
    INTERVAL = "interval"
    CRON = "cron"
    ONCE = "once"


@dataclass
class ScheduledJob:
    """Scheduled job definition"""
    id: str
    name: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    priority: TaskPriority = TaskPriority.NORMAL
    description: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskScheduler:
    """Advanced task scheduler with cron-like functionality"""
    
    def __init__(self, agent: EnhancedAutonomousAgent):
        self.agent = agent
        self.scheduled_jobs = {}
        self.scheduler_active = False
        self.scheduler_thread = None
        self.job_history = []
    
    def start_scheduler(self):
        """Start the task scheduler"""
        if self.scheduler_active:
            return
        
        self.scheduler_active = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, name="SchedulerThread")
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        logger.info("Task scheduler started")
    
    def stop_scheduler(self):
        """Stop the task scheduler"""
        self.scheduler_active = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Task scheduler stopped")
    
    def schedule_recurring_task(self, name: str, function: Callable, 
                              interval_seconds: int, *args, **kwargs) -> str:
        """Schedule a recurring task"""
        job_id = hashlib.md5(f"{name}_{datetime.now()}".encode()).hexdigest()
        
        job = ScheduledJob(
            id=job_id,
            name=name,
            function=function,
            args=args,
            kwargs=kwargs,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=interval_seconds,
            next_run=datetime.now()
        )
        
        self.scheduled_jobs[job_id] = job
        
        logger.info(f"Scheduled recurring task: {name} (every {interval_seconds}s)")
        return job_id
    
    def schedule_cron_task(self, name: str, function: Callable, 
                          cron_expression: str, *args, **kwargs) -> str:
        """Schedule a task with cron-like expression"""
        job_id = hashlib.md5(f"{name}_{datetime.now()}".encode()).hexdigest()
        
        job = ScheduledJob(
            id=job_id,
            name=name,
            function=function,
            args=args,
            kwargs=kwargs,
            schedule_type=ScheduleType.CRON,
            cron_expression=cron_expression,
            next_run=self._parse_cron(cron_expression)
        )
        
        self.scheduled_jobs[job_id] = job
        
        logger.info(f"Scheduled cron task: {name} ({cron_expression})")
        return job_id
    
    def schedule_one_time_task(self, name: str, function: Callable,
                              scheduled_time: datetime, *args, **kwargs) -> str:
        """Schedule a one-time task"""
        job_id = hashlib.md5(f"{name}_{datetime.now()}".encode()).hexdigest()
        
        job = ScheduledJob(
            id=job_id,
            name=name,
            function=function,
            args=args,
            kwargs=kwargs,
            schedule_type=ScheduleType.ONCE,
            scheduled_time=scheduled_time,
            next_run=scheduled_time
        )
        
        self.scheduled_jobs[job_id] = job
        
        logger.info(f"Scheduled one-time task: {name} at {scheduled_time}")
        return job_id
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.scheduler_active:
            try:
                now = datetime.now()
                
                for job_id, job in self.scheduled_jobs.items():
                    if not job.active:
                        continue
                    
                    if now >= job.next_run:
                        # Check if max runs reached
                        if job.max_runs and job.run_count >= job.max_runs:
                            job.active = False
                            logger.info(f"Job {job.name} reached max runs ({job.max_runs})")
                            continue
                        
                        # Create and schedule task
                        task = self.agent.create_task(
                            name=f"scheduled_{job.name}",
                            function=job.function,
                            *job.args,
                            description=f"Scheduled task: {job.name}",
                            priority=job.priority,
                            **job.kwargs
                        )
                        
                        # Add job metadata to task
                        task.metadata.update({
                            'scheduled_job_id': job_id,
                            'schedule_type': job.schedule_type.value,
                            'run_count': job.run_count + 1
                        })
                        
                        self.agent.schedule_task(task)
                        
                        # Update job timing
                        job.last_run = now
                        job.run_count += 1
                        
                        # Calculate next run time
                        if job.schedule_type == ScheduleType.INTERVAL:
                            job.next_run = now + timedelta(seconds=job.interval_seconds)
                        elif job.schedule_type == ScheduleType.CRON:
                            job.next_run = self._parse_cron(job.cron_expression)
                        elif job.schedule_type == ScheduleType.ONCE:
                            job.active = False  # One-time task completed
                        
                        # Record in history
                        self._record_job_execution(job, task)
                        
                        logger.info(f"Executed scheduled job: {job.name} (run {job.run_count})")
                
                time.sleep(1)  # Check every second
            
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(5)
    
    def _parse_cron(self, cron_expression: str) -> datetime:
        """Parse cron expression (simplified implementation)"""
        # This is a simplified implementation
        # In production, use a proper cron parser like croniter
        
        parts = cron_expression.split()
        
        if len(parts) != 5:
            raise ValueError("Invalid cron expression. Expected format: minute hour day month weekday")
        
        minute, hour, day, month, weekday = parts
        
        now = datetime.now()
        
        # For now, just schedule for next hour
        # In production, implement proper cron parsing
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        return next_run
    
    def _record_job_execution(self, job: ScheduledJob, task: Task):
        """Record job execution in history"""
        execution_record = {
            'job_id': job.id,
            'job_name': job.name,
            'task_id': task.id,
            'executed_at': datetime.now(),
            'run_count': job.run_count,
            'schedule_type': job.schedule_type.value
        }
        
        self.job_history.append(execution_record)
        
        # Keep only last 1000 records
        if len(self.job_history) > 1000:
            self.job_history = self.job_history[-1000:]
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled job"""
        if job_id in self.scheduled_jobs:
            self.scheduled_jobs[job_id].active = False
            logger.info(f"Cancelled job: {job_id}")
            return True
        return False
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job"""
        if job_id in self.scheduled_jobs:
            self.scheduled_jobs[job_id].active = False
            logger.info(f"Paused job: {job_id}")
            return True
        return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        if job_id in self.scheduled_jobs:
            self.scheduled_jobs[job_id].active = True
            logger.info(f"Resumed job: {job_id}")
            return True
        return False
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get all scheduled jobs"""
        jobs = []
        
        for job in self.scheduled_jobs.values():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'schedule_type': job.schedule_type.value,
                'interval_seconds': job.interval_seconds,
                'cron_expression': job.cron_expression,
                'scheduled_time': job.scheduled_time.isoformat() if job.scheduled_time else None,
                'priority': job.priority.value,
                'description': job.description,
                'active': job.active,
                'created_at': job.created_at.isoformat(),
                'last_run': job.last_run.isoformat() if job.last_run else None,
                'next_run': job.next_run.isoformat() if job.next_run else None,
                'run_count': job.run_count,
                'max_runs': job.max_runs,
                'metadata': job.metadata
            })
        
        return jobs
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job"""
        job = self.scheduled_jobs.get(job_id)
        if not job:
            return None
        
        return {
            'id': job.id,
            'name': job.name,
            'schedule_type': job.schedule_type.value,
            'interval_seconds': job.interval_seconds,
            'cron_expression': job.cron_expression,
            'scheduled_time': job.scheduled_time.isoformat() if job.scheduled_time else None,
            'priority': job.priority.value,
            'description': job.description,
            'active': job.active,
            'created_at': job.created_at.isoformat(),
            'last_run': job.last_run.isoformat() if job.last_run else None,
            'next_run': job.next_run.isoformat() if job.next_run else None,
            'run_count': job.run_count,
            'max_runs': job.max_runs,
            'metadata': job.metadata
        }
    
    def get_job_history(self, job_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get job execution history"""
        history = self.job_history
        
        if job_id:
            history = [h for h in history if h['job_id'] == job_id]
        
        # Return most recent records
        return history[-limit:] if len(history) > limit else history
    
    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update job parameters"""
        job = self.scheduled_jobs.get(job_id)
        if not job:
            return False
        
        # Update allowed fields
        allowed_fields = ['name', 'description', 'priority', 'active', 'max_runs', 'metadata']
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(job, field, value)
        
        logger.info(f"Updated job: {job_id}")
        return True
    
    def cleanup_old_history(self, days: int = 30):
        """Clean up old job history"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        self.job_history = [
            record for record in self.job_history
            if record['executed_at'] > cutoff_date
        ]
        
        logger.info(f"Cleaned up job history older than {days} days")


# Example scheduled tasks
def maintenance_task():
    """Example maintenance task"""
    logger.info("Running maintenance task")
    return "Maintenance completed"


def data_backup_task():
    """Example data backup task"""
    logger.info("Running data backup task")
    return "Backup completed"


def health_check_task():
    """Example health check task"""
    logger.info("Running health check task")
    return "Health check completed"


def report_generation_task():
    """Example report generation task"""
    logger.info("Running report generation task")
    return "Report generated"


# Example usage functions
def setup_default_schedules(scheduler: TaskScheduler):
    """Setup default scheduled tasks"""
    
    # Maintenance every hour
    scheduler.schedule_recurring_task(
        "maintenance",
        maintenance_task,
        3600,  # 1 hour
        priority=TaskPriority.LOW
    )
    
    # Health check every 5 minutes
    scheduler.schedule_recurring_task(
        "health_check",
        health_check_task,
        300,  # 5 minutes
        priority=TaskPriority.NORMAL
    )
    
    # Data backup daily at 2 AM
    scheduler.schedule_cron_task(
        "data_backup",
        data_backup_task,
        "0 2 * * *",  # Daily at 2 AM
        priority=TaskPriority.HIGH
    )
    
    # Report generation weekly on Monday at 9 AM
    scheduler.schedule_cron_task(
        "weekly_report",
        report_generation_task,
        "0 9 * * 1",  # Weekly on Monday at 9 AM
        priority=TaskPriority.NORMAL
    )
    
    logger.info("Default schedules configured")
