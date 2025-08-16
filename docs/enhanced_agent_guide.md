# Enhanced Autonomous Agent Guide

## Overview

The Enhanced Autonomous Agent is a comprehensive system that combines RAG (Retrieval-Augmented Generation), web automation, task scheduling, workflow management, and system monitoring to create a powerful autonomous agent for job application automation and other complex tasks.

## Features

### Core Features
- **RAG System**: Knowledge management with vector search and semantic retrieval
- **Web Automation**: Selenium-based web scraping and form filling
- **Task Scheduling**: Priority-based task queuing with retry mechanisms
- **Workflow Management**: Complex task orchestration with dependencies
- **System Monitoring**: Real-time metrics and alerting
- **Caching**: Performance optimization with Redis and local caching
- **Multi-threading**: Concurrent task execution
- **Persistence**: Database storage for tasks and agent memory

### Advanced Features
- **Async Support**: Both sync and async task execution
- **Priority Queuing**: 5-level priority system (Critical, High, Normal, Low, Background)
- **Retry Logic**: Automatic retry with exponential backoff
- **Conditional Execution**: Workflow steps with conditional logic
- **Alert Handlers**: Customizable alert handling (email, Slack, etc.)
- **Cron-like Scheduling**: Advanced task scheduling with cron expressions

## Quick Start

### Basic Usage

```python
from core.enhanced_agent import EnhancedAutonomousAgent, AgentConfig, TaskPriority

# Configure the agent
config = AgentConfig(
    max_workers=4,
    rag_enabled=True,
    selenium_enabled=True,
    cache_enabled=True
)

# Create agent
agent = EnhancedAutonomousAgent(config)

# Start the agent
agent.start()

# Create and schedule tasks
task = agent.create_task(
    name="Example Task",
    function=lambda x: f"Processed: {x}",
    "Hello World",
    priority=TaskPriority.HIGH
)

agent.schedule_task(task)

# Stop the agent
agent.stop()
```

### RAG Knowledge Management

```python
# Add knowledge to the system
agent.add_knowledge(
    "Python is excellent for automation tasks",
    {"category": "programming", "type": "best_practices"}
)

# Query knowledge base
results = agent.query_knowledge("Python automation")
for result in results:
    print(f"Document: {result['document']}")
    print(f"Similarity: {result['similarity']:.2f}")
```

### Web Automation

```python
# Scrape a webpage
result = agent.web_scrape(
    "https://example.com",
    selectors={"title": "h1", "content": ".main-content"}
)

print(f"Title: {result['extracted']['title']}")
print(f"Content: {result['extracted']['content']}")
```

## Advanced Usage

### Workflow Management

```python
from core.workflow_manager import WorkflowManager

# Create workflow manager
workflow_manager = WorkflowManager(agent)

# Define workflow steps
steps = [
    {
        'name': 'analyze_job',
        'function': analyze_job_posting,
        'description': 'Analyze job posting',
        'priority': TaskPriority.HIGH
    },
    {
        'name': 'prepare_resume',
        'function': prepare_resume,
        'dependencies': ['analyze_job'],
        'description': 'Prepare tailored resume'
    },
    {
        'name': 'submit_application',
        'function': submit_application,
        'dependencies': ['prepare_resume'],
        'condition': 'context.get("resume_ready") == True'
    }
]

# Create and execute workflow
workflow_id = workflow_manager.create_workflow("Job Application", steps)
execution_id = workflow_manager.execute_workflow(workflow_id, {"job_url": "..."})

# Check status
status = workflow_manager.get_workflow_status(execution_id)
print(f"Workflow status: {status['status']}")
```

### Task Scheduling

```python
from core.scheduler import TaskScheduler

# Create scheduler
scheduler = TaskScheduler(agent)
scheduler.start_scheduler()

# Schedule recurring task
job_id = scheduler.schedule_recurring_task(
    "maintenance",
    maintenance_function,
    3600  # Every hour
)

# Schedule cron task
cron_job_id = scheduler.schedule_cron_task(
    "daily_backup",
    backup_function,
    "0 2 * * *"  # Daily at 2 AM
)

# Schedule one-time task
one_time_job_id = scheduler.schedule_one_time_task(
    "special_task",
    special_function,
    datetime.now() + timedelta(hours=1)
)
```

