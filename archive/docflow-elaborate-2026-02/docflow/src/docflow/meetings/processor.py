"""Meeting intelligence and transcript processing."""

import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from ..providers import LLMProvider, EmbeddingProvider
from ..embedding.pipeline import EmbeddingPipeline

logger = logging.getLogger(__name__)


@dataclass
class MeetingTranscript:
    """Represents a meeting transcript."""
    
    title: str
    date: datetime
    participants: list[str]
    content: str
    source_file: Optional[Path] = None


@dataclass
class Decision:
    """Extracted decision from meeting."""
    
    title: str
    description: str
    owner: Optional[str] = None
    deadline: Optional[str] = None


@dataclass
class ActionItem:
    """Extracted action item from meeting."""
    
    description: str
    owner: Optional[str] = None
    deadline: Optional[str] = None


class MeetingProcessor:
    """Process meeting transcripts and extract actionable insights."""
    
    def __init__(self, llm_provider: LLMProvider, 
                 embedding_provider: Optional[EmbeddingProvider] = None):
        """Initialize meeting processor.
        
        Args:
            llm_provider: LLM provider for extraction/analysis
            embedding_provider: Optional embedding provider for document matching
        """
        self.llm = llm_provider
        self.embedding = embedding_provider
        self.embedding_pipeline = EmbeddingPipeline(embedding_provider)
    
    def process_transcript(self, transcript: MeetingTranscript) -> dict:
        """Process a meeting transcript and extract insights.
        
        Args:
            transcript: MeetingTranscript object
        
        Returns:
            Dict with extracted decisions and action items
        """
        try:
            # Extract decisions and action items
            decisions = self._extract_decisions(transcript.content)
            action_items = self._extract_action_items(transcript.content)
            
            # Find relevant documents
            relevant_docs = self._match_to_documents(
                transcript.content,
                decisions + [f"{a.description}" for a in action_items]
            )
            
            return {
                "transcript_title": transcript.title,
                "date": transcript.date.isoformat(),
                "participants": transcript.participants,
                "decisions": [
                    {
                        "title": d.title,
                        "description": d.description,
                        "owner": d.owner,
                        "deadline": d.deadline,
                    }
                    for d in decisions
                ],
                "action_items": [
                    {
                        "description": a.description,
                        "owner": a.owner,
                        "deadline": a.deadline,
                    }
                    for a in action_items
                ],
                "relevant_documents": relevant_docs,
            }
        
        except Exception as e:
            logger.error(f"Failed to process transcript: {e}")
            return {}
    
    def _extract_decisions(self, transcript: str) -> list[Decision]:
        """Extract decisions from transcript using LLM.
        
        Args:
            transcript: Meeting transcript content
        
        Returns:
            List of Decision objects
        """
        prompt = f"""Extract all major decisions made during this meeting.
For each decision, provide:
1. Title (short phrase)
2. Description (1-2 sentences)
3. Owner (who's responsible for implementing)
4. Deadline (if mentioned)

Meeting transcript:
{transcript[:2000]}...

Respond with JSON: {{"decisions": [{{"title": "...", "description": "...", "owner": "...", "deadline": "..."}}]}}"""
        
        try:
            result = self.llm.complete_structured(prompt, {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "owner": {"type": "string"},
                                "deadline": {"type": "string"},
                            }
                        }
                    }
                }
            })
            
            decisions = []
            for d in result.get("decisions", []):
                decisions.append(Decision(
                    title=d.get("title", ""),
                    description=d.get("description", ""),
                    owner=d.get("owner"),
                    deadline=d.get("deadline"),
                ))
            
            return decisions
        
        except Exception as e:
            logger.error(f"Failed to extract decisions: {e}")
            return []
    
    def _extract_action_items(self, transcript: str) -> list[ActionItem]:
        """Extract action items from transcript using LLM.
        
        Args:
            transcript: Meeting transcript content
        
        Returns:
            List of ActionItem objects
        """
        prompt = f"""Extract all action items from this meeting transcript.
For each action, provide:
1. Description (what needs to be done)
2. Owner (who's doing it)
3. Deadline (if mentioned)

Be specific and concise.

Meeting transcript:
{transcript[:2000]}...

Respond with JSON: {{"actions": [{{"description": "...", "owner": "...", "deadline": "..."}}]}}"""
        
        try:
            result = self.llm.complete_structured(prompt, {
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "owner": {"type": "string"},
                                "deadline": {"type": "string"},
                            }
                        }
                    }
                }
            })
            
            actions = []
            for a in result.get("actions", []):
                actions.append(ActionItem(
                    description=a.get("description", ""),
                    owner=a.get("owner"),
                    deadline=a.get("deadline"),
                ))
            
            return actions
        
        except Exception as e:
            logger.error(f"Failed to extract action items: {e}")
            return []
    
    def _match_to_documents(self, transcript_content: str, items: list[str]) -> list[dict]:
        """Match extracted items to relevant documents.
        
        Args:
            transcript_content: Full transcript
            items: Extracted decisions/actions
        
        Returns:
            List of matching document references
        """
        if not self.embedding_pipeline.provider:
            logger.debug("Embedding disabled, skipping document matching")
            return []
        
        try:
            relevant = []
            
            # Combine all items into search query
            search_query = " ".join(items[:5])  # Use first 5 items
            
            # Search embeddings
            results = self.embedding_pipeline.search(search_query, k=5)
            
            for result in results:
                doc_id = result.get("metadata", {}).get("doc_id", "unknown")
                score = result.get("score", 0.0)
                
                # Only include high-confidence matches
                if score > 0.7:  # Threshold
                    relevant.append({
                        "doc_id": doc_id,
                        "relevance_score": score,
                        "snippet": result.get("text", "")[:100],
                    })
            
            return relevant
        
        except Exception as e:
            logger.error(f"Document matching failed: {e}")
            return []
    
    def propose_updates(self, decisions: list[dict], doc_id: str) -> list[dict]:
        """Propose document updates based on meeting decisions.
        
        Args:
            decisions: List of decision dicts
            doc_id: Target document ID
        
        Returns:
            List of proposed changes
        """
        prompt = f"""Based on these meeting decisions, what updates should be made to the document?

Decisions:
{chr(10).join(f'- {d.get("title", "")}: {d.get("description", "")}' for d in decisions)}

Suggest specific changes to the document, including:
1. Sections to update
2. New content to add
3. Sections to clarify

Respond as a bullet list of concrete suggestions."""
        
        try:
            suggestions = self.llm.complete(prompt)
            
            # Parse suggestions into structured format
            proposals = []
            for line in suggestions.split("\n"):
                if line.strip().startswith("-"):
                    proposals.append({
                        "type": "suggested_update",
                        "suggestion": line.strip()[2:],  # Remove "- "
                        "doc_id": doc_id,
                    })
            
            return proposals
        
        except Exception as e:
            logger.error(f"Failed to generate update proposals: {e}")
            return []
