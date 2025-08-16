#!/usr/bin/env python3
"""
Enhanced Autonomous Agent Demo
==============================

This script demonstrates the comprehensive features of the enhanced autonomous agent:
- RAG (Retrieval-Augmented Generation) for knowledge management
- Web automation with Selenium
- Task scheduling and queuing
- Workflow management
- System monitoring and alerting
- Caching and performance optimization
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
from core.workflow_manager import WorkflowManager, create_job_application_workflow
from core.monitoring import MonitoringModule, AlertSeverity
from core.scheduler import TaskScheduler, setup_default_schedules

from utils.logger import get_logger

logger = get_logger(__name__)


def example_task(message: str, delay: int = 1) -> str:
    """Example task function"""
    time.sleep(delay)
    return f"Task completed: {message}"


async def example_async_task(message: str, delay: int = 1) -> str:
    """Example async task function"""
    await asyncio.sleep(delay)
    return f"Async task completed: {message}"


def web_scraping_task(agent: EnhancedAutonomousAgent, url: str) -> dict:
    """Example web scraping task"""
    logger.info(f"Scraping website: {url}")
    result = agent.web_scrape(url)
    return result


def data_processing_task(data: str) -> dict:
    """Example data processing task"""
    logger.info(f"Processing data: {data[:50]}...")
    # Simulate data processing
    time.sleep(2)
    return {
        'processed_data': f"Processed: {data}",
        'timestamp': datetime.now().isoformat(),
        'status': 'completed'
    }


def knowledge_query_task(agent: EnhancedAutonomousAgent, query: str) -> list:
    """Example knowledge query task"""
    logger.info(f"Querying knowledge base: {query}")
    results = agent.query_knowledge(query)
    return results


def comprehensive_demo():
    """Comprehensive demo showing all advanced features"""
    print("=== Enhanced Autonomous Agent Comprehensive Demo ===")
    print("=" * 60)
    
    # Configure agent with all features enabled
    config = AgentConfig(
        max_workers=3,
        debug_mode=True,
        rag_enabled=True,
        selenium_enabled=True,
        cache_enabled=True,
        enable_persistence=True,
        max_browser_instances=2,
        task_timeout=60
    )
    
    # Create enhanced agent
    print("1. Initializing Enhanced Autonomous Agent...")
    agent = EnhancedAutonomousAgent(config)
    
    # Initialize additional modules
    print("2. Setting up advanced modules...")
    workflow_manager = WorkflowManager(agent)
    monitoring = MonitoringModule(agent)
    scheduler = TaskScheduler(agent)
    
    # Add knowledge to RAG system
    print("3. Populating knowledge base...")
    if agent.rag:
        knowledge_items = [
            ("Python is excellent for automation and AI development", {"category": "programming", "type": "general"}),
            ("Web scraping requires handling dynamic content and rate limits", {"category": "web", "type": "best_practices"}),
            ("Monitoring systems help prevent failures and optimize performance", {"category": "operations", "type": "monitoring"}),
            ("Task scheduling enables autonomous operation", {"category": "automation", "type": "scheduling"}),
            ("RAG systems combine retrieval and generation for better AI responses", {"category": "AI", "type": "rag"}),
            ("Job application automation requires careful handling of forms and data", {"category": "automation", "type": "job_applications"}),
            ("Selenium WebDriver is powerful for web automation", {"category": "web", "type": "selenium"}),
            ("Caching improves performance by storing frequently accessed data", {"category": "performance", "type": "caching"})
        ]
        
        for text, metadata in knowledge_items:
            agent.add_knowledge(text, metadata)
        
        print(f"   ✓ Added {len(knowledge_items)} knowledge items")
    
    # Start all components
    print("4. Starting all system components...")
    agent.start()
    monitoring.start_monitoring()
    scheduler.start_scheduler()
    
    # Register alert handlers
    monitoring.register_alert_handler("logger", lambda alert: logger.warning(f"ALERT: {alert.message}"))
    
    try:
        # Demo 1: Basic task execution
        print("\n--- Demo 1: Basic Task Execution ---")
        tasks = [
            agent.create_task("Task 1", example_task, "Hello from Task 1", priority=TaskPriority.HIGH),
            agent.create_task("Task 2", example_async_task, "Async Task", delay=2),
            agent.create_task("Task 3", example_task, "Background Task", priority=TaskPriority.LOW)
        ]
        
        for task in tasks:
            agent.schedule_task(task)
        
        print("   ✓ Scheduled 3 tasks with different priorities")
        
        # Demo 2: Knowledge queries
        print("\n--- Demo 2: Knowledge Base Queries ---")
        if agent.rag:
            queries = ["Python automation", "web scraping", "system monitoring", "job applications"]
            for query in queries:
                results = agent.query_knowledge(query)
                if results:
                    print(f"   Query: {query}")
                    for result in results[:2]:  # Show top 2 results
                        print(f"     - {result['document'][:80]}... (similarity: {result['similarity']:.2f})")
        
        # Demo 3: Workflow execution
        print("\n--- Demo 3: Workflow Management ---")
        workflow_steps = [
            {
                'name': 'analyze_job',
                'function': lambda job_url: {'url': job_url, 'analysis': 'Job analyzed successfully'},
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
            }
        ]
        
        workflow_id = workflow_manager.create_workflow("Demo Workflow", workflow_steps)
        execution_id = workflow_manager.execute_workflow(workflow_id, {"user": "demo"})
        
        print(f"   ✓ Started workflow execution: {execution_id}")
        
        # Demo 4: Scheduled tasks
        print("\n--- Demo 4: Task Scheduling ---")
        def demo_maintenance():
            return "Demo maintenance completed"
        
        # Schedule recurring task
        job_id = scheduler.schedule_recurring_task(
            "demo_maintenance", demo_maintenance, 30  # Every 30 seconds
        )
        print(f"   ✓ Scheduled maintenance job: {job_id}")
        
        # Demo 5: Web scraping
        print("\n--- Demo 5: Web Automation ---")
        if agent.web_automation:
            scraping_task = agent.create_task(
                "Web Scraping Demo",
                web_scraping_task,
                agent,
                "https://httpbin.org/html",
                description="Scrape a test webpage"
            )
            agent.schedule_task(scraping_task)
            print("   ✓ Scheduled web scraping task")
        
        # Demo 6: Data processing with caching
        print("\n--- Demo 6: Data Processing with Caching ---")
        data_tasks = [
            agent.create_task("Data Processing 1", data_processing_task, "Sample data 1"),
            agent.create_task("Data Processing 2", data_processing_task, "Sample data 2"),
            agent.create_task("Data Processing 3", data_processing_task, "Sample data 3")
        ]
        
        for task in data_tasks:
            agent.schedule_task(task)
        
        print("   ✓ Scheduled data processing tasks (will use caching)")
        
        # Demo 7: Knowledge queries as tasks
        print("\n--- Demo 7: Knowledge Queries as Tasks ---")
        if agent.rag:
            query_tasks = [
                agent.create_task("Query 1", knowledge_query_task, agent, "Python automation"),
                agent.create_task("Query 2", knowledge_query_task, agent, "web scraping best practices"),
                agent.create_task("Query 3", knowledge_query_task, agent, "system monitoring")
            ]
            
            for task in query_tasks:
                agent.schedule_task(task)
            
            print("   ✓ Scheduled knowledge query tasks")
        
        # Wait for execution and monitoring
        print("\n--- Waiting for execution (20 seconds) ---")
        time.sleep(20)
        
        # Demo 8: System monitoring
        print("\n--- Demo 8: System Monitoring ---")
        metrics = monitoring.get_metrics(5)
        if metrics:
            latest = metrics[-1]
            print(f"   CPU: {latest['cpu_percent']:.1f}%")
            print(f"   Memory: {latest['memory_percent']:.1f}%")
            print(f"   Tasks: {latest['pending_tasks']} pending, {latest['running_tasks']} running")
        
        alerts = monitoring.get_alerts()
        print(f"   Alerts: {len(alerts)} total")
        
        # Show system health
        health = monitoring.get_system_health()
        print(f"   System Health: {health['status']}")
        if health['issues']:
            print(f"   Issues: {', '.join(health['issues'])}")
        
        # Demo 9: Final status and results
        print("\n--- Demo 9: Final Status ---")
        status = agent.get_status()
        print(f"   Agent Status: {status['is_running']}")
        print(f"   Pending Tasks: {status['pending_tasks']}")
        print(f"   Running Tasks: {status['running_tasks']}")
        print(f"   Completed Tasks: {status['completed_tasks']}")
        
        # Show completed tasks
        print(f"\n   Completed Tasks: {len(agent.completed_tasks)}")
        for task_id, task in list(agent.completed_tasks.items())[:5]:  # Show first 5
            print(f"     - {task.name}: {task.status.value}")
            if task.result:
                if isinstance(task.result, str):
                    print(f"       Result: {task.result[:50]}...")
                else:
                    print(f"       Result: {type(task.result).__name__}")
            if task.error:
                print(f"       Error: {task.error}")
        
        # Show workflow status
        workflow_status = workflow_manager.get_workflow_status(execution_id)
        print(f"\n   Workflow Status: {workflow_status.get('status', 'unknown')}")
        if workflow_status.get('step_results'):
            print(f"   Completed Steps: {len(workflow_status['step_results'])}")
        
        # Show scheduled jobs
        jobs = scheduler.get_jobs()
        print(f"\n   Scheduled Jobs: {len(jobs)}")
        for job in jobs:
            print(f"     - {job['name']}: {job['schedule_type']} (active: {job['active']})")
        
        # Show cache statistics
        if agent.cache:
            print(f"\n   Cache Status: Enabled")
            # Note: Cache statistics would need to be added to the cache module
        
        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("The enhanced autonomous agent demonstrated:")
        print("✓ RAG-powered knowledge management")
        print("✓ Web automation with Selenium")
        print("✓ Task scheduling and queuing")
        print("✓ Workflow orchestration")
        print("✓ System monitoring and alerting")
        print("✓ Performance caching")
        print("✓ Multi-threading and async support")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    
    except Exception as e:
        print(f"Demo error: {e}")
        logger.error(f"Demo error: {e}", exc_info=True)
    
    finally:
        # Cleanup
        print("\n--- Cleanup ---")
        scheduler.stop_scheduler()
        monitoring.stop_monitoring()
        agent.stop()
        print("All components stopped successfully")


def quick_demo():
    """Quick demo for testing basic functionality"""
    print("=== Quick Enhanced Agent Demo ===")
    
    # Simple configuration
    config = AgentConfig(
        max_workers=2,
        debug_mode=True,
        rag_enabled=True,
        selenium_enabled=False,  # Disable for quick demo
        cache_enabled=True
    )
    
    # Create agent
    agent = EnhancedAutonomousAgent(config)
    
    # Add some knowledge
    if agent.rag:
        agent.add_knowledge("Python is a versatile programming language.", {"topic": "programming"})
        agent.add_knowledge("Automation saves time and reduces errors.", {"topic": "automation"})
    
    # Start agent
    agent.start()
    
    try:
        # Create simple tasks
        tasks = [
            agent.create_task("Quick Task 1", example_task, "Hello World"),
            agent.create_task("Quick Task 2", example_task, "Test Message", delay=1)
        ]
        
        for task in tasks:
            agent.schedule_task(task)
        
        # Query knowledge
        if agent.rag:
            results = agent.query_knowledge("Python")
            print(f"Knowledge query results: {len(results)} found")
        
        # Wait for completion
        time.sleep(3)
        
        # Show results
        print(f"Completed tasks: {len(agent.completed_tasks)}")
        for task_id, task in agent.completed_tasks.items():
            print(f"  - {task.name}: {task.result}")
    
    finally:
        agent.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Autonomous Agent Demo")
    parser.add_argument("--quick", action="store_true", help="Run quick demo instead of comprehensive demo")
    
    args = parser.parse_args()
    
    if args.quick:
        quick_demo()
    else:
        comprehensive_demo()
