"""
Advanced job scraping module with Selenium, anti-detection, and rate limiting
"""
import asyncio
import random
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import json
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from seleniumwire import webdriver as wire_webdriver
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import cloudscraper
from fake_useragent import UserAgent

from config.settings import settings
from models.database import Job, JobStatus, get_session
from utils.logger import get_logger
from llm.provider_manager import generate_structured_response

logger = get_logger(__name__)

class RateLimiter:
    """Domain-specific rate limiting"""
    
    def __init__(self):
        self.domain_last_access = {}
        self.domain_delays = {
            'linkedin.com': 5,
            'indeed.com': 3,
            'greenhouse.io': 4,
            'lever.co': 3,
            'workable.com': 3,
            'default': settings.rate_limit_delay
        }
    
    async def wait_if_needed(self, url: str):
        """Wait if rate limit requires it"""
        domain = urlparse(url).netloc
        last_access = self.domain_last_access.get(domain, 0)
        delay = self.domain_delays.get(domain, self.domain_delays['default'])
        
        time_since = time.time() - last_access
        if time_since < delay:
            wait_time = delay - time_since + random.uniform(0.5, 1.5)
            logger.info(f"Rate limiting: waiting {wait_time:.1f}s for {domain}")
            await asyncio.sleep(wait_time)
        
        self.domain_last_access[domain] = time.time()

