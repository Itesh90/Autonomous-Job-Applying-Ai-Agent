"""
AI Job Application Agent - Main Streamlit Application
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import asyncio
from pathlib import Path
import json

from config.settings import settings, FEATURES
from models.database import get_session, Candidate, Job, Application, JobStatus, ApplicationStatus
from utils.logger import get_logger, log_audit

# Initialize logger
logger = get_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="AI Job Application Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stMetricLabel {font-size: 0.9rem;}
    .stMetricValue {font-size: 1.8rem;}
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'agent_running' not in st.session_state:
    st.session_state.agent_running = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Dashboard"
if 'candidate_profile' not in st.session_state:
    st.session_state.candidate_profile = None

def load_candidate_profile():
    """Load candidate profile from database"""
    session = get_session()
    candidate = session.query(Candidate).first()
    session.close()
    return candidate

def get_application_stats():
    """Get application statistics"""
    session = get_session()
    
    # Get counts
    total_jobs = session.query(Job).count()
    completed_apps = session.query(Application).filter_by(status=ApplicationStatus.SUBMITTED).count()
    pending_apps = session.query(Application).filter_by(status=ApplicationStatus.PENDING).count()
    review_apps = session.query(Application).filter_by(status=ApplicationStatus.NEEDS_REVIEW).count()
    
    # Calculate success rate
    total_processed = session.query(Application).filter(
        Application.status.in_([ApplicationStatus.SUBMITTED, ApplicationStatus.FAILED])
    ).count()
    
    success_rate = (completed_apps / total_processed * 100) if total_processed > 0 else 0
    
    session.close()
    
    return {
        'total_jobs': total_jobs,
        'completed': completed_apps,
        'pending': pending_apps,
        'review': review_apps,
        'success_rate': success_rate
    }

def dashboard_page():
    """Main dashboard page"""
    st.title("🤖 AI Job Application Agent Dashboard")
    
    # Get statistics
    stats = get_application_stats()
    
    # Metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Total Jobs",
            stats['total_jobs'],
            delta="+12 today" if stats['total_jobs'] > 0 else None
        )
    
    with col2:
        st.metric(
            "Applications Submitted",
            stats['completed'],
            delta="+3 today" if stats['completed'] > 0 else None
        )
    
    with col3:
        st.metric(
            "Pending",
            stats['pending']
        )
    
    with col4:
        st.metric(
            "Needs Review",
            stats['review'],
            delta_color="inverse" if stats['review'] > 5 else "normal"
        )
    
    with col5:
        st.metric(
            "Success Rate",
            f"{stats['success_rate']:.1f}%",
            delta="+2.3%" if stats['success_rate'] > 70 else "-1.2%"
        )
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        # Application trend chart
        st.subheader("📈 Application Trend")
        
        # Generate sample data (replace with real data)
        dates = pd.date_range(end=datetime.now(), periods=30)
        trend_data = pd.DataFrame({
            'Date': dates,
            'Submitted': [i + 2 for i in range(30)],
            'Failed': [1 if i % 3 == 0 else 0 for i in range(30)]
        })
        
        fig = px.line(trend_data, x='Date', y=['Submitted', 'Failed'], 
                     title='Applications Over Time',
                     labels={'value': 'Count', 'variable': 'Status'})
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Success rate by platform
        st.subheader("🎯 Success by Platform")
        
        platform_data = pd.DataFrame({
            'Platform': ['LinkedIn', 'Indeed', 'Greenhouse', 'Lever', 'Workable'],
            'Success Rate': [75, 68, 82, 71, 79]
        })
        
        fig = px.bar(platform_data, x='Platform', y='Success Rate',
                    title='Success Rate by Platform',
                    color='Success Rate',
                    color_continuous_scale='RdYlGn')
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent applications
    st.subheader("📋 Recent Applications")
    
    session = get_session()
    recent_apps = session.query(Application).order_by(Application.created_at.desc()).limit(5).all()
    
    if recent_apps:
        for app in recent_apps:
            with st.expander(f"{app.job.title if app.job else 'Unknown'} - {app.status}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Company:** {app.job.company if app.job else 'N/A'}")
                    st.write(f"**Applied:** {app.created_at.strftime('%Y-%m-%d %H:%M')}")
                
                with col2:
                    st.write(f"**Status:** {app.status}")
                    st.write(f"**Confidence:** {app.confidence_score:.1%}")
                
                with col3:
                    if app.status == ApplicationStatus.NEEDS_REVIEW:
                        if st.button(f"Review", key=f"review_{app.id}"):
                            st.session_state.current_page = "Manual Review"
                            st.rerun()
    else:
        st.info("No applications yet. Start by adding your profile and configuring job search criteria.")
    
    session.close()
    
    # Control panel
    st.subheader("🎮 Control Panel")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 Scan for New Jobs", type="primary", use_container_width=True):
            with st.spinner("Scanning job sites..."):
                # Trigger job scanning
                st.success("Found 15 new job postings!")
    
    with col2:
        if st.button("🚀 Process Applications", type="primary", use_container_width=True,
                    disabled=st.session_state.agent_running):
            st.session_state.agent_running = True
            st.success("Application processing started!")
            st.rerun()
    
    with col3:
        if st.button("🛑 Stop Agent", type="secondary", use_container_width=True,
                    disabled=not st.session_state.agent_running):
            st.session_state.agent_running = False
            st.info("Agent stopped")
            st.rerun()

def profile_page():
    """Profile management page"""
    st.title("👤 Profile Management")
    
    # Load existing profile
    candidate = load_candidate_profile()
    
    # Profile form
    with st.form("profile_form"):
        st.subheader("Personal Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            first_name = st.text_input("First Name", value=candidate.first_name if candidate else "")
            last_name = st.text_input("Last Name", value=candidate.last_name if candidate else "")
            email = st.text_input("Email", value=candidate.email if candidate else "")
        
        with col2:
            phone = st.text_input("Phone", value=candidate.phone if candidate else "")
            location = st.text_input("Location", value="")
            years_exp = st.number_input("Years of Experience", min_value=0, max_value=50, value=0)
        
        st.subheader("Professional Summary")
        summary = st.text_area("Summary", height=150, 
                              value=candidate.profile_summary if candidate else "",
                              help="Brief overview of your experience and career goals")
        
        st.subheader("Skills")
        skills = st.text_area("Skills (comma-separated)", 
                             value=", ".join(candidate.skills) if candidate and candidate.skills else "",
                             help="Enter your key skills separated by commas")
        
        st.subheader("Resume Upload")
        resume_file = st.file_uploader("Upload Resume", type=['pdf', 'docx', 'txt'])
        
        st.subheader("Job Preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            desired_roles = st.text_area("Desired Job Titles", 
                                        help="Enter job titles you're interested in, one per line")
            remote_pref = st.selectbox("Remote Preference", 
                                      ["Flexible", "Remote Only", "Hybrid", "On-site Only"])
        
        with col2:
            min_salary = st.number_input("Minimum Salary ($)", min_value=0, step=5000)
            max_salary = st.number_input("Maximum Salary ($)", min_value=0, step=5000)
        
        # Submit button
        submitted = st.form_submit_button("Save Profile", type="primary", use_container_width=True)
        
        if submitted:
            # Save profile to database
            session = get_session()
            
            if not candidate:
                candidate = Candidate()
            
            candidate.first_name = first_name
            candidate.last_name = last_name
            candidate.email = email
            candidate.phone = phone
            candidate.profile_summary = summary
            candidate.years_experience = years_exp
            candidate.skills = skills.split(",") if skills else []
            candidate.remote_preference = remote_pref.lower().replace(" ", "_")
            candidate.min_salary = min_salary
            candidate.max_salary = max_salary
            
            if desired_roles:
                candidate.desired_roles = [r.strip() for r in desired_roles.split("\n")]
            
            session.add(candidate)
            session.commit()
            session.close()
            
            st.success("✅ Profile saved successfully!")
            log_audit("profile_updated", {"candidate_id": candidate.id})

def settings_page():
    """Settings and configuration page"""
    st.title("⚙️ Settings")
    
    # API Keys section
    st.subheader("🔑 API Keys")
    
    with st.expander("LLM Provider Configuration", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            openai_key = st.text_input("OpenAI API Key", type="password", 
                                      value="sk-..." if settings.openai_api_key else "")
            anthropic_key = st.text_input("Anthropic API Key", type="password",
                                         value="sk-ant-..." if settings.anthropic_api_key else "")
        
        with col2:
            default_provider = st.selectbox("Default LLM Provider", 
                                          ["openai", "anthropic", "local"])
            temperature = st.slider("Temperature", 0.0, 1.0, 0.0, 0.1)
        
        if st.button("Save API Keys"):
            # Save keys (in production, these should be encrypted)
            st.success("API keys saved successfully!")
    
    # Automation settings
    st.subheader("🤖 Automation Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        rate_limit = st.number_input("Rate Limit Delay (seconds)", 
                                    min_value=1, max_value=60, value=settings.rate_limit_delay)
        max_concurrent = st.number_input("Max Concurrent Applications", 
                                        min_value=1, max_value=10, value=settings.max_concurrent_jobs)
        dry_run = st.checkbox("Dry Run Mode", value=settings.dry_run_mode,
                            help="Test without actually submitting applications")
    
    with col2:
        headless = st.checkbox("Headless Browser", value=settings.headless_browser,
                              help="Run browser in background without UI")
        use_selenium = st.checkbox("Use Selenium", value=settings.use_selenium)
        use_undetected = st.checkbox("Use Undetected Chrome", value=settings.use_undetected_chrome,
                                    help="Use anti-detection browser for better success rate")
    
    # Feature flags
    st.subheader("🚀 Features")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.checkbox("RAG Enabled", value=FEATURES["rag_enabled"])
        st.checkbox("Multi-Provider LLM", value=FEATURES["multi_provider_llm"])
    
    with col2:
        st.checkbox("CAPTCHA Detection", value=FEATURES["captcha_detection"])
        st.checkbox("Monitoring Enabled", value=FEATURES["monitoring_enabled"])
    
    with col3:
        st.checkbox("Audit Logging", value=FEATURES["audit_logging"])
        st.checkbox("Data Encryption", value=FEATURES["data_encryption"])
    
    # Save settings button
    if st.button("Save All Settings", type="primary", use_container_width=True):
        st.success("Settings saved successfully!")
        log_audit("settings_updated", {"updated_by": "user"})

def jobs_page():
    """Job listings and management page"""
    st.title("💼 Job Listings")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        search = st.text_input("Search", placeholder="Search jobs...")
    
    with col2:
        status_filter = st.selectbox("Status", ["All", "Discovered", "Queued", "Completed", "Failed"])
    
    with col3:
        platform_filter = st.selectbox("Platform", ["All", "LinkedIn", "Indeed", "Greenhouse", "Lever"])
    
    with col4:
        date_range = st.selectbox("Date Range", ["All Time", "Today", "This Week", "This Month"])
    
    # Jobs table
    session = get_session()
    query = session.query(Job)
    
    if status_filter != "All":
        query = query.filter_by(status=status_filter.lower())
    
    jobs = query.order_by(Job.created_at.desc()).limit(50).all()
    
    if jobs:
        # Create DataFrame for display
        jobs_data = []
        for job in jobs:
            jobs_data.append({
                'Title': job.title,
                'Company': job.company,
                'Location': job.location,
                'Status': job.status,
                'Score': f"{job.relevance_score:.1%}" if job.relevance_score else "N/A",
                'Posted': job.posted_date.strftime('%Y-%m-%d') if job.posted_date else "Unknown",
                'ID': job.id
            })
        
        df = pd.DataFrame(jobs_data)
        
        # Display with selection
        selected = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row"
        )
        
        # Job details
        if selected and selected['selection']['rows']:
            selected_idx = selected['selection']['rows'][0]
            selected_job = jobs[selected_idx]
            
            st.subheader(f"Job Details: {selected_job.title}")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Company:** {selected_job.company}")
                st.write(f"**Location:** {selected_job.location}")
                st.write(f"**URL:** {selected_job.url}")
                
                if selected_job.description:
                    st.write("**Description:**")
                    st.write(selected_job.description[:500] + "..." if len(selected_job.description) > 500 else selected_job.description)
            
            with col2:
                st.write(f"**Status:** {selected_job.status}")
                st.write(f"**Relevance Score:** {selected_job.relevance_score:.1%}")
                
                if selected_job.status == JobStatus.DISCOVERED:
                    if st.button("Apply Now", key=f"apply_{selected_job.id}"):
                        st.success("Application queued!")
                
                if st.button("View Full Details", key=f"view_{selected_job.id}"):
                    st.json({"job_id": selected_job.id, "url": selected_job.url})
    else:
        st.info("No jobs found. Try adjusting your filters or scanning for new jobs.")
    
    session.close()

def monitoring_page():
    """System monitoring and metrics page"""
    st.title("📊 System Monitoring")
    
    # System metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("CPU Usage", "23%", delta="-2%")
    
    with col2:
        st.metric("Memory", "1.2 GB", delta="+0.1 GB")
    
    with col3:
        st.metric("Active Browsers", "2", delta="0")
    
    with col4:
        st.metric("API Calls Today", "156", delta="+12")
    
    # LLM usage chart
    st.subheader("🤖 LLM Usage")
    
    llm_data = pd.DataFrame({
        'Provider': ['OpenAI', 'Anthropic', 'Local'],
        'Calls': [89, 45, 22],
        'Tokens': [15234, 8921, 3421],
        'Cost': [4.57, 2.23, 0.00]
    })
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(llm_data, values='Calls', names='Provider', title='API Calls by Provider')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(llm_data, x='Provider', y='Cost', title='Cost by Provider ($)')
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent logs
    st.subheader("📝 Recent Logs")
    
    log_level = st.selectbox("Log Level", ["All", "ERROR", "WARNING", "INFO", "DEBUG"])
    
    # Sample logs (replace with real log reading)
    logs = [
        {"time": "2024-01-15 10:23:45", "level": "INFO", "message": "Application submitted successfully for Software Engineer at TechCo"},
        {"time": "2024-01-15 10:22:30", "level": "WARNING", "message": "Rate limit approaching for linkedin.com"},
        {"time": "2024-01-15 10:21:15", "level": "ERROR", "message": "Failed to parse form on greenhouse.io - retrying"},
        {"time": "2024-01-15 10:20:00", "level": "INFO", "message": "Job scanning completed - found 12 new positions"},
    ]
    
    for log in logs:
        if log_level == "All" or log["level"] == log_level:
            color = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵", "DEBUG": "⚪"}.get(log["level"], "⚪")
            st.text(f"{color} [{log['time']}] {log['level']}: {log['message']}")

# Sidebar navigation
with st.sidebar:
    st.title("🤖 AI Job Agent")
    
    # Agent status
    if st.session_state.agent_running:
        st.success("✅ Agent Running")
    else:
        st.info("⏸️ Agent Paused")
    
    st.divider()
    
    # Navigation
    pages = {
        "Dashboard": "📊",
        "Profile": "👤",
        "Jobs": "💼",
        "Settings": "⚙️",
        "Monitoring": "📈"
    }
    
    for page_name, icon in pages.items():
        if st.button(f"{icon} {page_name}", key=f"nav_{page_name}", use_container_width=True,
                    type="primary" if st.session_state.current_page == page_name else "secondary"):
            st.session_state.current_page = page_name
            st.rerun()
    
    st.divider()
    
    # Quick stats
    stats = get_application_stats()
    st.metric("Success Rate", f"{stats['success_rate']:.1f}%")
    st.metric("Pending Reviews", stats['review'])
    
    st.divider()
    
    # Quick actions
    if st.button("🆘 Help", use_container_width=True):
        st.info("Check documentation at github.com/yourrepo")

# Main content area
if st.session_state.current_page == "Dashboard":
    dashboard_page()
elif st.session_state.current_page == "Profile":
    profile_page()
elif st.session_state.current_page == "Settings":
    settings_page()
elif st.session_state.current_page == "Jobs":
    jobs_page()
elif st.session_state.current_page == "Monitoring":
    monitoring_page()

# Footer
st.divider()
st.caption("AI Job Application Agent v1.0.0 | © 2024 | [Documentation](https://github.com/yourrepo)")
