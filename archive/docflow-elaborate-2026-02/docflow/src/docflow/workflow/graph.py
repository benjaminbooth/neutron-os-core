"""LangGraph workflow orchestration for autonomous DocFlow operations."""

import asyncio
from typing import TypedDict, Annotated, Literal
from datetime import datetime, timedelta
from pathlib import Path
import logging

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver

from ..core.state import DocumentState, WorkflowState, ReviewStatus
from ..core.config import ConfigManager
from ..core.persistence import StatePersistence
from ..providers.factory import get_provider
from ..review.manager import ReviewManager
from ..git.integration import GitIntegration
from ..embedding.pipeline import EmbeddingPipeline
from ..meetings.processor import MeetingProcessor
from ..diagrams import DiagramIntelligence
from ..convert.comment_extractor import DocxCommentExtractor

logger = logging.getLogger(__name__)


class WorkflowStateDict(TypedDict):
    """State for the workflow graph."""
    
    # Core workflow state
    documents: list[DocumentState]
    pending_reviews: list[str]  # Document IDs with pending reviews
    pending_comments: list[dict]  # Comments to incorporate
    pending_meetings: list[str]  # Meeting transcripts to process
    
    # Execution context
    current_step: str
    last_run: datetime
    next_run: datetime
    errors: list[str]
    
    # Decisions made by agents
    decisions: dict[str, str]
    
    # Control flow
    should_continue: bool
    should_notify: bool