class BrowserManager:
    """Manages browser instances with anti-detection"""
    
    def __init__(self, use_undetected: bool = True, headless: bool = False):
        self.use_undetected = use_undetected and settings.use_undetected_chrome
        self.headless = headless or settings.headless_browser
        self.ua = UserAgent()
        self.driver = None
    
    def create_driver(self) -> webdriver.Chrome:
        """Create browser driver with anti-detection measures"""
        if self.use_undetected:
            return self._create_undetected_driver()
        else:
            return self._create_standard_driver()
    
    def _create_undetected_driver(self) -> uc.Chrome:
        """Create undetected Chrome driver"""
        options = uc.ChromeOptions()
        
        # Anti-detection options
        options.add_argument(f'--user-agent={self.ua.random}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Performance options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        if self.headless:
            options.add_argument('--headless=new')
        
        # Additional privacy options
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
            'profile.managed_default_content_settings.images': 2  # Block images for speed
        }
        options.add_experimental_option('prefs', prefs)
        
        driver = uc.Chrome(options=options, version_main=None)
        
        # Execute anti-detection scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.ua.random})
        
        return driver
    
    def _create_standard_driver(self) -> webdriver.Chrome:
        """Create standard Chrome driver with Selenium Wire for network interception"""
        options = Options()
        
        options.add_argument(f'--user-agent={self.ua.random}')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        if self.headless:
            options.add_argument('--headless')
        
        # Selenium Wire options for network interception
        seleniumwire_options = {
            'disable_capture': False,
            'request_storage': 'memory',
            'request_storage_max_size': 100
        }
        
        driver = wire_webdriver.Chrome(
            options=options,
            seleniumwire_options=seleniumwire_options
        )
        
        return driver
    
    def human_like_scroll(self, driver: webdriver.Chrome):
        """Simulate human-like scrolling"""
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        
        current_position = 0
        while current_position < total_height:
            scroll_distance = random.randint(300, 700)
            driver.execute_script(f"window.scrollTo(0, {current_position + scroll_distance});")
            current_position += scroll_distance
            time.sleep(random.uniform(0.5, 1.5))
    
    def random_mouse_movement(self, driver: webdriver.Chrome):
        """Simulate random mouse movements"""
        action = ActionChains(driver)
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            action.move_by_offset(x, y)
            action.pause(random.uniform(0.1, 0.3))
        action.perform()
    
    def close(self):
        """Close browser driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None

class JobScraper:
    """Main job scraping orchestrator"""
    
    def __init__(self):
        self.browser_manager = BrowserManager()
        self.rate_limiter = RateLimiter()
        self.session = get_session()
        self.scraped_urls = set()
    
    async def scrape_jobs(self, 
                         sources: List[str] = None,
                         keywords: List[str] = None,
                         locations: List[str] = None,
                         max_jobs: int = 50) -> List[Job]:
        """Scrape jobs from multiple sources"""
        
        sources = sources or ['linkedin', 'indeed', 'greenhouse']
        keywords = keywords or ['software engineer', 'developer', 'data scientist']
        locations = locations or ['remote', 'New York', 'San Francisco']
        
        all_jobs = []
        
        for source in sources:
            try:
                if source == 'linkedin':
                    jobs = await self.scrape_linkedin(keywords, locations, max_jobs // len(sources))
                elif source == 'indeed':
                    jobs = await self.scrape_indeed(keywords, locations, max_jobs // len(sources))
                elif source == 'greenhouse':
                    jobs = await self.scrape_greenhouse_boards(max_jobs // len(sources))
                else:
                    logger.warning(f"Unknown source: {source}")
                    continue
                
                all_jobs.extend(jobs)
                
            except Exception as e:
                logger.error(f"Error scraping {source}: {e}")
                continue
        
        # Save jobs to database
        self._save_jobs(all_jobs)
        
        return all_jobs
    
    async def scrape_linkedin(self, keywords: List[str], locations: List[str], max_jobs: int) -> List[Job]:
        """Scrape LinkedIn jobs"""
        jobs = []
        driver = self.browser_manager.create_driver()
        
        try:
            for keyword in keywords:
                for location in locations:
                    # Build LinkedIn URL
                    search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}"
                    
                    # Rate limiting
                    await self.rate_limiter.wait_if_needed(search_url)
                    
                    driver.get(search_url)
                    await asyncio.sleep(random.uniform(2, 4))
                    
                    # Scroll to load more jobs
                    self.browser_manager.human_like_scroll(driver)
                    
                    # Extract job listings
                    job_cards = driver.find_elements(By.CSS_SELECTOR, "div.job-card-container")
                    
                    for card in job_cards[:max_jobs]:
                        try:
                            job = self._extract_linkedin_job(card, driver)
                            if job and job['url'] not in self.scraped_urls:
                                jobs.append(job)
                                self.scraped_urls.add(job['url'])
                        except Exception as e:
                            logger.error(f"Error extracting LinkedIn job: {e}")
                            continue
                    
                    if len(jobs) >= max_jobs:
                        break
                
                if len(jobs) >= max_jobs:
                    break
                    
        finally:
            driver.quit()
        
        return jobs
    
    def _extract_linkedin_job(self, card, driver) -> Dict[str, Any]:
        """Extract job details from LinkedIn card"""
        try:
            # Click on job card to load details
            card.click()
            time.sleep(random.uniform(1, 2))
            
            # Extract information
            title = card.find_element(By.CSS_SELECTOR, "h3.job-card-list__title").text
            company = card.find_element(By.CSS_SELECTOR, "h4.job-card-container__company-name").text
            location = card.find_element(By.CSS_SELECTOR, "span.job-card-container__metadata-item").text
            
            # Get job URL
            job_link = card.find_element(By.CSS_SELECTOR, "a.job-card-container__link")
            url = job_link.get_attribute("href")
            
            # Try to get job description from details panel
            description = ""
            try:
                desc_element = driver.find_element(By.CSS_SELECTOR, "div.jobs-description")
                description = desc_element.text
            except:
                pass
            
            # Extract salary if available
            salary_info = self._extract_salary(description)
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'url': url,
                'description': description,
                'source': 'linkedin',
                'posted_date': datetime.now(),
                'min_salary': salary_info.get('min'),
                'max_salary': salary_info.get('max')
            }
            
        except Exception as e:
            logger.error(f"Error extracting LinkedIn job details: {e}")
            return None
    
    async def scrape_indeed(self, keywords: List[str], locations: List[str], max_jobs: int) -> List[Job]:
        """Scrape Indeed jobs"""
        jobs = []
        driver = self.browser_manager.create_driver()
        
        try:
            for keyword in keywords:
                for location in locations:
                    # Build Indeed URL
                    search_url = f"https://www.indeed.com/jobs?q={keyword}&l={location}"
                    
                    # Rate limiting
                    await self.rate_limiter.wait_if_needed(search_url)
                    
                    driver.get(search_url)
                    await asyncio.sleep(random.uniform(2, 4))
                    
                    # Extract job listings
                    job_cards = driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
                    
                    for card in job_cards[:max_jobs]:
                        try:
                            job = self._extract_indeed_job(card)
                            if job and job['url'] not in self.scraped_urls:
                                jobs.append(job)
                                self.scraped_urls.add(job['url'])
                        except Exception as e:
                            logger.error(f"Error extracting Indeed job: {e}")
                            continue
                    
                    if len(jobs) >= max_jobs:
                        break
                
                if len(jobs) >= max_jobs:
                    break
                    
        finally:
            driver.quit()
        
        return jobs
    
    def _extract_indeed_job(self, card) -> Dict[str, Any]:
        """Extract job details from Indeed card"""
        try:
            title_element = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span[title]")
            title = title_element.text
            
            company = card.find_element(By.CSS_SELECTOR, "span.companyName").text
            location = card.find_element(By.CSS_SELECTOR, "div.companyLocation").text
            
            # Get job URL
            link = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
            url = link.get_attribute("href")
            
            # Get description snippet
            try:
                description = card.find_element(By.CSS_SELECTOR, "div.job-snippet").text
            except:
                description = ""
            
            # Extract salary if available
            salary_text = ""
            try:
                salary_element = card.find_element(By.CSS_SELECTOR, "div.salary-snippet")
                salary_text = salary_element.text
            except:
                pass
            
            salary_info = self._extract_salary(salary_text)
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'url': url,
                'description': description,
                'source': 'indeed',
                'posted_date': datetime.now(),
                'min_salary': salary_info.get('min'),
                'max_salary': salary_info.get('max')
            }
            
        except Exception as e:
            logger.error(f"Error extracting Indeed job details: {e}")
            return None
    
    async def scrape_greenhouse_boards(self, max_jobs: int) -> List[Job]:
        """Scrape jobs from Greenhouse job boards"""
        jobs = []
        
        # List of known companies using Greenhouse
        greenhouse_companies = [
            "https://boards.greenhouse.io/spotify",
            "https://boards.greenhouse.io/airbnb",
            "https://boards.greenhouse.io/databricks",
            "https://boards.greenhouse.io/robinhood",
        ]
        
        driver = self.browser_manager.create_driver()
        
        try:
            for board_url in greenhouse_companies:
                try:
                    await self.rate_limiter.wait_if_needed(board_url)
                    driver.get(board_url)
                    await asyncio.sleep(random.uniform(2, 4))
                    
                    # Extract job listings
                    job_links = driver.find_elements(By.CSS_SELECTOR, "div.opening a")
                    
                    for link in job_links[:max_jobs // len(greenhouse_companies)]:
                        try:
                            job_url = link.get_attribute("href")
                            job_title = link.text
                            
                            # Extract company from URL
                            company = board_url.split("/")[-1].title()
                            
                            # Get job details
                            job = {
                                'title': job_title,
                                'company': company,
                                'url': job_url,
                                'source': 'greenhouse',
                                'platform': 'greenhouse',
                                'posted_date': datetime.now()
                            }
                            
                            if job_url not in self.scraped_urls:
                                jobs.append(job)
                                self.scraped_urls.add(job_url)
                                
                        except Exception as e:
                            logger.error(f"Error extracting Greenhouse job: {e}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Error scraping Greenhouse board {board_url}: {e}")
                    continue
                    
        finally:
            driver.quit()
        
        return jobs
    
    def _extract_salary(self, text: str) -> Dict[str, Optional[int]]:
        """Extract salary information from text"""
        salary_info = {'min': None, 'max': None}
        
        if not text:
            return salary_info
        
        # Common salary patterns
        patterns = [
            r'\$([0-9,]+)\s*-\s*\$([0-9,]+)',  # $100,000 - $150,000
            r'\$([0-9,]+)k\s*-\s*\$([0-9,]+)k',  # $100k - $150k
            r'([0-9,]+)\s*-\s*([0-9,]+)\s*USD',  # 100000 - 150000 USD
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    min_sal = match.group(1).replace(',', '')
                    max_sal = match.group(2).replace(',', '')
                    
                    # Handle 'k' notation
                    if 'k' in text.lower():
                        salary_info['min'] = int(float(min_sal) * 1000)
                        salary_info['max'] = int(float(max_sal) * 1000)
                    else:
                        salary_info['min'] = int(min_sal)
                        salary_info['max'] = int(max_sal)
                    
                    break
                except:
                    continue
        
        return salary_info
    
    async def enrich_job_with_ai(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to extract structured information from job posting"""
        
        schema = {
            "type": "object",
            "properties": {
                "required_skills": {"type": "array", "items": {"type": "string"}},
                "nice_to_have_skills": {"type": "array", "items": {"type": "string"}},
                "experience_years": {"type": "number"},
                "remote_type": {"type": "string", "enum": ["remote", "hybrid", "onsite"]},
                "visa_sponsorship": {"type": "boolean"},
                "benefits": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["required_skills", "experience_years", "remote_type"]
        }
        
        prompt = f"""
        Analyze this job posting and extract structured information:
        
        Title: {job.get('title', '')}
        Company: {job.get('company', '')}
        Description: {job.get('description', '')[:1000]}
        
        Extract:
        - Required skills (technical skills that are mandatory)
        - Nice to have skills (preferred but not required)
        - Years of experience required (number)
        - Remote type (remote/hybrid/onsite)
        - Visa sponsorship available (true/false)
        - Key benefits mentioned
        """
        
        try:
            result = await generate_structured_response(prompt, schema, temperature=0)
            job.update(result)
        except Exception as e:
            logger.error(f"Error enriching job with AI: {e}")
        
        return job
    
    def _save_jobs(self, jobs: List[Dict[str, Any]]):
        """Save jobs to database"""
        for job_data in jobs:
            try:
                # Check if job already exists
                existing = self.session.query(Job).filter_by(url=job_data['url']).first()
                if existing:
                    continue
                
                # Create new job
                job = Job(
                    url=job_data['url'],
                    title=job_data['title'],
                    company=job_data['company'],
                    location=job_data.get('location', ''),
                    description=job_data.get('description', ''),
                    source=job_data.get('source', ''),
                    platform=job_data.get('platform', ''),
                    posted_date=job_data.get('posted_date', datetime.now()),
                    min_salary=job_data.get('min_salary'),
                    max_salary=job_data.get('max_salary'),
                    required_skills=job_data.get('required_skills', []),
                    nice_to_have_skills=job_data.get('nice_to_have_skills', []),
                    experience_required=job_data.get('experience_years'),
                    remote_type=job_data.get('remote_type', 'unknown'),
                    status=JobStatus.DISCOVERED,
                    relevance_score=0.0
                )
                
                self.session.add(job)
                
            except Exception as e:
                logger.error(f"Error saving job to database: {e}")
                continue
        
        self.session.commit()
        logger.info(f"Saved {len(jobs)} jobs to database")

# Async wrapper for use in Streamlit
async def scrape_jobs_async(sources: List[str] = None, 
                           keywords: List[str] = None,
                           locations: List[str] = None,
                           max_jobs: int = 50) -> List[Job]:
    """Async wrapper for job scraping"""
    scraper = JobScraper()
    return await scraper.scrape_jobs(sources, keywords, locations, max_jobs)

def scrape_jobs_sync(sources: List[str] = None,
                     keywords: List[str] = None, 
                     locations: List[str] = None,
                     max_jobs: int = 50) -> List[Job]:
    """Synchronous wrapper for Streamlit"""
    return asyncio.run(scrape_jobs_async(sources, keywords, locations, max_jobs))
