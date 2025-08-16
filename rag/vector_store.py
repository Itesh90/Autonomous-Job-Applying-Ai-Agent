"""
RAG (Retrieval-Augmented Generation) system for intelligent form filling
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import hashlib
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
import faiss
import pickle

from config.settings import settings
from models.database import Candidate, Job, Application, get_session
from utils.logger import get_logger
from llm.provider_manager import generate_llm_response

logger = get_logger(__name__)

@dataclass
class RetrievalResult:
    """Result from vector store retrieval"""
    content: str
    metadata: Dict[str, Any]
    score: float
    source: str

class VectorStore:
    """Advanced vector store for job and candidate data"""
    
    def __init__(self):
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.chroma_client = None
        self.collections = {}
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        self._initialize_stores()
    
    def _initialize_stores(self):
        """Initialize ChromaDB and collections"""
        try:
            # Initialize ChromaDB
            self.chroma_client = chromadb.PersistentClient(
                path=str(settings.chroma_persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Create collections
            self.collections['jobs'] = self.chroma_client.get_or_create_collection(
                name="jobs",
                metadata={"description": "Job postings and descriptions"}
            )
            
            self.collections['candidates'] = self.chroma_client.get_or_create_collection(
                name="candidates",
                metadata={"description": "Candidate profiles and experiences"}
            )
            
            self.collections['applications'] = self.chroma_client.get_or_create_collection(
                name="applications",
                metadata={"description": "Previous application data and responses"}
            )
            
            self.collections['knowledge'] = self.chroma_client.get_or_create_collection(
                name="knowledge",
                metadata={"description": "Domain knowledge and best practices"}
            )
            
            logger.info("Vector stores initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing vector stores: {e}")
            raise
    
    def add_job(self, job: Job):
        """Add job posting to vector store"""
        try:
            # Prepare job text
            job_text = f"""
            Job Title: {job.title}
            Company: {job.company}
            Location: {job.location}
            Remote Type: {job.remote_type}
            
            Description:
            {job.description}
            
            Requirements:
            {job.requirements}
            
            Required Skills: {', '.join(job.required_skills or [])}
            Nice to Have: {', '.join(job.nice_to_have_skills or [])}
            Experience Required: {job.experience_required} years
            Salary Range: ${job.min_salary} - ${job.max_salary}
            """
            
            # Split into chunks
            chunks = self.text_splitter.split_text(job_text)
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(chunks).tolist()
            
            # Prepare documents for ChromaDB
            ids = [f"job_{job.id}_{i}" for i in range(len(chunks))]
            metadatas = [{
                "job_id": job.id,
                "company": job.company,
                "title": job.title,
                "source": job.source,
                "chunk_index": i
            } for i in range(len(chunks))]
            
            # Add to ChromaDB
            self.collections['jobs'].add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"Added job {job.id} to vector store with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error adding job to vector store: {e}")
    
    def add_candidate_profile(self, candidate: Candidate):
        """Add candidate profile to vector store"""
        try:
            # Prepare candidate text
            candidate_text = f"""
            Name: {candidate.first_name} {candidate.last_name}
            Email: {candidate.email}
            Years of Experience: {candidate.years_experience}
            
            Professional Summary:
            {candidate.profile_summary}
            
            Skills: {', '.join(candidate.skills or [])}
            
            Education:
            {json.dumps(candidate.education, indent=2) if candidate.education else 'N/A'}
            
            Experiences:
            {json.dumps(candidate.experiences, indent=2) if candidate.experiences else 'N/A'}
            
            Desired Roles: {', '.join(candidate.desired_roles or [])}
            Desired Locations: {', '.join(candidate.desired_locations or [])}
            Remote Preference: {candidate.remote_preference}
            Salary Range: ${candidate.min_salary} - ${candidate.max_salary}
            """
            
            # Add resume text if available
            if candidate.resume_text:
                candidate_text += f"\n\nResume Content:\n{candidate.resume_text}"
            
            # Split into chunks
            chunks = self.text_splitter.split_text(candidate_text)
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(chunks).tolist()
            
            # Prepare documents
            ids = [f"candidate_{candidate.id}_{i}" for i in range(len(chunks))]
            metadatas = [{
                "candidate_id": candidate.id,
                "type": "profile",
                "chunk_index": i
            } for i in range(len(chunks))]
            
            # Add to ChromaDB
            self.collections['candidates'].add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"Added candidate profile to vector store with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error adding candidate to vector store: {e}")
    
    def add_application_history(self, application: Application):
        """Add successful application to learn from"""
        try:
            if application.status != 'submitted':
                return
            
            # Prepare application text
            app_text = f"""
            Job: {application.job.title if application.job else 'Unknown'}
            Company: {application.job.company if application.job else 'Unknown'}
            
            Form Data Filled:
            {json.dumps(application.form_data, indent=2) if application.form_data else 'N/A'}
            
            Cover Letter:
            {application.cover_letter}
            
            Additional Questions and Answers:
            {json.dumps(application.additional_questions, indent=2) if application.additional_questions else 'N/A'}
            
            Confidence Score: {application.confidence_score}
            """
            
            # Generate embedding
            embedding = self.embedding_model.encode([app_text]).tolist()
            
            # Add to ChromaDB
            self.collections['applications'].add(
                ids=[f"app_{application.id}"],
                embeddings=embedding,
                documents=[app_text],
                metadatas=[{
                    "application_id": application.id,
                    "job_id": application.job_id,
                    "success": True,
                    "confidence": application.confidence_score
                }]
            )
            
            logger.info(f"Added application history to vector store")
            
        except Exception as e:
            logger.error(f"Error adding application to vector store: {e}")
    
    def search_similar_jobs(self, query: str, k: int = 5) -> List[RetrievalResult]:
        """Search for similar jobs in vector store"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query]).tolist()
            
            # Search in ChromaDB
            results = self.collections['jobs'].query(
                query_embeddings=query_embedding,
                n_results=k
            )
            
            # Format results
            retrieval_results = []
            for i in range(len(results['documents'][0])):
                retrieval_results.append(RetrievalResult(
                    content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i],
                    score=1 - results['distances'][0][i],  # Convert distance to similarity
                    source='jobs'
                ))
            
            return retrieval_results
            
        except Exception as e:
            logger.error(f"Error searching jobs: {e}")
            return []
    
    def get_relevant_experience(self, job_description: str, k: int = 3) -> List[RetrievalResult]:
        """Get relevant candidate experience for a job"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([job_description]).tolist()
            
            # Search in candidate collection
            results = self.collections['candidates'].query(
                query_embeddings=query_embedding,
                n_results=k
            )
            
            # Format results
            retrieval_results = []
            for i in range(len(results['documents'][0])):
                retrieval_results.append(RetrievalResult(
                    content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i],
                    score=1 - results['distances'][0][i],
                    source='candidates'
                ))
            
            return retrieval_results
            
        except Exception as e:
            logger.error(f"Error getting relevant experience: {e}")
            return []
    
    def find_similar_applications(self, job: Job, k: int = 3) -> List[RetrievalResult]:
        """Find similar successful applications"""
        try:
            query = f"{job.title} {job.company} {job.description[:500]}"
            query_embedding = self.embedding_model.encode([query]).tolist()
            
            # Search in applications collection
            results = self.collections['applications'].query(
                query_embeddings=query_embedding,
                n_results=k,
                where={"success": True}  # Only successful applications
            )
            
            # Format results
            retrieval_results = []
            for i in range(len(results['documents'][0])):
                retrieval_results.append(RetrievalResult(
                    content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i],
                    score=1 - results['distances'][0][i],
                    source='applications'
                ))
            
            return retrieval_results
            
        except Exception as e:
            logger.error(f"Error finding similar applications: {e}")
            return []
    
    def add_knowledge(self, knowledge_type: str, content: str, metadata: Dict[str, Any] = None):
        """Add domain knowledge to vector store"""
        try:
            # Split content into chunks
            chunks = self.text_splitter.split_text(content)
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(chunks).tolist()
            
            # Prepare documents
            ids = [f"knowledge_{knowledge_type}_{hashlib.md5(chunk.encode()).hexdigest()[:8]}" 
                   for chunk in chunks]
            
            metadatas = [{
                "type": knowledge_type,
                "chunk_index": i,
                **(metadata or {})
            } for i in range(len(chunks))]
            
            # Add to ChromaDB
            self.collections['knowledge'].add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"Added {knowledge_type} knowledge with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error adding knowledge: {e}")

class RAGApplicationAssistant:
    """RAG-powered assistant for job applications"""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.session = get_session()
    
    async def generate_contextual_response(self, 
                                          question: str,
                                          job: Job,
                                          candidate: Candidate,
                                          field_name: str = None) -> str:
        """Generate contextual response using RAG"""
        
        # Get relevant context
        relevant_experience = self.vector_store.get_relevant_experience(
            f"{job.title} {job.description[:500]}", k=3
        )
        
        similar_applications = self.vector_store.find_similar_applications(job, k=2)
        
        # Build context
        context = f"""
        You are filling out a job application for:
        Job: {job.title} at {job.company}
        
        Candidate Information:
        {candidate.profile_summary}
        Skills: {', '.join(candidate.skills or [])}
        Experience: {candidate.years_experience} years
        
        Relevant Experience:
        {chr(10).join([r.content[:200] for r in relevant_experience])}
        
        Similar Successful Applications:
        {chr(10).join([r.content[:200] for r in similar_applications])}
        
        Question: {question}
        Field Name: {field_name or 'unknown'}
        """
        
        prompt = f"""
        Based on the context provided, generate an appropriate response for this job application field.
        The response should be:
        1. Truthful and based on the candidate's actual experience
        2. Tailored to the specific job requirements
        3. Professional and concise
        4. Highlighting relevant skills and achievements
        
        Context:
        {context}
        
        Generate a response that would be appropriate for this field:
        """
        
        response = await generate_llm_response(prompt, temperature=0.3, max_tokens=500)
        return response
    
    async def generate_cover_letter(self, job: Job, candidate: Candidate) -> str:
        """Generate cover letter using RAG context"""
        
        # Get relevant context
        relevant_experience = self.vector_store.get_relevant_experience(
            f"{job.title} {job.description[:500]}", k=5
        )
        
        similar_applications = self.vector_store.find_similar_applications(job, k=3)
        
        # Extract key points from context
        experience_highlights = [r.content[:150] for r in relevant_experience[:3]]
        
        prompt = f"""
        Write a compelling cover letter for this job application:
        
        Job Details:
        - Title: {job.title}
        - Company: {job.company}
        - Required Skills: {', '.join(job.required_skills or [])}
        - Description: {job.description[:500]}
        
        Candidate Profile:
        - Name: {candidate.first_name} {candidate.last_name}
        - Summary: {candidate.profile_summary}
        - Key Skills: {', '.join(candidate.skills[:10] if candidate.skills else [])}
        - Years of Experience: {candidate.years_experience}
        
        Relevant Highlights to Include:
        {chr(10).join(experience_highlights)}
        
        Write a 3-4 paragraph cover letter that:
        1. Opens with enthusiasm for the specific role and company
        2. Highlights 2-3 specific achievements that match job requirements
        3. Demonstrates knowledge of the company and role
        4. Closes with a strong call to action
        
        Cover Letter:
        """
        
        cover_letter = await generate_llm_response(prompt, temperature=0.7, max_tokens=800)
        return cover_letter
    
    def calculate_job_match_score(self, job: Job, candidate: Candidate) -> float:
        """Calculate match score between job and candidate using embeddings"""
        try:
            # Create job embedding
            job_text = f"{job.title} {job.description} {' '.join(job.required_skills or [])}"
            job_embedding = self.vector_store.embedding_model.encode([job_text])[0]
            
            # Create candidate embedding
            candidate_text = f"{candidate.profile_summary} {' '.join(candidate.skills or [])} {candidate.resume_text or ''}"
            candidate_embedding = self.vector_store.embedding_model.encode([candidate_text])[0]
            
            # Calculate cosine similarity
            similarity = np.dot(job_embedding, candidate_embedding) / (
                np.linalg.norm(job_embedding) * np.linalg.norm(candidate_embedding)
            )
            
            # Adjust score based on specific criteria
            score = similarity
            
            # Boost score for skill matches
            if job.required_skills and candidate.skills:
                skill_match = len(set(job.required_skills) & set(candidate.skills)) / len(job.required_skills)
                score = score * 0.7 + skill_match * 0.3
            
            # Adjust for experience match
            if job.experience_required and candidate.years_experience:
                if candidate.years_experience >= job.experience_required:
                    score *= 1.1
                else:
                    score *= 0.9
            
            # Adjust for location/remote preference
            if job.remote_type == 'remote' and candidate.remote_preference in ['remote_only', 'flexible']:
                score *= 1.05
            
            return min(score, 1.0)  # Cap at 1.0
            
        except Exception as e:
            logger.error(f"Error calculating match score: {e}")
            return 0.5
    
    def index_all_data(self):
        """Index all existing data in vector stores"""
        try:
            # Index all candidates
            candidates = self.session.query(Candidate).all()
            for candidate in candidates:
                self.vector_store.add_candidate_profile(candidate)
            
            # Index all jobs
            jobs = self.session.query(Job).all()
            for job in jobs:
                self.vector_store.add_job(job)
            
            # Index successful applications
            applications = self.session.query(Application).filter_by(status='submitted').all()
            for app in applications:
                self.vector_store.add_application_history(app)
            
            logger.info(f"Indexed {len(candidates)} candidates, {len(jobs)} jobs, {len(applications)} applications")
            
        except Exception as e:
            logger.error(f"Error indexing data: {e}")

# Initialize global RAG assistant
rag_assistant = RAGApplicationAssistant()

# Utility functions for external use
async def get_contextual_answer(question: str, job_context: str = "", candidate_context: str = "") -> str:
    """Get RAG-enhanced answer for a question"""
    prompt = f"""
    Job Context: {job_context}
    Candidate Context: {candidate_context}
    Question: {question}
    
    Provide a relevant, professional answer based on the context:
    """
    
    return await generate_llm_response(prompt, temperature=0.3)

def update_vector_stores():
    """Update all vector stores with latest data"""
    rag_assistant.index_all_data()