### System Monitoring

```python
from core.monitoring import MonitoringModule, AlertSeverity

# Create monitoring module
monitoring = MonitoringModule(agent)
monitoring.start_monitoring()

# Register alert handlers
def email_alert_handler(alert):
    if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.ERROR]:
        send_email_alert(alert.message)

monitoring.register_alert_handler("email", email_alert_handler)

# Get system health
health = monitoring.get_system_health()
print(f"System status: {health['status']}")

# Get metrics
metrics = monitoring.get_metrics(10)  # Last 10 measurements
for metric in metrics:
    print(f"CPU: {metric['cpu_percent']}%, Memory: {metric['memory_percent']}%")
```

## Configuration

### AgentConfig Options

```python
config = AgentConfig(
    # Core settings
    max_iterations=100,
    task_timeout=300,
    debug_mode=True,
    
    # RAG settings
    rag_enabled=True,
    vector_db_path="./vector_db",
    embedding_model="all-MiniLM-L6-v2",
    max_retrieval_results=5,
    similarity_threshold=0.7,
    
    # Web automation settings
    selenium_enabled=True,
    headless_browser=True,
    browser_timeout=30,
    max_browser_instances=3,
    
    # Performance settings
    cache_enabled=True,
    cache_ttl=3600,
    max_workers=4,
    memory_limit_mb=1024,
    
    # Database settings
    db_path="./agent_data.db",
    enable_persistence=True,
    
    # Redis settings
    redis_host="localhost",
    redis_port=6379,
    redis_db=0,
    
    # Task queue settings
    task_queue_size=1000,
    priority_levels=5
)
```

## Task Priorities

- **CRITICAL (1)**: Must be executed immediately
- **HIGH (2)**: Important tasks that should be prioritized
- **NORMAL (3)**: Standard tasks (default)
- **LOW (4)**: Background tasks with lower priority
- **BACKGROUND (5)**: Non-urgent tasks

## Error Handling

The agent includes comprehensive error handling:

- **Automatic Retries**: Failed tasks are automatically retried up to 3 times
- **Exponential Backoff**: Retry delays increase with each attempt
- **Error Logging**: All errors are logged with full context
- **Graceful Degradation**: Individual module failures don't crash the system

## Performance Optimization

### Caching
- **Redis Cache**: Distributed caching for multi-instance deployments
- **Local Cache**: Fallback caching when Redis is unavailable
- **TTL Support**: Automatic cache expiration
- **Task Result Caching**: Cache task results to avoid recomputation

### Multi-threading
- **Worker Threads**: Configurable number of worker threads
- **Thread Pool**: Efficient thread management
- **Async Support**: Native async/await support for I/O-bound tasks

## Monitoring and Alerting

### Metrics Collected
- CPU usage percentage
- Memory usage and available memory
- Disk usage
- Task queue size and processing rates
- Agent status and module health

### Alert Types
- **High CPU Usage**: When CPU exceeds thresholds
- **High Memory Usage**: When memory usage is critical
- **Disk Space**: When disk usage is high
- **Task Queue Full**: When task queue is overloaded
- **Agent Stopped**: When agent is not running

### Alert Severities
- **INFO**: Informational messages
- **WARNING**: Issues that need attention
- **ERROR**: Problems that affect functionality
- **CRITICAL**: System-threatening issues

## Best Practices

### Task Design
1. **Keep tasks focused**: Each task should do one thing well
2. **Handle errors gracefully**: Always include proper error handling
3. **Use appropriate priorities**: Don't overuse HIGH/CRITICAL priorities
4. **Add descriptions**: Helpful for debugging and monitoring

### Workflow Design
1. **Plan dependencies carefully**: Ensure logical task ordering
2. **Use conditions sparingly**: Complex conditions can be hard to debug
3. **Monitor workflow execution**: Check status regularly
4. **Handle failures**: Plan for workflow step failures

### Performance
1. **Use caching**: Cache expensive operations
2. **Optimize database queries**: Minimize database calls
3. **Monitor resource usage**: Watch CPU, memory, and disk usage
4. **Scale appropriately**: Adjust worker count based on load

