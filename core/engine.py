# core/engine.py
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import time

from models.database import get_session, Job, Application, Candidate
from scraping.job_scraper import JobScraper
from llm.provider_manager import LLMProviderManager
from platform_adapters.adapter_registry import PlatformAdapterRegistry
from rag.vector_store import RAGVectorStore
from utils.logger import log_audit

logger = logging.getLogger(__name__)

class JobAgentEngine:
    """Core orchestration engine for the JobAgent."""

    def __init__(self):
        logger.info("Initializing JobAgent Engine...")
        self.scraper = JobScraper()
        self.llm_manager = LLMProviderManager()
        self.adapter_registry = PlatformAdapterRegistry()
        self.rag_store = RAGVectorStore()
        self.running = False
        self.dry_run_mode = False
        
        # Configuration
        self.max_concurrent_jobs = 3
        self.rate_limit_delay = 5  # seconds
        self.job_processing_timeout = 300  # seconds

    async def start(self):
        """Start the engine"""
        logger.info("Starting JobAgent Engine...")
        self.running = True
        
        try:
            while self.running:
                await self._process_job_queue()
                await asyncio.sleep(10)  # Check queue every 10 seconds
        except Exception as e:
            logger.error(f"Engine error: {e}")
            self.running = False
            raise

    async def stop(self):
        """Stop the engine"""
        logger.info("Stopping JobAgent Engine...")
        self.running = False

    async def _process_job_queue(self):
        """Process jobs from the queue"""
        session = get_session()
        try:
            # Get pending applications
            pending_apps = session.query(Application).filter_by(
                status='pending'
            ).limit(self.max_concurrent_jobs).all()
            
            if not pending_apps:
                return
            
            logger.info(f"Processing {len(pending_apps)} pending applications")
            
            # Process applications concurrently
            tasks = []
            for app in pending_apps:
                task = asyncio.create_task(self._process_application(app))
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle results
            for app, result in zip(pending_apps, results):
                if isinstance(result, Exception):
                    logger.error(f"Application {app.id} failed: {result}")
                    app.status = 'failed'
                    app.error_message = str(result)
                else:
                    logger.info(f"Application {app.id} completed successfully")
                
                app.updated_at = datetime.utcnow()
            
            session.commit()
            
        except Exception as e:
            logger.error(f"Error processing job queue: {e}")
            session.rollback()
        finally:
            session.close()

    async def _process_application(self, application: Application):
        """Process a single application"""
        logger.info(f"Processing application {application.id}")
        
        try:
            # Get job and candidate data
            session = get_session()
            job = session.query(Job).filter_by(id=application.job_id).first()
            candidate = session.query(Candidate).filter_by(id=application.candidate_id).first()
            
            if not job or not candidate:
                raise ValueError("Job or candidate not found")
            
            # 1. Detect platform
            platform = await self._detect_platform(job.url)
            logger.info(f"Detected platform: {platform}")
            
            # 2. Get platform adapter
            adapter = self.adapter_registry.get_adapter(platform)
            if not adapter:
                raise ValueError(f"No adapter found for platform: {platform}")
            
            # 3. Get LLM provider
            llm_provider = self.llm_manager.get_provider()
            if not llm_provider:
                raise ValueError("No LLM provider available")
            
            # 4. Process application
            result = await self._apply_to_job(job, candidate, adapter, llm_provider)
            
            # 5. Update application status
            application.status = result['status']
            application.submitted_at = datetime.utcnow() if result['status'] == 'submitted' else None
            application.error_message = result.get('error_message')
            
            # 6. Log audit trail
            log_audit(
                action='application_processed',
                job_id=str(job.id),
                platform=platform,
                status=result['status'],
                details=result
            )
            
            session.commit()
            logger.info(f"Application {application.id} processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing application {application.id}: {e}")
            application.status = 'failed'
            application.error_message = str(e)
            session.commit()
            raise
        finally:
            session.close()

    async def _detect_platform(self, url: str) -> str:
        """Detect the platform from URL"""
        # Simple platform detection based on URL
        url_lower = url.lower()
        
        if 'greenhouse' in url_lower:
            return 'greenhouse'
        elif 'lever' in url_lower:
            return 'lever'
        elif 'workable' in url_lower:
            return 'workable'
        elif 'linkedin' in url_lower:
            return 'linkedin'
        elif 'indeed' in url_lower:
            return 'indeed'
        else:
            return 'generic'

    async def _apply_to_job(self, job: Job, candidate: Candidate, adapter, llm_provider):
        """Apply to a job using the appropriate adapter"""
        try:
            # 1. Get job details
            job_details = await self.scraper.get_job_details(job.url)
            
            # 2. Generate application materials using RAG
            application_materials = await self._generate_application_materials(
                job_details, candidate, llm_provider
            )
            
            # 3. Apply using platform adapter
            if self.dry_run_mode:
                result = await adapter.dry_run_apply(job_details, application_materials)
            else:
                result = await adapter.apply(job_details, application_materials)
            
            return result
            
        except Exception as e:
            logger.error(f"Error applying to job: {e}")
            return {
                'status': 'failed',
                'error_message': str(e)
            }

    async def _generate_application_materials(self, job_details: Dict, candidate: Candidate, llm_provider):
        """Generate application materials using RAG and LLM"""
        try:
            # 1. Get relevant context from RAG
            context = await self.rag_store.get_relevant_context(
                job_details['description'], 
                candidate_id=str(candidate.id)
            )
            
            # 2. Generate cover letter
            cover_letter = await self._generate_cover_letter(
                job_details, candidate, context, llm_provider
            )
            
            # 3. Generate tailored responses
            responses = await self._generate_tailored_responses(
                job_details, candidate, context, llm_provider
            )
            
            return {
                'cover_letter': cover_letter,
                'responses': responses,
                'context': context
            }
            
        except Exception as e:
            logger.error(f"Error generating application materials: {e}")
            raise

    async def _generate_cover_letter(self, job_details: Dict, candidate: Candidate, context: str, llm_provider):
        """Generate a tailored cover letter"""
        prompt = f"""
        Generate a professional cover letter for the following job:
        
        Job Title: {job_details.get('title', 'N/A')}
        Company: {job_details.get('company', 'N/A')}
        Job Description: {job_details.get('description', 'N/A')}
        
        Candidate Information:
        {context}
        
        Requirements:
        1. Keep it professional and concise (3-4 paragraphs)
        2. Highlight relevant experience and skills
        3. Show enthusiasm for the role
        4. Include specific examples from the candidate's background
        5. Tailor it to the specific job requirements
        
        Cover Letter:
        """
        
        try:
            response = await llm_provider.chat([{"role": "user", "content": prompt}])
            return response
        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return "Cover letter generation failed"

    async def _generate_tailored_responses(self, job_details: Dict, candidate: Candidate, context: str, llm_provider):
        """Generate tailored responses for application questions"""
        # This would handle specific questions from the application form
        # For now, return a basic response
        return {
            'why_interested': f"I am excited about the {job_details.get('title', 'position')} role at {job_details.get('company', 'your company')} and believe my background aligns well with your requirements.",
            'salary_expectation': 'Competitive and commensurate with experience',
            'availability': 'Immediate',
            'relocation': 'Open to discussion'
        }

    def set_dry_run_mode(self, enabled: bool):
        """Enable or disable dry run mode"""
        self.dry_run_mode = enabled
        logger.info(f"Dry run mode {'enabled' if enabled else 'disabled'}")

    def get_status(self) -> Dict[str, Any]:
        """Get engine status"""
        return {
            'running': self.running,
            'dry_run_mode': self.dry_run_mode,
            'max_concurrent_jobs': self.max_concurrent_jobs,
            'rate_limit_delay': self.rate_limit_delay
        }

# Global engine instance
engine = JobAgentEngine()
