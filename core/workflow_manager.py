"""
Advanced workflow management for complex task orchestration
"""

import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from utils.logger import get_logger
from core.enhanced_agent import EnhancedAutonomousAgent, Task, TaskPriority, TaskStatus

logger = get_logger(__name__)


@dataclass
class WorkflowStep:
    """Individual step in a workflow"""
    name: str
    function: Any
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    description: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # Python expression for conditional execution
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Workflow execution instance"""
    id: str
    workflow_id: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    current_step: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowManager:
    """Advanced workflow management for complex task orchestration"""
    
    def __init__(self, agent: EnhancedAutonomousAgent):
        self.agent = agent
        self.workflows = {}
        self.workflow_executions = {}
        self.execution_queue = []
    
    def create_workflow(self, name: str, steps: List[Dict[str, Any]]) -> str:
        """Create a workflow with multiple steps"""
        workflow_id = hashlib.md5(f"{name}_{datetime.now()}".encode()).hexdigest()
        
        # Convert step dictionaries to WorkflowStep objects
        workflow_steps = []
        for step_data in steps:
            step = WorkflowStep(
                name=step_data.get('name', 'unnamed_step'),
                function=step_data['function'],
                args=step_data.get('args', ()),
                kwargs=step_data.get('kwargs', {}),
                description=step_data.get('description', ''),
                priority=TaskPriority(step_data.get('priority', 3)),
                timeout=step_data.get('timeout', 300),
                retry_count=step_data.get('retry_count', 0),
                max_retries=step_data.get('max_retries', 3),
                dependencies=step_data.get('dependencies', []),
                condition=step_data.get('condition'),
                metadata=step_data.get('metadata', {})
            )
            workflow_steps.append(step)
        
        self.workflows[workflow_id] = {
            'id': workflow_id,
            'name': name,
            'steps': workflow_steps,
            'created_at': datetime.now(),
            'metadata': {}
        }
        
        logger.info(f"Created workflow: {name} (ID: {workflow_id}) with {len(workflow_steps)} steps")
        return workflow_id
    
    def execute_workflow(self, workflow_id: str, context: Dict[str, Any] = None) -> str:
        """Execute a workflow"""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        execution_id = hashlib.md5(f"{workflow_id}_{datetime.now()}".encode()).hexdigest()
        
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            status='running',
            started_at=datetime.now(),
            context=context or {}
        )
        
        self.workflow_executions[execution_id] = execution
        
        # Add to execution queue
        self.execution_queue.append(execution_id)
        
        logger.info(f"Started workflow execution: {execution_id} for workflow: {workflow['name']}")
        
        # Start execution in background
        self._execute_workflow_async(execution_id)
        
        return execution_id
    
    def _execute_workflow_async(self, execution_id: str):
        """Execute workflow asynchronously"""
        try:
            execution = self.workflow_executions[execution_id]
            workflow = self.workflows[execution.workflow_id]
            
            # Execute steps sequentially
            for i, step in enumerate(workflow['steps']):
                execution.current_step = i
                
                # Check dependencies
                if not self._check_dependencies(step, execution):
                    logger.warning(f"Step {step.name} dependencies not met, skipping")
                    continue
                
                # Check condition
                if step.condition and not self._evaluate_condition(step.condition, execution):
                    logger.info(f"Step {step.name} condition not met, skipping")
                    continue
                
                # Create and schedule task
                task = self.agent.create_task(
                    name=f"{workflow['name']}_step_{i}_{step.name}",
                    function=step.function,
                    *step.args,
                    description=step.description,
                    priority=step.priority,
                    timeout=step.timeout,
                    **step.kwargs
                )
                
                # Add workflow context to task metadata
                task.metadata.update({
                    'workflow_id': execution.workflow_id,
                    'execution_id': execution_id,
                    'step_index': i,
                    'step_name': step.name
                })
                
                self.agent.schedule_task(task)
                
                # Wait for task completion (simplified - in production use proper async handling)
                while task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    time.sleep(0.1)
                
                if task.status == TaskStatus.FAILED:
                    execution.status = 'failed'
                    execution.error = task.error
                    execution.completed_at = datetime.now()
                    logger.error(f"Workflow execution {execution_id} failed at step {step.name}: {task.error}")
                    break
                
                # Store step result
                execution.step_results[i] = {
                    'name': step.name,
                    'result': task.result,
                    'status': task.status.value,
                    'completed_at': datetime.now()
                }
                
                # Update context with step result
                execution.context[f"step_{i}_result"] = task.result
                execution.context[f"step_{step.name}_result"] = task.result
                
                logger.info(f"Completed step {i}: {step.name}")
            
            else:
                # All steps completed successfully
                execution.status = 'completed'
                execution.completed_at = datetime.now()
                logger.info(f"Workflow execution {execution_id} completed successfully")
        
        except Exception as e:
            execution.status = 'failed'
            execution.error = str(e)
            execution.completed_at = datetime.now()
            logger.error(f"Workflow execution {execution_id} failed: {e}")
    
    def _check_dependencies(self, step: WorkflowStep, execution: WorkflowExecution) -> bool:
        """Check if step dependencies are met"""
        for dep in step.dependencies:
            if dep not in execution.step_results:
                return False
        return True
    
    def _evaluate_condition(self, condition: str, execution: WorkflowExecution) -> bool:
        """Evaluate step condition"""
        try:
            # Create a safe evaluation context
            context = {
                'context': execution.context,
                'step_results': execution.step_results,
                'current_step': execution.current_step
            }
            
            # Add common functions
            context.update({
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict
            })
            
            return eval(condition, {"__builtins__": {}}, context)
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False
    
    def get_workflow_status(self, execution_id: str) -> Dict[str, Any]:
        """Get workflow execution status"""
        execution = self.workflow_executions.get(execution_id)
        if not execution:
            return {}
        
        workflow = self.workflows.get(execution.workflow_id, {})
        
        return {
            'execution_id': execution.id,
            'workflow_id': execution.workflow_id,
            'workflow_name': workflow.get('name', 'Unknown'),
            'status': execution.status,
            'started_at': execution.started_at.isoformat() if execution.started_at else None,
            'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
            'current_step': execution.current_step,
            'total_steps': len(workflow.get('steps', [])),
            'step_results': execution.step_results,
            'error': execution.error,
            'context': execution.context
        }
    
    def cancel_workflow(self, execution_id: str) -> bool:
        """Cancel a workflow execution"""
        execution = self.workflow_executions.get(execution_id)
        if not execution:
            return False
        
        if execution.status in ['completed', 'failed', 'cancelled']:
            return False
        
        execution.status = 'cancelled'
        execution.completed_at = datetime.now()
        
        logger.info(f"Cancelled workflow execution: {execution_id}")
        return True
    
    def get_workflow_executions(self, workflow_id: str = None) -> List[Dict[str, Any]]:
        """Get all workflow executions"""
        executions = []
        
        for exec_id, execution in self.workflow_executions.items():
            if workflow_id and execution.workflow_id != workflow_id:
                continue
            
            executions.append(self.get_workflow_status(exec_id))
        
        return executions
    
    def cleanup_old_executions(self, days: int = 30):
        """Clean up old workflow executions"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        to_remove = []
        for exec_id, execution in self.workflow_executions.items():
            if execution.completed_at and execution.completed_at < cutoff_date:
                to_remove.append(exec_id)
        
        for exec_id in to_remove:
            del self.workflow_executions[exec_id]
        
        logger.info(f"Cleaned up {len(to_remove)} old workflow executions")