### Security
1. **Validate inputs**: Always validate task parameters
2. **Use secure connections**: Use HTTPS for web scraping
3. **Limit permissions**: Run with minimal required permissions
4. **Monitor access**: Log all system access

## Troubleshooting

### Common Issues

**Agent won't start**
- Check if required dependencies are installed
- Verify configuration settings
- Check log files for error messages

**Tasks not executing**
- Verify agent is running (`agent.is_running`)
- Check task queue size
- Review task priorities and dependencies

**RAG not working**
- Ensure ChromaDB is properly initialized
- Check embedding model availability
- Verify vector database path permissions

**Web automation failing**
- Check Selenium/Chrome installation
- Verify browser driver compatibility
- Review website accessibility

**High memory usage**
- Reduce `max_workers` setting
- Enable caching to reduce recomputation
- Monitor task complexity and duration

### Debug Mode

Enable debug mode for detailed logging:

```python
config = AgentConfig(debug_mode=True)
```

### Logging

The agent uses structured logging. Check logs for:
- Task execution details
- Error messages and stack traces
- Performance metrics
- System health information

## Integration Examples

### Job Application Automation

```python
def create_job_application_agent():
    config = AgentConfig(
        max_workers=3,
        rag_enabled=True,
        selenium_enabled=True,
        cache_enabled=True
    )
    
    agent = EnhancedAutonomousAgent(config)
    
    # Add job application knowledge
    agent.add_knowledge("Resume should highlight relevant skills", {"type": "resume"})
    agent.add_knowledge("Cover letters should be personalized", {"type": "cover_letter"})
    
    # Create workflow
    workflow_manager = WorkflowManager(agent)
    workflow_id = create_job_application_workflow(agent)
    
    return agent, workflow_manager, workflow_id
```

### Data Processing Pipeline

```python
def create_data_processing_agent():
    config = AgentConfig(
        max_workers=4,
        rag_enabled=True,
        cache_enabled=True
    )
    
    agent = EnhancedAutonomousAgent(config)
    
    # Schedule data processing tasks
    scheduler = TaskScheduler(agent)
    scheduler.schedule_recurring_task("data_extraction", extract_data, 3600)
    scheduler.schedule_recurring_task("data_cleaning", clean_data, 7200)
    scheduler.schedule_cron_task("daily_report", generate_report, "0 6 * * *")
    
    return agent, scheduler
```

## API Reference

### EnhancedAutonomousAgent

#### Methods
- `start()`: Start the agent
- `stop()`: Stop the agent
- `create_task(name, function, *args, **kwargs)`: Create a new task
- `schedule_task(task)`: Schedule a task for execution
- `add_knowledge(text, metadata)`: Add knowledge to RAG system
- `query_knowledge(query)`: Query knowledge base
- `web_scrape(url, selectors)`: Scrape a webpage
- `get_status()`: Get agent status

### WorkflowManager

#### Methods
- `create_workflow(name, steps)`: Create a workflow
- `execute_workflow(workflow_id, context)`: Execute a workflow
- `get_workflow_status(execution_id)`: Get workflow status
- `cancel_workflow(execution_id)`: Cancel a workflow

### TaskScheduler

#### Methods
- `schedule_recurring_task(name, function, interval)`: Schedule recurring task
- `schedule_cron_task(name, function, cron_expression)`: Schedule cron task
- `schedule_one_time_task(name, function, scheduled_time)`: Schedule one-time task
- `cancel_job(job_id)`: Cancel a scheduled job
- `get_jobs()`: Get all scheduled jobs

### MonitoringModule

#### Methods
- `start_monitoring()`: Start system monitoring
- `stop_monitoring()`: Stop system monitoring
- `get_metrics(last_n)`: Get recent metrics
- `get_alerts(severity, acknowledged)`: Get alerts
- `get_system_health()`: Get overall system health
- `register_alert_handler(name, handler)`: Register alert handler

## Contributing

When contributing to the enhanced autonomous agent:

1. Follow the existing code style
2. Add comprehensive tests
3. Update documentation
4. Include error handling
5. Consider performance implications
6. Add logging for debugging

## License

This enhanced autonomous agent is part of the Autonomous Job Applying Bot project and follows the same licensing terms.
