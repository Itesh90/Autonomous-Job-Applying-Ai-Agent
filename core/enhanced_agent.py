"""
Enhanced Autonomous Agent with RAG, Selenium, and Advanced Modules
=================================================================

A comprehensive autonomous agent system with:
- RAG (Retrieval-Augmented Generation) for knowledge management
- Selenium for web automation
- Caching for performance optimization
- Task scheduling and queuing
- Memory management and persistence
- Multi-threading support
"""

import asyncio
import json
import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from queue import Queue, PriorityQueue
import hashlib
import pickle
import os

# Third-party imports
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, WebDriverException
except ImportError:
    print("Selenium not installed. Run: pip install selenium")

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ChromaDB/SentenceTransformers not installed. Run: pip install chromadb sentence-transformers")

try:
    import redis
except ImportError:
    print("Redis not installed. Run: pip install redis")

try:
    from celery import Celery
except ImportError:
    print("Celery not installed. Run: pip install celery")

# Project imports
from config.settings import settings
from utils.logger import get_logger
from rag.vector_store import VectorStore
from models.database import get_session, Candidate, Job, Application

logger = get_logger(__name__)


# Enhanced Configuration
@dataclass
class AgentConfig:
    """Enhanced configuration for the autonomous agent"""
    # Core settings
    max_iterations: int = 100
    task_timeout: int = 300
    debug_mode: bool = True
    
    # RAG settings
    rag_enabled: bool = True
    vector_db_path: str = "./vector_db"
    embedding_model: str = "all-MiniLM-L6-v2"
    max_retrieval_results: int = 5
    similarity_threshold: float = 0.7
    
    # Web automation settings
    selenium_enabled: bool = True
    headless_browser: bool = True
    browser_timeout: int = 30
    max_browser_instances: int = 3
    
    # Performance settings
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour
    max_workers: int = 4
    memory_limit_mb: int = 1024
    
    # Database settings
    db_path: str = "./agent_data.db"
    enable_persistence: bool = True
    
    # Redis settings (for distributed caching)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Task queue settings
    task_queue_size: int = 1000
    priority_levels: int = 5


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Enhanced task representation"""
    id: str
    name: str
    description: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        return self.priority.value < other.priority.value


class RAGModule:
    """Retrieval-Augmented Generation module for knowledge management"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.vector_store = None
        self.setup_rag()
    
    def setup_rag(self):
        """Initialize RAG components"""
        try:
            # Use existing vector store from the project
            self.vector_store = VectorStore()
            logger.info("RAG module initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG module: {e}")
            self.config.rag_enabled = False
    
    def add_knowledge(self, text: str, metadata: Dict[str, Any] = None, doc_id: str = None) -> bool:
        """Add knowledge to the vector database"""
        if not self.config.rag_enabled or not self.vector_store:
            return False
        
        try:
            # Use the existing vector store's knowledge collection
            knowledge_type = metadata.get('type', 'general') if metadata else 'general'
            self.vector_store.add_knowledge(knowledge_type, text, metadata)
            logger.info(f"Added knowledge document: {knowledge_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return False
    
    def retrieve_knowledge(self, query: str, n_results: int = None) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge based on query"""
        if not self.config.rag_enabled or not self.vector_store:
            return []
        
        try:
            n_results = n_results or self.config.max_retrieval_results
            
            # Use existing vector store's search functionality for knowledge collection
            query_embedding = self.vector_store.embedding_model.encode([query]).tolist()
            
            # Search in knowledge collection
            results = self.vector_store.collections['knowledge'].query(
                query_embeddings=query_embedding,
                n_results=n_results
            )
            
            # Filter by similarity threshold
            filtered_results = []
            for i in range(len(results['documents'][0])):
                score = 1 - results['distances'][0][i]  # Convert distance to similarity
                if score >= self.config.similarity_threshold:
                    filtered_results.append({
                        'document': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'similarity': score
                    })
            
            logger.info(f"Retrieved {len(filtered_results)} relevant documents for query: {query}")
            return filtered_results
        except Exception as e:
            logger.error(f"Failed to retrieve knowledge: {e}")
            return []


class WebAutomationModule:
    """Selenium-based web automation module"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.driver_pool = Queue(maxsize=config.max_browser_instances)
        self.active_drivers = []
        self.setup_drivers()
    
    def setup_drivers(self):
        """Initialize browser drivers"""
        if not self.config.selenium_enabled:
            return
        
        try:
            for _ in range(self.config.max_browser_instances):
                driver = self._create_driver()
                self.driver_pool.put(driver)
                self.active_drivers.append(driver)
            
            logger.info(f"Initialized {self.config.max_browser_instances} browser instances")
        except Exception as e:
            logger.error(f"Failed to initialize browser drivers: {e}")
            self.config.selenium_enabled = False
    
    def _create_driver(self):
        """Create a new WebDriver instance"""
        options = Options()
        if self.config.headless_browser:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(self.config.browser_timeout)
        return driver
    
    def get_driver(self):
        """Get a driver from the pool"""
        if not self.config.selenium_enabled:
            return None
        return self.driver_pool.get()
    
    def return_driver(self, driver):
        """Return a driver to the pool"""
        if driver and self.config.selenium_enabled:
            self.driver_pool.put(driver)
    
    def scrape_page(self, url: str, selectors: Dict[str, str] = None) -> Dict[str, Any]:
        """Scrape a web page"""
        driver = self.get_driver()
        if not driver:
            return {'error': 'Web automation not available'}
        
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            result = {
                'url': url,
                'title': driver.title,
                'content': driver.page_source,
                'timestamp': datetime.now().isoformat()
            }
            
            # Extract specific elements if selectors provided
            if selectors:
                result['extracted'] = {}
                for key, selector in selectors.items():
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        result['extracted'][key] = element.text
                    except:
                        result['extracted'][key] = None
            
            return result
        except Exception as e:
            return {'error': str(e), 'url': url}
        finally:
            self.return_driver(driver)
    
    def cleanup(self):
        """Clean up all browser instances"""
        for driver in self.active_drivers:
            try:
                driver.quit()
            except:
                pass
        self.active_drivers.clear()


class CacheModule:
    """Caching module for performance optimization"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.local_cache = {}
        self.redis_client = None
        self.setup_cache()
    
    def setup_cache(self):
        """Initialize caching systems"""
        if not self.config.cache_enabled:
            return
        
        # Try to connect to Redis for distributed caching
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis not available, using local cache only: {e}")
            self.redis_client = None
    
    def get(self, key: str) -> Any:
        """Get value from cache"""
        if not self.config.cache_enabled:
            return None
        
        # Try Redis first
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    return pickle.loads(value.encode('latin-1'))
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        # Fall back to local cache
        cache_entry = self.local_cache.get(key)
        if cache_entry:
            if cache_entry['expires'] > datetime.now():
                return cache_entry['value']
            else:
                del self.local_cache[key]
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        if not self.config.cache_enabled:
            return False
        
        ttl = ttl or self.config.cache_ttl
        
        # Try Redis first
        if self.redis_client:
            try:
                serialized = pickle.dumps(value).decode('latin-1')
                self.redis_client.setex(key, ttl, serialized)
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        
        # Fall back to local cache
        self.local_cache[key] = {
            'value': value,
            'expires': datetime.now() + timedelta(seconds=ttl)
        }
        return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.config.cache_enabled:
            return False
        
        deleted = False
        
        # Try Redis
        if self.redis_client:
            try:
                deleted = bool(self.redis_client.delete(key))
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
        
        # Local cache
        if key in self.local_cache:
            del self.local_cache[key]
            deleted = True
        
        return deleted
    
    def clear(self):
        """Clear all cache"""
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                logger.error(f"Redis clear error: {e}")
        
        self.local_cache.clear()


class DatabaseModule:
    """Database module for persistent storage"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.conn = None
        self.setup_database()
    
    def setup_database(self):
        """Initialize database"""
        if not self.config.enable_persistence:
            return
        
        try:
            Path(self.config.db_path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.config.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            
            # Create tables
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    priority INTEGER,
                    status TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    error TEXT,
                    metadata TEXT
                )
            """)
            
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    timestamp TEXT,
                    ttl INTEGER
                )
            """)
            
            self.conn.commit()
            logger.info("Agent database initialized")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            self.config.enable_persistence = False
    
    def save_task(self, task: Task):
        """Save task to database"""
        if not self.config.enable_persistence or not self.conn:
            return
        
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO agent_tasks 
                (id, name, description, priority, status, created_at, result, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id, task.name, task.description, task.priority.value,
                task.status.value, task.created_at.isoformat(),
                json.dumps(task.result) if task.result else None,
                task.error, json.dumps(task.metadata)
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save task: {e}")
    
    def load_task(self, task_id: str) -> Optional[Task]:
        """Load task from database"""
        if not self.config.enable_persistence or not self.conn:
            return None
        
        try:
            cursor = self.conn.execute("SELECT * FROM agent_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                # Reconstruct task (simplified)
                return Task(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    function=lambda: None,  # Function not serializable
                    priority=TaskPriority(row['priority']),
                    status=TaskStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    result=json.loads(row['result']) if row['result'] else None,
                    error=row['error'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
        except Exception as e:
            logger.error(f"Failed to load task: {e}")
        
        return None
    
    def save_memory(self, key: str, value: Any, ttl: int = None):
        """Save to agent memory"""
        if not self.config.enable_persistence or not self.conn:
            return
        
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO agent_memory (key, value, timestamp, ttl)
                VALUES (?, ?, ?, ?)
            """, (key, json.dumps(value), datetime.now().isoformat(), ttl))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def load_memory(self, key: str) -> Any:
        """Load from agent memory"""
        if not self.config.enable_persistence or not self.conn:
            return None
        
        try:
            cursor = self.conn.execute(
                "SELECT value, timestamp, ttl FROM agent_memory WHERE key = ?", 
                (key,)
            )
            row = cursor.fetchone()
            if row:
                # Check if expired
                if row['ttl']:
                    created = datetime.fromisoformat(row['timestamp'])
                    if datetime.now() > created + timedelta(seconds=row['ttl']):
                        self.conn.execute("DELETE FROM agent_memory WHERE key = ?", (key,))
                        self.conn.commit()
                        return None
                
                return json.loads(row['value'])
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
        
        return None


class EnhancedAutonomousAgent:
    """Enhanced autonomous agent with RAG, web automation, and advanced features"""
    
    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig()
        self.task_queue = PriorityQueue(maxsize=self.config.task_queue_size)
        self.completed_tasks = {}
        self.running_tasks = {}
        self.is_running = False
        self.worker_threads = []
        
        # Initialize modules
        self.rag = RAGModule(self.config) if self.config.rag_enabled else None
        self.web_automation = WebAutomationModule(self.config) if self.config.selenium_enabled else None
        self.cache = CacheModule(self.config) if self.config.cache_enabled else None
        self.database = DatabaseModule(self.config) if self.config.enable_persistence else None
        
        # Thread pool for concurrent task execution
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        
        logger.info("Enhanced Autonomous Agent initialized")
    
    def add_knowledge(self, text: str, metadata: Dict[str, Any] = None) -> bool:
        """Add knowledge to RAG system"""
        if self.rag:
            return self.rag.add_knowledge(text, metadata)
        return False
    
    def query_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """Query knowledge base"""
        if self.rag:
            return self.rag.retrieve_knowledge(query)
        return []
    
    def create_task(self, name: str, function: Callable, *args, 
                   priority: TaskPriority = TaskPriority.NORMAL,
                   description: str = "", timeout: int = None,
                   scheduled_at: datetime = None, **kwargs) -> Task:
        """Create a new task"""
        task_id = hashlib.md5(f"{name}_{datetime.now()}".encode()).hexdigest()
        
        task = Task(
            id=task_id,
            name=name,
            description=description,
            function=function,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout or self.config.task_timeout,
            scheduled_at=scheduled_at
        )
        
        return task
    
    def schedule_task(self, task: Task) -> bool:
        """Schedule a task for execution"""
        try:
            # Check if task should be scheduled for later
            if task.scheduled_at and task.scheduled_at > datetime.now():
                # For simplicity, we'll just add to queue anyway
                # In production, you'd use a scheduler like Celery
                pass
            
            self.task_queue.put(task)
            logger.info(f"Scheduled task: {task.name} (ID: {task.id})")
            
            # Save to database if persistence enabled
            if self.database:
                self.database.save_task(task)
            
            return True
        except Exception as e:
            logger.error(f"Failed to schedule task: {e}")
            return False
    
    def execute_task(self, task: Task) -> Any:
        """Execute a single task"""
        task.status = TaskStatus.RUNNING
        self.running_tasks[task.id] = task
        start_time = datetime.now()
        
        try:
            logger.info(f"Executing task: {task.name}")
            
            # Check cache first
            cache_key = f"task_result_{task.id}"
            if self.cache:
                cached_result = self.cache.get(cache_key)
                if cached_result:
                    logger.info(f"Retrieved cached result for task: {task.name}")
                    task.result = cached_result
                    task.status = TaskStatus.COMPLETED
                    return cached_result
            
            # Query RAG for context if available
            context = []
            if self.rag and task.description:
                context = self.rag.retrieve_knowledge(task.description)
                if context:
                    logger.info(f"Retrieved {len(context)} context documents for task")
            
            # Execute task function
            if asyncio.iscoroutinefunction(task.function):
                # Handle async functions
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(
                            task.function(*task.args, **task.kwargs),
                            timeout=task.timeout
                        )
                    )
                finally:
                    loop.close()
            else:
                # Handle sync functions
                result = task.function(*task.args, **task.kwargs)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            
            # Cache result
            if self.cache and result:
                self.cache.set(cache_key, result)
            
            # Update database
            if self.database:
                self.database.save_task(task)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Task completed: {task.name} (took {execution_time:.2f}s)")
            
            return result
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.retry_count += 1
            
            logger.error(f"Task failed: {task.name} - {e}")
            
            # Retry if possible
            if task.retry_count <= task.max_retries:
                logger.info(f"Retrying task: {task.name} (attempt {task.retry_count})")
                task.status = TaskStatus.PENDING
                self.task_queue.put(task)
            
            # Update database
            if self.database:
                self.database.save_task(task)
            
            return None
        
        finally:
            if task.id in self.running_tasks:
                del self.running_tasks[task.id]
            self.completed_tasks[task.id] = task
    
    def worker_loop(self):
        """Main worker loop for processing tasks"""
        while self.is_running:
            try:
                task = self.task_queue.get(timeout=1)
                if task:
                    self.execute_task(task)
                    self.task_queue.task_done()
            except Exception as e:
                if self.is_running:  # Only log if we're still supposed to be running
                    logger.error(f"Worker error: {e}")
                time.sleep(0.1)
    
    def start(self):
        """Start the agent"""
        if self.is_running:
            logger.warning("Agent is already running")
            return
        
        self.is_running = True
        
        # Start worker threads
        for i in range(self.config.max_workers):
            thread = threading.Thread(target=self.worker_loop, name=f"Worker-{i}")
            thread.daemon = True
            thread.start()
            self.worker_threads.append(thread)
        
        logger.info(f"Agent started with {self.config.max_workers} workers")
    
    def stop(self):
        """Stop the agent"""
        if not self.is_running:
            logger.warning("Agent is not running")
            return
        
        logger.info("Stopping agent...")
        self.is_running = False
        
        # Wait for tasks to complete
        self.task_queue.join()
        
        # Wait for worker threads
        for thread in self.worker_threads:
            thread.join(timeout=5)
        
        # Cleanup modules
        if self.web_automation:
            self.web_automation.cleanup()
        
        if self.executor:
            self.executor.shutdown(wait=True)
        
        logger.info("Agent stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            'is_running': self.is_running,
            'pending_tasks': self.task_queue.qsize(),
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'modules': {
                'rag_enabled': bool(self.rag),
                'web_automation_enabled': bool(self.web_automation),
                'cache_enabled': bool(self.cache),
                'database_enabled': bool(self.database)
            }
        }
    
    def web_scrape(self, url: str, selectors: Dict[str, str] = None) -> Dict[str, Any]:
        """Convenience method for web scraping"""
        if self.web_automation:
            return self.web_automation.scrape_page(url, selectors)
        return {'error': 'Web automation not enabled'}


# Example usage and demo functions
def example_task(message: str, delay: int = 1) -> str:
    """Example task function"""
    time.sleep(delay)
    return f"Task completed: {message}"


async def example_async_task(message: str, delay: int = 1) -> str:
    """Example async task function"""
    await asyncio.sleep(delay)
    return f"Async task completed: {message}"


def web_search_task(agent: EnhancedAutonomousAgent, query: str) -> Dict[str, Any]:
    """Example web search task"""
    # This would integrate with search APIs or web scraping
    result = agent.web_scrape("https://www.google.com/search", {"query": query})
    return result


def demo_agent():
    """Demonstrate the enhanced autonomous agent"""
    print("=== Enhanced Autonomous Agent Demo ===")
    
    # Configure agent
    config = AgentConfig(
        max_workers=2,
        debug_mode=True,
        rag_enabled=True,
        selenium_enabled=True,
        cache_enabled=True
    )
    
    # Create agent
    agent = EnhancedAutonomousAgent(config)
    
    # Add some knowledge to RAG
    if agent.rag:
        agent.add_knowledge("Python is a programming language known for its simplicity.", {"topic": "programming"})
        agent.add_knowledge("Machine learning is a subset of artificial intelligence.", {"topic": "AI"})
        agent.add_knowledge("Web scraping involves extracting data from websites.", {"topic": "web"})
    
    # Start agent
    agent.start()
    
    try:
        # Create and schedule tasks
        tasks = [
            agent.create_task("Simple Task 1", example_task, "Hello World", priority=TaskPriority.HIGH),
            agent.create_task("Simple Task 2", example_task, "Test Message", delay=2),
            agent.create_task("Async Task", example_async_task, "Async Hello", delay=1),
        ]
        
        for task in tasks:
            agent.schedule_task(task)
        
        # Query knowledge base
        if agent.rag:
            print("\n--- Knowledge Base Query ---")
            results = agent.query_knowledge("What is Python?")
            for result in results:
                print(f"Similarity: {result['similarity']:.2f}")
                print(f"Content: {result['document']}")
                print(f"Metadata: {result['metadata']}")
                print()
        
        # Wait a bit for tasks to complete
        time.sleep(5)
        
        # Show status
        print("\n--- Agent Status ---")
        status = agent.get_status()
        for key, value in status.items():
            print(f"{key}: {value}")
        
        # Show completed tasks
        print("\n--- Completed Tasks ---")
        for task_id, task in agent.completed_tasks.items():
            print(f"Task: {task.name}")
            print(f"Status: {task.status.value}")
            print(f"Result: {task.result}")
            if task.error:
                print(f"Error: {task.error}")
            print()
    
    finally:
        # Stop agent
        agent.stop()


if __name__ == "__main__":
    demo_agent()
