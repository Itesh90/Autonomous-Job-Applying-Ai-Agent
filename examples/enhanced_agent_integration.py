#!/usr/bin/env python3
"""
Enhanced Autonomous Agent Integration Example
============================================

This example shows how to integrate the enhanced autonomous agent
with the existing job application system.
"""

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from core.enhanced_agent import (
    EnhancedAutonomousAgent, AgentConfig, TaskPriority, TaskStatus
)
from core.workflow_manager import WorkflowManager
from core.monitoring import MonitoringModule, AlertSeverity
from core.scheduler import TaskScheduler

from models.database import get_session, Candidate, Job, Application, ApplicationStatus
from rag.vector_store import VectorStore
from utils.logger import get_logger

logger = get_logger(__name__)


class JobApplicationAgent:
    """Enhanced job application agent using the autonomous agent system"""
    
    def __init__(self):
        # Configure the enhanced agent
        self.config = AgentConfig(
            max_workers=3,
            debug_mode=True,
            rag_enabled=True,
            selenium_enabled=True,
            cache_enabled=True,
            enable_persistence=True,
            max_browser_instances=2
        )
        
        # Initialize the enhanced agent
        self.agent = EnhancedAutonomousAgent(self.config)
        
        # Initialize additional modules
        self.workflow_manager = WorkflowManager(self.agent)
        self.monitoring = MonitoringModule(self.agent)
        self.scheduler = TaskScheduler(self.agent)
        
        # Initialize vector store
        self.vector_store = VectorStore()
        
        # Setup the system
        self._setup_system()
    
    def _setup_system(self):
        """Setup the job application system"""
        logger.info("Setting up job application agent...")
        
        # Add job application knowledge to RAG
        self._add_job_application_knowledge()
        
        # Create job application workflow
        self.workflow_id = self._create_job_application_workflow()
        
        # Setup scheduled tasks
        self._setup_scheduled_tasks()
        
        # Setup monitoring
        self._setup_monitoring()
        
        logger.info("Job application agent setup complete")
    
    def _add_job_application_knowledge(self):
        """Add job application knowledge to the RAG system"""
        knowledge_items = [
            # Resume writing
            ("Resume should be tailored to each job posting and highlight relevant skills", 
             {"category": "resume", "type": "best_practices"}),
            ("Use action verbs and quantify achievements in resume", 
             {"category": "resume", "type": "writing_tips"}),
            ("Keep resume concise, typically 1-2 pages", 
             {"category": "resume", "type": "formatting"}),
            
            # Cover letter writing
            ("Cover letter should be personalized and address specific job requirements", 
             {"category": "cover_letter", "type": "best_practices"}),
            ("Research the company before writing cover letter", 
             {"category": "cover_letter", "type": "research"}),
            ("Cover letter should complement, not repeat, resume", 
             {"category": "cover_letter", "type": "writing_tips"}),
            
            # Job application process
            ("Follow up on applications after 1-2 weeks", 
             {"category": "application", "type": "follow_up"}),
            ("Customize application for each company and position", 
             {"category": "application", "type": "customization"}),
            ("Track all applications in a spreadsheet or CRM", 
             {"category": "application", "type": "organization"}),
            
            # Interview preparation
            ("Research common interview questions for the role", 
             {"category": "interview", "type": "preparation"}),
            ("Prepare STAR method responses for behavioral questions", 
             {"category": "interview", "type": "techniques"}),
            ("Dress professionally and arrive early for interviews", 
             {"category": "interview", "type": "etiquette"}),
            
            # Networking
            ("Build professional network through LinkedIn and industry events", 
             {"category": "networking", "type": "strategies"}),
            ("Reach out to alumni and industry professionals", 
             {"category": "networking", "type": "outreach"}),
            ("Follow up with connections after meetings", 
             {"category": "networking", "type": "follow_up"})
        ]
        
        for text, metadata in knowledge_items:
            self.agent.add_knowledge(text, metadata)
        
        logger.info(f"Added {len(knowledge_items)} job application knowledge items")
    
    def _create_job_application_workflow(self):
        """Create the job application workflow"""
        workflow_steps = [
            {
                'name': 'analyze_job',
                'function': self._analyze_job_posting,
                'description': 'Analyze job posting and extract key requirements',
                'priority': TaskPriority.HIGH
            },
            {
                'name': 'prepare_resume',
                'function': self._prepare_tailored_resume,
                'dependencies': ['analyze_job'],
                'description': 'Prepare resume tailored to job requirements',
                'priority': TaskPriority.HIGH
            },
            {
                'name': 'write_cover_letter',
                'function': self._write_cover_letter,
                'dependencies': ['analyze_job', 'prepare_resume'],
                'description': 'Write personalized cover letter',
                'priority': TaskPriority.NORMAL
            },
            {
                'name': 'submit_application',
                'function': self._submit_application,
                'dependencies': ['prepare_resume', 'write_cover_letter'],
                'description': 'Submit application through job portal',
                'priority': TaskPriority.CRITICAL
            },
            {
                'name': 'follow_up',
                'function': self._schedule_follow_up,
                'dependencies': ['submit_application'],
                'description': 'Schedule follow-up reminder',
                'priority': TaskPriority.LOW
            }
        ]
        
        workflow_id = self.workflow_manager.create_workflow("Job Application", workflow_steps)
        logger.info(f"Created job application workflow: {workflow_id}")
        return workflow_id
    
    def _setup_scheduled_tasks(self):
        """Setup scheduled tasks for the job application system"""
        # Daily job search
        self.scheduler.schedule_cron_task(
            "daily_job_search",
            self._search_new_jobs,
            "0 9 * * *",  # Daily at 9 AM
            priority=TaskPriority.HIGH
        )
        
        # Weekly application review
        self.scheduler.schedule_cron_task(
            "weekly_application_review",
            self._review_applications,
            "0 10 * * 1",  # Weekly on Monday at 10 AM
            priority=TaskPriority.NORMAL
        )
        
        # Monthly networking reminder
        self.scheduler.schedule_cron_task(
            "monthly_networking",
            self._networking_reminder,
            "0 14 1 * *",  # Monthly on 1st at 2 PM
            priority=TaskPriority.LOW
        )
        
        logger.info("Scheduled job application tasks")
    
    def _setup_monitoring(self):
        """Setup monitoring and alerting"""
        # Register alert handlers
        self.monitoring.register_alert_handler("logger", self._log_alert)
        
        # Set custom thresholds for job application system
        self.monitoring.set_threshold("task_queue_warning", 50)  # Lower threshold for job apps
        self.monitoring.set_threshold("task_queue_critical", 100)
        
        logger.info("Setup monitoring and alerting")
    
    def start(self):
        """Start the job application agent"""
        logger.info("Starting job application agent...")
        
        # Start all components
        self.agent.start()
        self.monitoring.start_monitoring()
        self.scheduler.start_scheduler()
        
        logger.info("Job application agent started successfully")
    
    def stop(self):
        """Stop the job application agent"""
        logger.info("Stopping job application agent...")
        
        # Stop all components
        self.scheduler.stop_scheduler()
        self.monitoring.stop_monitoring()
        self.agent.stop()
        
        logger.info("Job application agent stopped")
    
    def apply_to_job(self, job_url: str, candidate_id: int = None):
        """Apply to a specific job"""
        logger.info(f"Starting application process for job: {job_url}")
        
        # Create context for the workflow
        context = {
            'job_url': job_url,
            'candidate_id': candidate_id,
            'application_date': datetime.now().isoformat()
        }
        
        # Execute the job application workflow
        execution_id = self.workflow_manager.execute_workflow(self.workflow_id, context)
        
        logger.info(f"Started job application workflow: {execution_id}")
        return execution_id
    
    def get_application_status(self, execution_id: str):
        """Get the status of a job application"""
        return self.workflow_manager.get_workflow_status(execution_id)
    
    def search_jobs(self, keywords: str, location: str = None):
        """Search for jobs using the enhanced agent"""
        logger.info(f"Searching for jobs with keywords: {keywords}")
        
        # Create a job search task
        task = self.agent.create_task(
            name="Job Search",
            function=self._search_jobs_task,
            keywords,
            location,
            description=f"Search for jobs with keywords: {keywords}",
            priority=TaskPriority.HIGH
        )
        
        self.agent.schedule_task(task)
        return task.id
    
    def get_system_status(self):
        """Get overall system status"""
        return {
            'agent_status': self.agent.get_status(),
            'system_health': self.monitoring.get_system_health(),
            'recent_alerts': self.monitoring.get_alerts(limit=5),
            'scheduled_jobs': self.scheduler.get_jobs()
        }
    
    # Workflow step functions
    def _analyze_job_posting(self, job_url: str, **context):
        """Analyze job posting and extract requirements"""
        logger.info(f"Analyzing job posting: {job_url}")
        
        # Simulate job analysis
        time.sleep(2)
        
        # Query knowledge base for job analysis tips
        analysis_tips = self.agent.query_knowledge("job posting analysis")
        
        return {
            'job_url': job_url,
            'title': 'Software Engineer',
            'company': 'Example Corp',
            'requirements': ['Python', 'JavaScript', '3+ years experience'],
            'analysis_tips': analysis_tips,
            'analysis_complete': True
        }
    
    def _prepare_tailored_resume(self, job_analysis: dict, **context):
        """Prepare resume tailored to job requirements"""
        logger.info("Preparing tailored resume")
        
        # Query knowledge base for resume tips
        resume_tips = self.agent.query_knowledge("resume writing best practices")
        
        # Simulate resume preparation
        time.sleep(3)
        
        return {
            'resume_file': 'tailored_resume.pdf',
            'resume_tips': resume_tips,
            'tailored_for': job_analysis['title'],
            'resume_ready': True
        }
    
    def _write_cover_letter(self, job_analysis: dict, resume_data: dict, **context):
        """Write personalized cover letter"""
        logger.info("Writing cover letter")
        
        # Query knowledge base for cover letter tips
        cover_letter_tips = self.agent.query_knowledge("cover letter writing")
        
        # Simulate cover letter writing
        time.sleep(2)
        
        return {
            'cover_letter_file': 'cover_letter.pdf',
            'cover_letter_tips': cover_letter_tips,
            'personalized_for': job_analysis['company'],
            'cover_letter_ready': True
        }
    
    def _submit_application(self, resume_data: dict, cover_letter_data: dict, **context):
        """Submit application through job portal"""
        logger.info("Submitting application")
        
        # Simulate application submission
        time.sleep(5)
        
        return {
            'submission_id': f"app_{int(time.time())}",
            'submitted_at': datetime.now().isoformat(),
            'status': 'submitted',
            'submission_successful': True
        }
    
    def _schedule_follow_up(self, submission_data: dict, **context):
        """Schedule follow-up reminder"""
        logger.info("Scheduling follow-up")
        
        # Schedule follow-up task
        follow_up_time = datetime.now() + timedelta(days=7)
        
        self.scheduler.schedule_one_time_task(
            "follow_up_reminder",
            self._send_follow_up,
            follow_up_time,
            submission_data['submission_id']
        )
        
        return {
            'follow_up_scheduled': True,
            'follow_up_date': follow_up_time.isoformat()
        }
    
    # Scheduled task functions
    def _search_new_jobs(self):
        """Search for new job postings"""
        logger.info("Searching for new job postings")
        
        # Query knowledge base for job search strategies
        search_strategies = self.agent.query_knowledge("job search strategies")
        
        # Simulate job search
        time.sleep(5)
        
        return {
            'jobs_found': 15,
            'search_strategies': search_strategies,
            'search_complete': True
        }
    
    def _review_applications(self):
        """Review recent applications"""
        logger.info("Reviewing recent applications")
        
        # Get applications from database
        session = get_session()
        recent_apps = session.query(Application).filter(
            Application.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        session.close()
        
        return {
            'applications_reviewed': len(recent_apps),
            'review_complete': True
        }
    
    def _networking_reminder(self):
        """Send networking reminder"""
        logger.info("Sending networking reminder")
        
        # Query knowledge base for networking tips
        networking_tips = self.agent.query_knowledge("professional networking")
        
        return {
            'reminder_sent': True,
            'networking_tips': networking_tips
        }
    
    # Helper functions
    def _search_jobs_task(self, keywords: str, location: str = None):
        """Task function for job search"""
        logger.info(f"Executing job search task: {keywords}")
        
        # Simulate job search
        time.sleep(3)
        
        return {
            'keywords': keywords,
            'location': location,
            'jobs_found': 25,
            'search_results': [
                {'title': 'Software Engineer', 'company': 'Tech Corp', 'location': 'Remote'},
                {'title': 'Python Developer', 'company': 'Startup Inc', 'location': 'San Francisco'}
            ]
        }
    
    def _send_follow_up(self, submission_id: str):
        """Send follow-up email"""
        logger.info(f"Sending follow-up for submission: {submission_id}")
        
        # Query knowledge base for follow-up tips
        follow_up_tips = self.agent.query_knowledge("application follow up")
        
        return {
            'follow_up_sent': True,
            'submission_id': submission_id,
            'follow_up_tips': follow_up_tips
        }
    
    def _log_alert(self, alert):
        """Log alert handler"""
        logger.warning(f"JOB APPLICATION ALERT [{alert.severity.value.upper()}]: {alert.message}")


def main():
    """Main function to demonstrate the job application agent"""
    print("=== Enhanced Job Application Agent Demo ===")
    
    # Create the job application agent
    agent = JobApplicationAgent()
    
    try:
        # Start the agent
        agent.start()
        
        # Apply to a job
        print("\n1. Applying to a job...")
        execution_id = agent.apply_to_job("https://example.com/job/123")
        
        # Search for jobs
        print("\n2. Searching for jobs...")
        search_task_id = agent.search_jobs("Python developer", "Remote")
        
        # Wait for some processing
        print("\n3. Waiting for processing...")
        time.sleep(10)
        
        # Check application status
        print("\n4. Checking application status...")
        status = agent.get_application_status(execution_id)
        print(f"   Application status: {status.get('status', 'unknown')}")
        
        # Get system status
        print("\n5. System status...")
        system_status = agent.get_system_status()
        print(f"   Agent running: {system_status['agent_status']['is_running']}")
        print(f"   System health: {system_status['system_health']['status']}")
        print(f"   Recent alerts: {len(system_status['recent_alerts'])}")
        print(f"   Scheduled jobs: {len(system_status['scheduled_jobs'])}")
        
        # Wait a bit more
        print("\n6. Waiting for more processing...")
        time.sleep(5)
        
        print("\nDemo completed successfully!")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    
    except Exception as e:
        print(f"Demo error: {e}")
        logger.error(f"Demo error: {e}", exc_info=True)
    
    finally:
        # Stop the agent
        agent.stop()


if __name__ == "__main__":
    main()
