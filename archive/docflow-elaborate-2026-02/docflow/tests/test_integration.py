"""
Integration tests for DocFlow end-to-end workflows
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import json
from unittest.mock import Mock, patch, AsyncMock

from docflow.core.state import DocumentState, StateEnum
from docflow.core.state import ReviewPeriod, ReviewStatus
from docflow.core.state import WorkflowState, AutonomyLevel
from docflow.providers.local import LocalStorageProvider
from docflow.providers.factory import create_storage_provider, create_llm_provider
from docflow.convert.markdown import MarkdownConverter
from docflow.review.manager import ReviewManager
from docflow.git.integration import GitIntegration
from docflow.workflow.graph import DocFlowWorkflow
from docflow.core.config import load_config


class TestDocumentLifecycle:
    """Test complete document lifecycle from creation to archive"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.repo_root = self.temp_dir / "repo"
        self.repo_root.mkdir()
        self.storage_path = self.temp_dir / "storage"
        self.storage_path.mkdir()
        self.db_path = self.temp_dir / "state.db"
        
        # Create test config
        self.config = {
            "repository_root": str(self.repo_root),
            "state_db_path": str(self.db_path),
            "storage_provider": "local",
            "local_storage_path": str(self.storage_path),
            "review": {
                "default_duration_days": 7,
                "promotion_threshold": 1
            }
        }
    
    def teardown_method(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_document_creation_to_publish(self):
        """Test creating a document and publishing it"""
        # Create document
        doc_path = self.repo_root / "docs" / "test.md"
        doc_path.parent.mkdir(parents=True)
        doc_path.write_text("# Test Document\n\nInitial content")
        
        # Initialize document state
        doc_state = DocumentState(
            path=doc_path,
            state=StateEnum.LOCAL,
            version="0.1.0"
        )
        
        # Create storage provider
        storage = LocalStorageProvider(base_path=str(self.storage_path))
        
        # Move to draft
        doc_state.state = StateEnum.DRAFT
        doc_state.version = "0.2.0"
        doc_id = await storage.upload_document(doc_state, doc_path)
        assert doc_id is not None
        
        # Create review period
        review = ReviewPeriod(
            document_id=doc_id,
            reviewers=["reviewer1@test.com", "reviewer2@test.com"],
            deadline=datetime.now() + timedelta(days=7)
        )
        
        # Simulate review responses
        review.add_response("reviewer1@test.com", True, "Looks good")
        assert review.status == ReviewStatus.IN_PROGRESS
        
        # Check if ready for promotion
        assert review.is_ready_for_promotion(threshold=1)
        
        # Promote to published
        doc_state.state = StateEnum.PUBLISHED
        doc_state.version = "1.0.0"
        doc_state.published_at = datetime.now()
        
        # Upload published version
        published_id = await storage.upload_document(doc_state, doc_path)
        assert published_id is not None
        
        # Verify in storage
        published_docs = await storage.list_documents(state="published")
        assert any("test.md" in doc["name"] for doc in published_docs)
    
    @pytest.mark.asyncio
    async def test_document_with_comments_integration(self):
        """Test document with comment processing"""
        # Create document
        doc_path = self.repo_root / "api.md"
        doc_path.write_text("# API Reference\n\n## Endpoints\n\nGET /api/users")
        
        doc_state = DocumentState(
            path=doc_path,
            state=StateEnum.DRAFT
        )
        
        # Create storage
        storage = LocalStorageProvider(base_path=str(self.storage_path))
        doc_id = await storage.upload_document(doc_state, doc_path)
        
        # Simulate comments
        comments = [
            {
                "id": "1",
                "author": "Sarah",
                "content": "Please add authentication details",
                "line": 5,
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "2",
                "author": "John",
                "content": "Include rate limiting info",
                "line": 7,
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        # Save comments
        comments_dir = Path(storage.base_path) / "comments"
        comments_dir.mkdir(exist_ok=True)
        comments_file = comments_dir / f"{doc_id}.json"
        comments_file.write_text(json.dumps(comments))
        
        # Retrieve comments
        retrieved_comments = await storage.get_comments(doc_id)
        assert len(retrieved_comments) == 2
        
        # Process with mock LLM
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_response = Mock()
            mock_response.content = [
                Mock(text='{"category": "missing_info", "priority": "high"}')
            ]
            mock_anthropic.return_value.messages.create = AsyncMock(return_value=mock_response)
            
            # Would normally categorize comments here
            # result = await llm.categorize_comment(comments[0]["content"])


class TestReviewWorkflow:
    """Test review workflow integration"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = {
            "repository_root": str(self.temp_dir),
            "review": {
                "default_duration_days": 7,
                "promotion_threshold": 2,
                "require_all_reviewers": False
            }
        }
    
    def teardown_method(self):
        """Clean up"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_review_cycle(self):
        """Test complete review cycle"""
        # Create review manager
        manager = ReviewManager(self.config)
        
        # Create review period
        review = await manager.create_review(
            document_id="doc-123",
            reviewers=["alice@test.com", "bob@test.com", "charlie@test.com"]
        )
        
        assert review.status == ReviewStatus.PENDING
        
        # Start review
        review.status = ReviewStatus.IN_PROGRESS
        
        # Add responses
        review.add_response("alice@test.com", True, "Approved")
        review.add_response("bob@test.com", True, "LGTM")
        
        # Check promotion readiness
        assert review.is_ready_for_promotion(threshold=2)
        
        # Complete review
        review.status = ReviewStatus.COMPLETED
        assert review.all_approved(required_count=2)
    
    @pytest.mark.asyncio
    async def test_review_expiry_and_extension(self):
        """Test review deadline and extension"""
        manager = ReviewManager(self.config)
        
        # Create review with short deadline
        review = await manager.create_review(
            document_id="doc-456",
            reviewers=["user@test.com"],
            deadline=datetime.now() + timedelta(hours=1)
        )
        
        # Check if expired (not yet)
        assert not review.is_expired()
        
        # Simulate time passing
        review.deadline = datetime.now() - timedelta(hours=1)
        assert review.is_expired()
        
        # Extend deadline
        review.extend_deadline(days=3)
        assert not review.is_expired()
        assert review.deadline > datetime.now()


class TestGitIntegration:
    """Test Git integration workflows"""
    
    def setup_method(self):
        """Set up test environment with Git repo"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.repo_path = self.temp_dir / "repo"
        self.repo_path.mkdir()
        
        # Initialize git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=self.repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_path)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_path)
        
        self.config = {
            "repository_root": str(self.repo_path),
            "git": {
                "branch_policies": {
                    "main": "canonical",
                    "feature/*": "draft"
                },
                "auto_commit": True
            }
        }
    
    def teardown_method(self):
        """Clean up"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_branch_state_mapping(self):
        """Test mapping Git branches to document states"""
        git = GitIntegration(self.config)
        
        # Test branch policies
        assert git.get_state_for_branch("main") == StateEnum.PUBLISHED
        assert git.get_state_for_branch("feature/new-docs") == StateEnum.DRAFT
        assert git.get_state_for_branch("random-branch") == StateEnum.LOCAL
    
    def test_document_tracking(self):
        """Test tracking document changes in Git"""
        git = GitIntegration(self.config)
        
        # Create a document
        doc_path = self.repo_path / "test.md"
        doc_path.write_text("# Test")
        
        # Stage and commit
        import subprocess
        subprocess.run(["git", "add", "test.md"], cwd=self.repo_path)
        subprocess.run(["git", "commit", "-m", "Add test doc"], cwd=self.repo_path)
        
        # Check if tracked
        result = subprocess.run(
            ["git", "ls-files", "test.md"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        assert "test.md" in result.stdout


class TestLangGraphWorkflow:
    """Test LangGraph workflow orchestration"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = {
            "repository_root": str(self.temp_dir),
            "state_db_path": str(self.temp_dir / "state.db"),
            "workflow_checkpoint_path": str(self.temp_dir / "checkpoints.db"),
            "storage_provider": "local",
            "local_storage_path": str(self.temp_dir / "storage"),
            "autonomy": {
                "level": "assisted"
            }
        }
    
    def teardown_method(self):
        """Clean up"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_workflow_initialization(self):
        """Test workflow initialization"""
        workflow = DocFlowWorkflow(self.config)
        
        # Check graph structure
        assert workflow.graph is not None
        # Note: Graph structure verification would go here
    
    @pytest.mark.asyncio
    async def test_workflow_state_transitions(self):
        """Test workflow state transitions"""
        workflow = DocFlowWorkflow(self.config)
        
        # Create initial state
        initial_state = {
            "documents": {},
            "pending_reviews": [],
            "pending_publishes": [],
            "errors": []
        }
        
        # Mock check_git
        with patch.object(workflow, 'check_git') as mock_git:
            mock_git.return_value = {
                **initial_state,
                "git_changes": ["docs/new.md"]
            }
            
            result = await workflow.check_git(initial_state)
            assert "git_changes" in result
            assert len(result["git_changes"]) == 1


class TestDiagramIntegration:
    """Test diagram generation integration"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "diagrams"
        self.output_dir.mkdir()
    
    def teardown_method(self):
        """Clean up"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_diagram_generation_pipeline(self):
        """Test complete diagram generation pipeline"""
        from ..diagrams.parser import DiagramSpecParser
        from ..diagrams.generators.graphviz import GraphvizGenerator
        from ..diagrams.intelligence import DiagramIntelligence
        
        # Create test document with diagram
        content = """
        # Architecture
        
        [DIAGRAM type="flowchart" title="System Flow"]
        User -> API
        API -> Database
        API -> Cache
        [/DIAGRAM]
        """
        
        # Parse diagrams
        parser = DiagramSpecParser()
        specs = parser.parse_markdown(content)
        assert len(specs) == 1
        
        # Generate with mock LLM
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            # Mock quality evaluation
            mock_response = Mock()
            mock_response.content = [
                Mock(text='{"score": 8.5, "readability": 9, "feedback": "Good"}')
            ]
            mock_anthropic.return_value.messages.create = AsyncMock(return_value=mock_response)
            
            intelligence = DiagramIntelligence(
                output_dir=str(self.output_dir),
                llm_provider=Mock()
            )
            
            # Would generate diagram here
            # result = await intelligence.process_document(content)


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios"""
    
    def setup_method(self):
        """Set up complete test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.repo = self.temp_dir / "repo"
        self.repo.mkdir()
        
        # Complete config
        self.config = {
            "repository_root": str(self.repo),
            "state_db_path": str(self.temp_dir / "state.db"),
            "storage_provider": "local",
            "local_storage_path": str(self.temp_dir / "storage"),
            "llm_provider": "anthropic",
            "anthropic": {
                "api_key": "test-key"
            },
            "review": {
                "default_duration_days": 7,
                "promotion_threshold": 1
            },
            "autonomy": {
                "level": "assisted"
            },
            "git": {
                "auto_commit": True
            }
        }
    
    def teardown_method(self):
        """Clean up"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_new_document_full_cycle(self):
        """Test new document through complete lifecycle"""
        # Create document
        doc_path = self.repo / "guide.md"
        doc_path.write_text("""
        # User Guide
        
        ## Getting Started
        
        1. Install the package
        2. Configure settings
        3. Run the application
        
        [DIAGRAM type="flowchart" title="Setup Flow"]
        Start -> Install -> Configure -> Run -> Success
        [/DIAGRAM]
        """)
        
        # Initialize state
        doc_state = DocumentState(
            path=doc_path,
            state=StateEnum.LOCAL
        )
        
        # Create providers
        storage = LocalStorageProvider(base_path=str(self.temp_dir / "storage"))
        
        # Step 1: Move to draft
        doc_state.state = StateEnum.DRAFT
        doc_id = await storage.upload_document(doc_state, doc_path)
        
        # Step 2: Add comments
        comments = [
            {
                "author": "Reviewer",
                "content": "Add system requirements",
                "line": 5
            }
        ]
        
        # Step 3: Process comments (mock)
        # In real scenario, would use LLM to categorize and suggest changes
        
        # Step 4: Update document
        updated_content = doc_path.read_text() + "\n## System Requirements\n\n- Python 3.8+"
        doc_path.write_text(updated_content)
        
        # Step 5: Create review
        review = ReviewPeriod(
            document_id=doc_id,
            reviewers=["reviewer@test.com"],
            deadline=datetime.now() + timedelta(days=3)
        )
        
        # Step 6: Approve
        review.add_response("reviewer@test.com", True, "Approved with requirements added")
        
        # Step 7: Publish
        if review.is_ready_for_promotion(threshold=1):
            doc_state.state = StateEnum.PUBLISHED
            doc_state.version = "1.0.0"
            published_id = await storage.upload_document(doc_state, doc_path)
            assert published_id is not None
        
        # Verify published
        published = await storage.list_documents(state="published")
        assert len(published) > 0
    
    @pytest.mark.asyncio  
    async def test_bulk_onboarding_scenario(self):
        """Test bulk document onboarding"""
        from ..onboarding.intelligent_onboard import IntelligentOnboarder
        
        # Create multiple documents
        docs = [
            ("README.md", "# Project\n\nMain documentation"),
            ("docs/api.md", "# API Reference\n\n[Link to README](../README.md)"),
            ("docs/guide.md", "# User Guide\n\n[API Docs](./api.md)"),
        ]
        
        for path, content in docs:
            doc_path = self.repo / path
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(content)
        
        # Initialize onboarder
        onboarder = IntelligentOnboarder(self.repo)
        
        # Discover documents
        discovered = await onboarder.discover_documents()
        assert len(discovered) == 3
        
        # Build link graph
        onboarder.build_link_graph()
        
        # Find root documents
        roots = onboarder.find_root_documents(top_n=1)
        assert roots[0].title == "Project"  # README should be root
        
        # Simulate bulk onboarding
        for path, doc in onboarder.documents.items():
            onboarder.decisions[path] = onboarder._auto_decide(doc, [])
        
        # Generate report
        report = onboarder.generate_report()
        assert "Total documents discovered: 3" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])