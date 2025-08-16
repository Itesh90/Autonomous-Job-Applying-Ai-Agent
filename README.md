# 🤖 AI Job Application Agent

An advanced autonomous system that intelligently scans job postings and automatically fills out applications using multiple LLM providers, RAG, and web automation.

## ✨ Features

- **Multi-Provider LLM System**: Supports OpenAI, Anthropic, and local models with automatic fallback
- **RAG Integration**: Uses vector databases for intelligent context-aware form filling
- **Advanced Web Scraping**: Selenium and Playwright support with anti-detection measures
- **Platform Adapters**: Built-in support for LinkedIn, Indeed, Greenhouse, Lever, Workable
- **CAPTCHA Detection**: Automatically detects and pauses for human intervention
- **Data Encryption**: All PII encrypted at rest using Fernet encryption
- **Comprehensive UI**: Beautiful Streamlit dashboard with real-time monitoring
- **Dry Run Mode**: Test applications without actually submitting
- **Audit Logging**: Complete compliance trail for all actions

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Chrome/Chromium browser
- 8GB RAM minimum (16GB recommended for local LLMs)
- PostgreSQL (optional, SQLite by default)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/job-agent.git
cd job-agent
```

2. **Create virtual environment**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Install browser drivers**
```bash
playwright install chromium
```

5. **Set up environment variables**
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your API keys
# Generate encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

6. **Initialize database**
```bash
python -c "from models.database import init_database; init_database()"
```

7. **Run the application**
```bash
streamlit run main_app.py
```

The application will open at http://localhost:8501

## 📖 Usage Guide

### 1. Profile Setup
- Navigate to the **Profile** page
- Fill in your personal information
- Upload your resume (PDF/DOCX)
- Set job preferences (roles, salary, location)

### 2. Configure API Keys
- Go to **Settings** page
- Add your OpenAI/Anthropic API keys
- Configure rate limits and browser settings
- Enable/disable features as needed

### 3. Job Scanning
- Click **Scan for New Jobs** on Dashboard
- The agent will search configured job sites
- Jobs are automatically scored for relevance

### 4. Application Processing
- Click **Process Applications** to start
- Agent will automatically fill and submit forms
- Monitor progress in real-time
- Review flagged applications manually

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit UI  │────│  Core Engine    │────│  LLM Providers  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Web Scraping   │────│ Platform        │────│   RAG System    │
│  (Selenium)     │    │ Adapters        │    │   (ChromaDB)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │   Encrypted Database    │
                    │   (PostgreSQL/SQLite)   │
                    └─────────────────────────┘
```

## 🔧 Configuration

### LLM Providers

Configure in `.env`:
```env
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
DEFAULT_LLM_PROVIDER=openai
```

### Browser Settings

```env
HEADLESS_BROWSER=false  # Set to true for production
USE_SELENIUM=true
USE_UNDETECTED_CHROME=true  # Anti-detection
BROWSER_TIMEOUT=30000
```

### Rate Limiting

```env
RATE_LIMIT_DELAY=5  # Seconds between requests
MAX_CONCURRENT_JOBS=3
```

## 🛡️ Safety & Compliance

- **No CAPTCHA Bypass**: System pauses for human verification
- **Rate Limiting**: Respects website limits
- **Robots.txt Compliance**: Follows crawling guidelines
- **Data Encryption**: All PII encrypted at rest
- **Audit Trail**: Complete logging of all actions
- **GDPR Compliant**: Data retention and privacy controls

## 📊 Monitoring

Access the monitoring dashboard to view:
- Application success rates
- LLM API usage and costs
- System performance metrics
- Error logs and debugging info

## 🧪 Development

### Running Tests
```bash
pytest tests/
```

### Code Style
```bash
black .
flake8 .
mypy .
```

### Docker Setup
```bash
docker-compose up --build
```

## 📝 API Documentation

The system exposes a FastAPI backend (optional):
```bash
uvicorn api.main:app --reload
```

API docs available at: http://localhost:8000/docs

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This tool is for educational and personal use. Always:
- Respect website terms of service
- Be transparent about automated applications
- Comply with local employment laws
- Use responsibly and ethically

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

- Documentation: [GitHub Wiki](https://github.com/yourusername/job-agent/wiki)
- Issues: [GitHub Issues](https://github.com/yourusername/job-agent/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/job-agent/discussions)

## 🙏 Acknowledgments

- OpenAI and Anthropic for LLM APIs
- Streamlit for the amazing UI framework
- Selenium and Playwright teams
- All open-source contributors

---

**Made with ❤️ by the AI Job Agent Team**
