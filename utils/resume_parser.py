# utils/resume_parser.py
import re
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("PyPDF2 not available. PDF parsing will be disabled.")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx not available. DOCX parsing will be disabled.")

logger = logging.getLogger(__name__)

class ResumeParser:
    """Parse resume files and extract structured information"""
    
    def __init__(self):
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
        self.url_pattern = re.compile(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?')
        
    def parse_resume(self, file_path: str) -> Dict[str, Any]:
        """Parse a resume file and extract structured information"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path}")
        
        # Determine file type and parse accordingly
        if file_path.suffix.lower() == '.pdf':
            if not PDF_AVAILABLE:
                raise ImportError("PyPDF2 is required for PDF parsing")
            text = self._extract_text_from_pdf(file_path)
        elif file_path.suffix.lower() in ['.docx', '.doc']:
            if not DOCX_AVAILABLE:
                raise ImportError("python-docx is required for DOCX parsing")
            text = self._extract_text_from_docx(file_path)
        else:
            # Try to read as plain text
            text = self._extract_text_from_file(file_path)
        
        # Parse the extracted text
        return self._parse_resume_text(text)
    
    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                
                return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise
    
    def _extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        try:
            doc = Document(file_path)
            text = ""
            
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from DOCX {file_path}: {e}")
            raise
    
    def _extract_text_from_file(self, file_path: Path) -> str:
        """Extract text from plain text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()
    
    def _parse_resume_text(self, text: str) -> Dict[str, Any]:
        """Parse resume text and extract structured information"""
        parsed_data = {
            'name': self._extract_name(text),
            'email': self._extract_email(text),
            'phone': self._extract_phone(text),
            'linkedin': self._extract_linkedin(text),
            'website': self._extract_website(text),
            'education': self._extract_education(text),
            'experience': self._extract_experience(text),
            'skills': self._extract_skills(text),
            'summary': self._extract_summary(text),
            'raw_text': text
        }
        
        return parsed_data
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract name from resume text"""
        # Look for common name patterns at the beginning of the document
        lines = text.split('\n')
        
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line and len(line) < 50:  # Reasonable name length
                # Check if line looks like a name (no special characters, proper case)
                if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', line):
                    return line
                elif re.match(r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$', line):  # Middle initial
                    return line
        
        return None
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email address from resume text"""
        emails = self.email_pattern.findall(text)
        return emails[0] if emails else None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number from resume text"""
        phones = self.phone_pattern.findall(text)
        return phones[0] if phones else None
    
    def _extract_linkedin(self, text: str) -> Optional[str]:
        """Extract LinkedIn URL from resume text"""
        urls = self.url_pattern.findall(text)
        for url in urls:
            if 'linkedin.com' in url.lower():
                return url
        return None
    
    def _extract_website(self, text: str) -> Optional[str]:
        """Extract personal website from resume text"""
        urls = self.url_pattern.findall(text)
        for url in urls:
            if 'linkedin.com' not in url.lower() and 'github.com' not in url.lower():
                return url
        return None
    
    def _extract_education(self, text: str) -> List[Dict[str, str]]:
        """Extract education information from resume text"""
        education = []
        
        # Look for education section
        education_section = self._find_section(text, ['education', 'academic', 'degree'])
        
        if education_section:
            # Parse education entries
            lines = education_section.split('\n')
            current_entry = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_entry:
                        education.append(current_entry)
                        current_entry = {}
                    continue
                
                # Look for degree patterns
                if re.search(r'\b(BA|BS|MA|MS|PhD|MBA|BSc|MSc)\b', line, re.IGNORECASE):
                    if current_entry:
                        education.append(current_entry)
                    current_entry = {'degree': line}
                elif 'university' in line.lower() or 'college' in line.lower():
                    current_entry['institution'] = line
                elif re.search(r'\b(20\d{2}|19\d{2})\b', line):  # Year pattern
                    current_entry['year'] = line
            
            if current_entry:
                education.append(current_entry)
        
        return education
    
    def _extract_experience(self, text: str) -> List[Dict[str, str]]:
        """Extract work experience from resume text"""
        experience = []
        
        # Look for experience section
        experience_section = self._find_section(text, ['experience', 'work history', 'employment'])
        
        if experience_section:
            # Parse experience entries
            lines = experience_section.split('\n')
            current_entry = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_entry:
                        experience.append(current_entry)
                        current_entry = {}
                    continue
                
                # Look for job title patterns
                if re.search(r'\b(Developer|Engineer|Manager|Analyst|Consultant|Specialist)\b', line, re.IGNORECASE):
                    if current_entry:
                        experience.append(current_entry)
                    current_entry = {'title': line}
                elif 'company' in line.lower() or 'inc' in line.lower() or 'corp' in line.lower():
                    current_entry['company'] = line
                elif re.search(r'\b(20\d{2}|19\d{2})\b', line):  # Year pattern
                    current_entry['period'] = line
            
            if current_entry:
                experience.append(current_entry)
        
        return experience
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills from resume text"""
        skills = []
        
        # Look for skills section
        skills_section = self._find_section(text, ['skills', 'technologies', 'programming languages'])
        
        if skills_section:
            # Extract skills (comma-separated, bullet points, etc.)
            skill_patterns = [
                r'[•\-\*]\s*([^,\n]+)',  # Bullet points
                r'([A-Z][a-z]+(?:\s*[A-Z][a-z]+)*)',  # Capitalized words
            ]
            
            for pattern in skill_patterns:
                matches = re.findall(pattern, skills_section)
                skills.extend([skill.strip() for skill in matches if len(skill.strip()) > 2])
        
        # Remove duplicates and common words
        common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        skills = list(set([skill.lower() for skill in skills if skill.lower() not in common_words]))
        
        return skills[:20]  # Limit to top 20 skills
    
    def _extract_summary(self, text: str) -> Optional[str]:
        """Extract summary/objective from resume text"""
        # Look for summary section
        summary_section = self._find_section(text, ['summary', 'objective', 'profile'])
        
        if summary_section:
            # Take first paragraph as summary
            paragraphs = summary_section.split('\n\n')
            if paragraphs:
                return paragraphs[0].strip()
        
        return None
    
    def _find_section(self, text: str, section_keywords: List[str]) -> Optional[str]:
        """Find a specific section in the resume text"""
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            for keyword in section_keywords:
                if keyword in line_lower:
                    # Return the section content
                    section_lines = []
                    for j in range(i + 1, len(lines)):
                        next_line = lines[j].strip()
                        if next_line and next_line.isupper():  # New section header
                            break
                        section_lines.append(next_line)
                    
                    return '\n'.join(section_lines)
        
        return None

# Global resume parser instance
resume_parser = ResumeParser()