class DocFlowWorkflow:
    """Main workflow orchestrator using LangGraph."""
    
    def __init__(self, config_path: Path = None):
        """Initialize the workflow.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = ConfigManager(config_path or Path(".doc-workflow.yaml"))
        
        # Initialize providers
        self.storage = get_provider("storage", self.config.storage_provider)
        self.llm = get_provider("llm", self.config.llm_provider)
        self.notification = get_provider("notification", self.config.notification_provider)
        self.embedding = get_provider("embedding", self.config.embedding_provider)
        
        # Initialize managers
        self.persistence = StatePersistence(self.config.state_db_path)
        self.review_manager = ReviewManager(self.config, self.persistence)
        self.git = GitIntegration(self.config.git_repo_path)
        self.embedding_pipeline = EmbeddingPipeline(self.embedding, self.llm)
        self.meeting_processor = MeetingProcessor(self.llm, self.persistence)
        self.diagram_intelligence = DiagramIntelligence(
            self.llm,
            self.config.design_system
        )
        
        # Build the graph
        self.graph = self._build_graph()
        
        # Checkpointing for persistence
        self.checkpointer = SqliteSaver.from_path(
            str(self.config.workflow_checkpoint_path)
        )
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow.
        
        Nodes:
        - check_git: Check for new commits
        - poll_storage: Check OneDrive/storage for changes
        - fetch_comments: Extract comments from documents
        - analyze_feedback: Categorize and prioritize feedback
        - update_documents: Apply changes to markdown
        - generate_diagrams: Create/update diagrams
        - publish: Upload to storage
        - check_reviews: Check review deadlines and status
        - process_meetings: Extract decisions from meeting transcripts
        - update_embeddings: Update vector store
        - send_notifications: Send email/Teams updates
        
        Edges define the flow between nodes based on conditions.
        """
        workflow = StateGraph(WorkflowStateDict)
        
        # Add nodes
        workflow.add_node("check_git", self._check_git)
        workflow.add_node("poll_storage", self._poll_storage)
        workflow.add_node("fetch_comments", self._fetch_comments)
        workflow.add_node("analyze_feedback", self._analyze_feedback)
        workflow.add_node("update_documents", self._update_documents)
        workflow.add_node("generate_diagrams", self._generate_diagrams)
        workflow.add_node("publish", self._publish)
        workflow.add_node("check_reviews", self._check_reviews)
        workflow.add_node("process_meetings", self._process_meetings)
        workflow.add_node("update_embeddings", self._update_embeddings)
        workflow.add_node("send_notifications", self._send_notifications)
        
        # Define edges
        workflow.set_entry_point("check_git")
        
        # From check_git
        workflow.add_edge("check_git", "poll_storage")
        
        # From poll_storage
        workflow.add_conditional_edges(
            "poll_storage",
            self._route_after_poll,
            {
                "fetch_comments": "fetch_comments",
                "check_reviews": "check_reviews",
                "continue": "check_reviews",
            }
        )
        
        # From fetch_comments
        workflow.add_edge("fetch_comments", "analyze_feedback")
        
        # From analyze_feedback
        workflow.add_conditional_edges(
            "analyze_feedback",
            self._route_after_analysis,
            {
                "update_documents": "update_documents",
                "check_reviews": "check_reviews",
            }
        )
        
        # From update_documents
        workflow.add_edge("update_documents", "generate_diagrams")
        
        # From generate_diagrams
        workflow.add_edge("generate_diagrams", "publish")
        
        # From publish
        workflow.add_edge("publish", "update_embeddings")
        
        # From check_reviews
        workflow.add_conditional_edges(
            "check_reviews",
            self._route_after_reviews,
            {
                "process_meetings": "process_meetings",
                "update_embeddings": "update_embeddings",
            }
        )
        
        # From process_meetings
        workflow.add_edge("process_meetings", "update_embeddings")
        
        # From update_embeddings
        workflow.add_conditional_edges(
            "update_embeddings",
            self._route_to_notifications,
            {
                "send_notifications": "send_notifications",
                "end": END,
            }
        )
        
        # From send_notifications
        workflow.add_edge("send_notifications", END)
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def _check_git(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Check for new commits in git repository."""
        logger.info("Checking git for changes...")
        
        try:
            # Get changed files since last run
            changed_files = self.git.get_changed_files_since(state.get("last_run"))
            
            if changed_files:
                logger.info(f"Found {len(changed_files)} changed files")
                
                # Load or create document states for changed files
                for file_path in changed_files:
                    if file_path.suffix == '.md':
                        doc_state = self.persistence.load_state(str(file_path))
                        if doc_state is None:
                            doc_state = DocumentState(
                                source_path=file_path,
                                markdown=file_path.read_text(),
                            )
                        
                        if doc_state not in state["documents"]:
                            state["documents"].append(doc_state)
        
        except Exception as e:
            logger.error(f"Git check failed: {e}")
            state["errors"].append(f"Git check error: {str(e)}")
        
        state["current_step"] = "check_git"
        return state
    
    async def _poll_storage(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Poll storage provider for changes."""
        logger.info("Polling storage for changes...")
        
        try:
            # Get recent documents with comments
            docs_with_comments = await self.storage.get_documents_with_comments(
                since=state.get("last_run")
            )
            
            if docs_with_comments:
                logger.info(f"Found {len(docs_with_comments)} documents with new comments")
                state["pending_comments"].extend(docs_with_comments)
        
        except Exception as e:
            logger.error(f"Storage poll failed: {e}")
            state["errors"].append(f"Storage poll error: {str(e)}")
        
        state["current_step"] = "poll_storage"
        return state
    
    async def _fetch_comments(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Extract comments from documents."""
        logger.info("Fetching comments from documents...")
        
        for doc_info in state["pending_comments"]:
            try:
                # Download document
                local_path = await self.storage.download(
                    doc_info["remote_path"],
                    Path("/tmp") / doc_info["name"]
                )
                
                # Extract comments
                extractor = DocxCommentExtractor()
                comments = extractor.extract_comments(local_path)
                
                # Add to state
                for comment in comments:
                    comment["document_id"] = doc_info["id"]
                    state["pending_comments"].append(comment)
                
                logger.info(f"Extracted {len(comments)} comments from {doc_info['name']}")
            
            except Exception as e:
                logger.error(f"Comment extraction failed for {doc_info['name']}: {e}")
                state["errors"].append(f"Comment extraction error: {str(e)}")
        
        state["current_step"] = "fetch_comments"
        return state
    
    async def _analyze_feedback(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Use LLM to analyze and categorize feedback."""
        logger.info("Analyzing feedback with LLM...")
        
        try:
            for comment in state["pending_comments"]:
                # Categorize comment
                category = await self.llm.categorize_comment(
                    comment["text"],
                    comment.get("context", "")
                )
                comment["category"] = category
                
                # Determine if actionable
                if category in ["error", "clarification", "enhancement"]:
                    comment["actionable"] = True
                else:
                    comment["actionable"] = False
                
                logger.debug(f"Comment categorized as {category}: {comment['text'][:50]}...")
        
        except Exception as e:
            logger.error(f"Feedback analysis failed: {e}")
            state["errors"].append(f"Analysis error: {str(e)}")
        
        state["current_step"] = "analyze_feedback"
        return state
    
    async def _update_documents(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Apply actionable feedback to documents."""
        logger.info("Updating documents with feedback...")
        
        # Group comments by document
        comments_by_doc = {}
        for comment in state["pending_comments"]:
            if comment.get("actionable"):
                doc_id = comment["document_id"]
                if doc_id not in comments_by_doc:
                    comments_by_doc[doc_id] = []
                comments_by_doc[doc_id].append(comment)
        
        # Apply changes to each document
        for doc_id, comments in comments_by_doc.items():
            try:
                # Find document state
                doc_state = next(
                    (d for d in state["documents"] if d.id == doc_id),
                    None
                )
                
                if doc_state:
                    # Use LLM to suggest changes
                    changes = await self.llm.suggest_document_changes(
                        doc_state.markdown,
                        comments
                    )
                    
                    # Apply changes
                    if changes:
                        doc_state.markdown = changes["updated_markdown"]
                        doc_state.last_modified = datetime.now()
                        
                        # Save state
                        self.persistence.save_state(doc_state)
                        
                        logger.info(f"Updated document {doc_id} with {len(comments)} comments")
            
            except Exception as e:
                logger.error(f"Document update failed for {doc_id}: {e}")
                state["errors"].append(f"Update error: {str(e)}")
        
        state["current_step"] = "update_documents"
        return state
    
    async def _generate_diagrams(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Generate diagrams for documents that need them."""
        logger.info("Generating diagrams...")
        
        for doc_state in state["documents"]:
            try:
                if "[DIAGRAM]" in doc_state.markdown:
                    # Generate diagrams
                    output_dir = Path(doc_state.source_path).parent / ".diagrams"
                    updated_markdown, diagram_files = await self.diagram_intelligence.process_document(
                        doc_state.markdown,
                        output_dir
                    )
                    
                    # Update document
                    doc_state.markdown = updated_markdown
                    doc_state.attachments = diagram_files
                    
                    logger.info(f"Generated {len(diagram_files)} diagrams for {doc_state.source_path}")
            
            except Exception as e:
                logger.error(f"Diagram generation failed for {doc_state.source_path}: {e}")
                state["errors"].append(f"Diagram error: {str(e)}")
        
        state["current_step"] = "generate_diagrams"
        return state
    
    async def _publish(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Publish updated documents to storage."""
        logger.info("Publishing documents...")
        
        for doc_state in state["documents"]:
            try:
                if doc_state.last_modified > state.get("last_run", datetime.min):
                    # Convert to DOCX and upload
                    await self.review_manager.publish_document(doc_state)
                    
                    logger.info(f"Published {doc_state.source_path}")
            
            except Exception as e:
                logger.error(f"Publishing failed for {doc_state.source_path}: {e}")
                state["errors"].append(f"Publish error: {str(e)}")
        
        state["current_step"] = "publish"
        return state
    
    async def _check_reviews(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Check review deadlines and status."""
        logger.info("Checking review status...")
        
        try:
            # Get active reviews
            active_reviews = self.review_manager.get_active_reviews()
            
            for review in active_reviews:
                # Check if deadline approaching
                if review.deadline - datetime.now() < timedelta(days=1):
                    state["pending_reviews"].append(review.document_id)
                    state["should_notify"] = True
                    
                    logger.warning(f"Review deadline approaching for {review.document_id}")
        
        except Exception as e:
            logger.error(f"Review check failed: {e}")
            state["errors"].append(f"Review check error: {str(e)}")
        
        state["current_step"] = "check_reviews"
        return state
    
    async def _process_meetings(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Process meeting transcripts to extract decisions."""
        logger.info("Processing meeting transcripts...")
        
        for transcript_path in state["pending_meetings"]:
            try:
                # Process transcript
                decisions = await self.meeting_processor.process_transcript(
                    Path(transcript_path)
                )
                
                # Store decisions
                for decision in decisions:
                    state["decisions"][decision["id"]] = decision["text"]
                
                logger.info(f"Extracted {len(decisions)} decisions from meeting")
            
            except Exception as e:
                logger.error(f"Meeting processing failed: {e}")
                state["errors"].append(f"Meeting error: {str(e)}")
        
        state["current_step"] = "process_meetings"
        return state
    
    async def _update_embeddings(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Update vector store with new content."""
        logger.info("Updating embeddings...")
        
        for doc_state in state["documents"]:
            try:
                if doc_state.last_modified > state.get("last_run", datetime.min):
                    # Update embeddings
                    await self.embedding_pipeline.process_document(
                        doc_state.source_path,
                        doc_state.markdown
                    )
                    
                    logger.info(f"Updated embeddings for {doc_state.source_path}")
            
            except Exception as e:
                logger.error(f"Embedding update failed: {e}")
                state["errors"].append(f"Embedding error: {str(e)}")
        
        state["current_step"] = "update_embeddings"
        return state
    
    async def _send_notifications(self, state: WorkflowStateDict) -> WorkflowStateDict:
        """Send notifications to stakeholders."""
        logger.info("Sending notifications...")
        
        if state["should_notify"]:
            try:
                # Prepare notification content
                notification = {
                    "subject": "DocFlow Update",
                    "pending_reviews": state["pending_reviews"],
                    "errors": state["errors"],
                    "decisions": state["decisions"],
                }
                
                # Send via configured provider
                await self.notification.send_update(notification)
                
                logger.info("Notifications sent")
            
            except Exception as e:
                logger.error(f"Notification failed: {e}")
                state["errors"].append(f"Notification error: {str(e)}")
        
        state["current_step"] = "send_notifications"
        return state
    
    # Routing functions
    def _route_after_poll(self, state: WorkflowStateDict) -> Literal["fetch_comments", "check_reviews", "continue"]:
        """Route after polling storage."""
        if state["pending_comments"]:
            return "fetch_comments"
        return "check_reviews"
    
    def _route_after_analysis(self, state: WorkflowStateDict) -> Literal["update_documents", "check_reviews"]:
        """Route after analyzing feedback."""
        actionable = any(c.get("actionable") for c in state["pending_comments"])
        if actionable:
            return "update_documents"
        return "check_reviews"
    
    def _route_after_reviews(self, state: WorkflowStateDict) -> Literal["process_meetings", "update_embeddings"]:
        """Route after checking reviews."""
        if state["pending_meetings"]:
            return "process_meetings"
        return "update_embeddings"
    
    def _route_to_notifications(self, state: WorkflowStateDict) -> Literal["send_notifications", "end"]:
        """Route to notifications or end."""
        if state["should_notify"] or state["errors"]:
            return "send_notifications"
        return "end"
    
    async def run(self, initial_state: WorkflowStateDict = None) -> WorkflowStateDict:
        """Run the workflow.
        
        Args:
            initial_state: Initial state or None to start fresh
        
        Returns:
            Final workflow state
        """
        if initial_state is None:
            initial_state = WorkflowStateDict(
                documents=[],
                pending_reviews=[],
                pending_comments=[],
                pending_meetings=[],
                current_step="start",
                last_run=datetime.now() - timedelta(hours=1),
                next_run=datetime.now() + timedelta(hours=1),
                errors=[],
                decisions={},
                should_continue=True,
                should_notify=False,
            )
        
        # Run the graph
        config = {"configurable": {"thread_id": "docflow-main"}}
        result = await self.graph.ainvoke(initial_state, config)
        
        # Update last run time
        result["last_run"] = datetime.now()
        
        return result
    
    async def run_daemon(self, interval_minutes: int = 30):
        """Run workflow as a daemon.
        
        Args:
            interval_minutes: Minutes between runs
        """
        logger.info(f"Starting DocFlow daemon (interval: {interval_minutes} minutes)")
        
        state = None
        while True:
            try:
                # Run workflow
                state = await self.run(state)
                
                # Log results
                if state["errors"]:
                    logger.error(f"Workflow completed with {len(state['errors'])} errors")
                else:
                    logger.info("Workflow completed successfully")
                
                # Sleep until next run
                await asyncio.sleep(interval_minutes * 60)
            
            except KeyboardInterrupt:
                logger.info("Daemon stopped by user")
                break
            except Exception as e:
                logger.error(f"Daemon error: {e}")
                await asyncio.sleep(60)  # Short sleep on error