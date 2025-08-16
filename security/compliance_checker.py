# security/compliance_checker.py
from datetime import datetime, timedelta
from typing import Dict, Any
import logging

from models.database import get_session, Application, Job, Candidate
from models.api_keys import AuditLog

logger = logging.getLogger(__name__)

class ComplianceChecker:
    """GDPR and privacy compliance checker"""
    
    def __init__(self):
        self.pii_manager = None  # Will be imported when needed
    
    def check_data_retention(self) -> Dict[str, Any]:
        """Check data retention compliance"""
        session = get_session()
        
        try:
            # Check for old data that should be deleted
            retention_limit = datetime.utcnow() - timedelta(days=90)
            
            old_applications = session.query(Application).filter(
                Application.created_at < retention_limit
            ).count()
            
            old_jobs = session.query(Job).filter(
                Job.scraped_at < retention_limit
            ).count()
            
            # Check for old audit logs
            old_audit_logs = session.query(AuditLog).filter(
                AuditLog.timestamp < retention_limit
            ).count()
            
            return {
                'old_applications': old_applications,
                'old_jobs': old_jobs,
                'old_audit_logs': old_audit_logs,
                'compliance_status': 'pass' if all([
                    old_applications == 0,
                    old_jobs == 0,
                    old_audit_logs == 0
                ]) else 'needs_attention'
            }
        finally:
            session.close()
    
    def audit_data_access(self, user_id: str, data_type: str, action: str):
        """Log data access for audit trail"""
        audit_entry = AuditLog.create(
            action=f"data_access_{action}",
            entity_id=user_id,
            details={
                'data_type': data_type,
                'action': action,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        session = get_session()
        try:
            session.add(audit_entry)
            session.commit()
        finally:
            session.close()
    
    def generate_privacy_report(self) -> Dict[str, Any]:
        """Generate privacy compliance report"""
        session = get_session()
        
        try:
            # Data inventory
            total_candidates = session.query(Candidate).count()
            total_applications = session.query(Application).count()
            total_jobs = session.query(Job).count()
            
            # Recent activity
            last_30_days = datetime.utcnow() - timedelta(days=30)
            recent_applications = session.query(Application).filter(
                Application.created_at >= last_30_days
            ).count()
            
            recent_audit_logs = session.query(AuditLog).filter(
                AuditLog.timestamp >= last_30_days
            ).count()
            
            # Data retention compliance
            retention_status = self.check_data_retention()
            
            return {
                'data_inventory': {
                    'candidates': total_candidates,
                    'applications': total_applications,
                    'jobs': total_jobs
                },
                'recent_activity': {
                    'applications_last_30_days': recent_applications,
                    'audit_logs_last_30_days': recent_audit_logs
                },
                'retention_compliance': retention_status,
                'last_updated': datetime.utcnow().isoformat()
            }
        finally:
            session.close()
    
    def cleanup_old_data(self, days_old: int = 90) -> Dict[str, int]:
        """Clean up old data for compliance"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        session = get_session()
        
        try:
            # Delete old applications
            old_applications = session.query(Application).filter(
                Application.created_at < cutoff_date
            ).delete()
            
            # Delete old jobs
            old_jobs = session.query(Job).filter(
                Job.scraped_at < cutoff_date
            ).delete()
            
            # Delete old audit logs (keep some for compliance)
            old_audit_logs = session.query(AuditLog).filter(
                AuditLog.timestamp < cutoff_date
            ).delete()
            
            session.commit()
            
            return {
                'applications_deleted': old_applications,
                'jobs_deleted': old_jobs,
                'audit_logs_deleted': old_audit_logs
            }
        except Exception as e:
            logger.error(f"Error during data cleanup: {e}")
            session.rollback()
            raise
        finally:
            session.close()

# Global compliance checker instance
compliance_checker = ComplianceChecker()