# Example workflow definitions
def create_job_application_workflow(agent: EnhancedAutonomousAgent) -> str:
    """Create a job application workflow"""
    workflow_manager = WorkflowManager(agent)
    
    steps = [
        {
            'name': 'analyze_job',
            'function': lambda job_url: {'url': job_url, 'analysis': 'Job analyzed'},
            'args': ('https://example.com/job',),
            'description': 'Analyze job posting',
            'priority': TaskPriority.HIGH
        },
        {
            'name': 'prepare_resume',
            'function': lambda job_data: {'resume': 'Resume prepared for job'},
            'description': 'Prepare tailored resume',
            'dependencies': ['analyze_job'],
            'priority': TaskPriority.HIGH
        },
        {
            'name': 'write_cover_letter',
            'function': lambda job_data, resume_data: {'cover_letter': 'Cover letter written'},
            'description': 'Write cover letter',
            'dependencies': ['analyze_job', 'prepare_resume'],
            'priority': TaskPriority.NORMAL
        },
        {
            'name': 'submit_application',
            'function': lambda job_data, resume_data, cover_letter: {'submitted': True},
            'description': 'Submit application',
            'dependencies': ['prepare_resume', 'write_cover_letter'],
            'condition': 'context.get("step_prepare_resume_result") and context.get("step_write_cover_letter_result")',
            'priority': TaskPriority.CRITICAL
        }
    ]
    
    return workflow_manager.create_workflow("Job Application", steps)


def create_data_processing_workflow(agent: EnhancedAutonomousAgent) -> str:
    """Create a data processing workflow"""
    workflow_manager = WorkflowManager(agent)
    
    steps = [
        {
            'name': 'extract_data',
            'function': lambda source: {'data': 'Data extracted from source'},
            'description': 'Extract data from source',
            'priority': TaskPriority.HIGH
        },
        {
            'name': 'clean_data',
            'function': lambda raw_data: {'cleaned_data': 'Data cleaned'},
            'description': 'Clean extracted data',
            'dependencies': ['extract_data'],
            'priority': TaskPriority.NORMAL
        },
        {
            'name': 'analyze_data',
            'function': lambda cleaned_data: {'analysis': 'Data analyzed'},
            'description': 'Analyze cleaned data',
            'dependencies': ['clean_data'],
            'priority': TaskPriority.NORMAL
        },
        {
            'name': 'generate_report',
            'function': lambda analysis: {'report': 'Report generated'},
            'description': 'Generate analysis report',
            'dependencies': ['analyze_data'],
            'priority': TaskPriority.LOW
        }
    ]
    
    return workflow_manager.create_workflow("Data Processing", steps)
