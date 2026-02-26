"""
Unit tests for provider implementations
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path
import tempfile
import shutil
from datetime import datetime
import json

from docflow.providers.base import StorageProvider, NotificationProvider, EmbeddingProvider, LLMProvider
from docflow.providers.local import LocalStorageProvider
from docflow.providers.onedrive import OneDriveProvider
from docflow.llm.anthropic_provider import AnthropicProvider
from docflow.core.state import DocumentState, StateEnum


class TestLocalStorageProvider:
    """Test LocalStorageProvider implementation"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = LocalStorageProvider(base_path=self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_upload_document(self):
        """Test document upload"""
        # Create test document
        test_path = Path(self.temp_dir) / "test.md"
        test_path.write_text("# Test Document\nContent here")
        
        doc_state = DocumentState(
            path=test_path,
            state=StateEnum.DRAFT,
            version="1.0.0"
        )
        
        # Upload
        doc_id = await self.storage.upload_document(doc_state, test_path)
        
        assert doc_id is not None
        assert (Path(self.storage.base_path) / "draft" / "test.md").exists()
    
    @pytest.mark.asyncio
    async def test_download_document(self):
        """Test document download"""
        # Create document in storage
        draft_dir = Path(self.storage.base_path) / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        test_file = draft_dir / "test.md"
        test_file.write_text("# Downloaded\nContent")
        
        # Download
        local_path = Path(self.temp_dir) / "downloaded.md"
        await self.storage.download_document("draft/test.md", local_path)
        
        assert local_path.exists()
        assert local_path.read_text() == "# Downloaded\nContent"
    
    @pytest.mark.asyncio
    async def test_list_documents(self):
        """Test listing documents"""
        # Create test documents
        for state in ["draft", "published"]:
            dir_path = Path(self.storage.base_path) / state
            dir_path.mkdir(parents=True, exist_ok=True)
            for i in range(3):
                (dir_path / f"doc{i}.md").write_text(f"Document {i}")
        
        # List all
        docs = await self.storage.list_documents()
        assert len(docs) == 6
        
        # List by state
        drafts = await self.storage.list_documents(state="draft")
        assert len(drafts) == 3
    
    @pytest.mark.asyncio
    async def test_get_comments(self):
        """Test getting comments"""
        # Create comments file
        comments_dir = Path(self.storage.base_path) / "comments"
        comments_dir.mkdir(parents=True, exist_ok=True)
        comments_file = comments_dir / "test.md.json"
        
        test_comments = [
            {
                "id": "1",
                "author": "Test User",
                "content": "Please clarify this section",
                "timestamp": datetime.now().isoformat(),
                "line": 5
            }
        ]
        comments_file.write_text(json.dumps(test_comments))
        
        # Get comments
        comments = await self.storage.get_comments("test.md")
        assert len(comments) == 1
        assert comments[0]["content"] == "Please clarify this section"
    
    @pytest.mark.asyncio
    async def test_sync_status(self):
        """Test sync status"""
        # Create document with metadata
        doc_path = Path(self.storage.base_path) / "published" / "test.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text("# Test")
        
        meta_path = doc_path.with_suffix(".md.meta")
        metadata = {
            "last_sync": datetime.now().isoformat(),
            "version": "1.0.0",
            "checksum": "abc123"
        }
        meta_path.write_text(json.dumps(metadata))
        
        # Check sync
        status = await self.storage.get_sync_status("published/test.md")
        assert status["synced"] == True
        assert "last_sync" in status


class TestOneDriveProvider:
    """Test OneDriveProvider implementation"""
    
    def setup_method(self):
        """Set up test environment"""
        self.provider = OneDriveProvider(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret"
        )
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_authenticate(self, mock_session):
        """Test authentication flow"""
        # Mock token response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            'access_token': 'test-token',
            'expires_in': 3600
        })
        mock_response.status = 200
        
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
        
        # Authenticate
        token = await self.provider._get_access_token()
        assert token == 'test-token'
    
    @pytest.mark.asyncio
    @patch.object(OneDriveProvider, '_get_access_token', return_value='test-token')
    @patch('aiohttp.ClientSession')
    async def test_upload_document(self, mock_session, mock_token):
        """Test document upload to OneDrive"""
        # Mock upload response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            'id': 'doc-123',
            'name': 'test.md',
            'webUrl': 'https://onedrive.com/test.md'
        })
        mock_response.status = 201
        
        mock_session.return_value.__aenter__.return_value.put.return_value.__aenter__.return_value = mock_response
        
        # Create test document
        test_path = Path("/tmp/test.md")
        test_path.write_text("# Test")
        
        doc_state = DocumentState(
            path=test_path,
            state=StateEnum.PUBLISHED
        )
        
        # Upload
        doc_id = await self.provider.upload_document(doc_state, test_path)
        assert doc_id == 'doc-123'
    
    @pytest.mark.asyncio
    @patch.object(OneDriveProvider, '_get_access_token', return_value='test-token')
    @patch('aiohttp.ClientSession')
    async def test_get_comments(self, mock_session, mock_token):
        """Test getting comments from OneDrive"""
        # Mock comments response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            'value': [
                {
                    'id': 'comment-1',
                    'content': 'Please review',
                    'createdBy': {'user': {'displayName': 'John Doe'}},
                    'createdDateTime': '2024-01-01T10:00:00Z'
                }
            ]
        })
        mock_response.status = 200
        
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        # Get comments
        comments = await self.provider.get_comments('doc-123')
        assert len(comments) == 1
        assert comments[0]['content'] == 'Please review'


class TestAnthropicProvider:
    """Test AnthropicProvider implementation"""
    
    def setup_method(self):
        """Set up test environment"""
        self.provider = AnthropicProvider(api_key="test-key")
    
    @pytest.mark.asyncio
    @patch('anthropic.AsyncAnthropic')
    async def test_categorize_comment(self, mock_client):
        """Test comment categorization"""
        # Mock response
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"category": "clarification", "confidence": 0.95}')
        ]
        
        mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)
        
        # Categorize
        result = await self.provider.categorize_comment(
            "This section is unclear",
            "# Document\nSome content here"
        )
        
        assert result["category"] == "clarification"
        assert result["confidence"] == 0.95
    
    @pytest.mark.asyncio
    @patch('anthropic.AsyncAnthropic')
    async def test_suggest_change(self, mock_client):
        """Test change suggestion"""
        # Mock response
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='Updated clearer content')
        ]
        
        mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)
        
        # Suggest change
        result = await self.provider.suggest_change(
            "Make this clearer",
            "Unclear content",
            {"line_start": 5, "line_end": 7}
        )
        
        assert "Updated clearer content" in result
    
    @pytest.mark.asyncio
    @patch('anthropic.AsyncAnthropic')
    async def test_analyze_feedback(self, mock_client):
        """Test feedback analysis"""
        # Mock response
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps({
                "summary": "Multiple reviewers request clarification",
                "themes": ["clarity", "examples needed"],
                "priority": "high",
                "suggested_actions": ["Add examples", "Simplify language"]
            }))
        ]
        
        mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)
        
        # Analyze feedback
        feedback = [
            {"content": "Unclear", "author": "User1"},
            {"content": "Needs examples", "author": "User2"}
        ]
        
        result = await self.provider.analyze_feedback(feedback)
        assert result["priority"] == "high"
        assert "clarity" in result["themes"]


class TestNotificationProvider:
    """Test notification provider implementations"""
    
    @pytest.mark.asyncio
    @patch('smtplib.SMTP')
    async def test_email_notification(self, mock_smtp):
        """Test email notification sending"""
        from ..providers.email import EmailNotificationProvider
        
        provider = EmailNotificationProvider(
            smtp_server="smtp.test.com",
            smtp_port=587,
            sender="docflow@test.com",
            password="test-pass"
        )
        
        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # Send notification
        await provider.send_notification(
            recipients=["user@test.com"],
            subject="Test Notification",
            body="This is a test",
            priority="high"
        )
        
        mock_server.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_teams_notification(self, mock_session):
        """Test Teams webhook notification"""
        from ..providers.teams import TeamsNotificationProvider
        
        provider = TeamsNotificationProvider(
            webhook_url="https://teams.webhook.url"
        )
        
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
        
        # Send notification
        await provider.send_notification(
            recipients=[],  # Teams uses webhook, not individual recipients
            subject="Test Alert",
            body="Document needs review",
            priority="normal"
        )
        
        mock_session.return_value.__aenter__.return_value.post.assert_called_once()


class TestEmbeddingProvider:
    """Test embedding provider implementations"""
    
    @pytest.mark.asyncio
    async def test_chroma_embedding(self):
        """Test ChromaDB embedding provider"""
        from ..providers.chroma import ChromaEmbeddingProvider
        
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = ChromaEmbeddingProvider(
                persist_directory=temp_dir,
                collection_name="test_docs"
            )
            
            # Store embedding
            await provider.store_embedding(
                doc_id="doc-1",
                chunks=["This is chunk 1", "This is chunk 2"],
                metadata={"title": "Test Doc", "state": "published"}
            )
            
            # Query similar
            results = await provider.query_similar(
                query="chunk content",
                top_k=2
            )
            
            assert len(results) <= 2
            assert all('doc_id' in r for r in results)
    
    @pytest.mark.asyncio
    @patch('pinecone.Index')
    async def test_pinecone_embedding(self, mock_index):
        """Test Pinecone embedding provider"""
        from ..providers.pinecone import PineconeEmbeddingProvider
        
        provider = PineconeEmbeddingProvider(
            api_key="test-key",
            environment="test-env",
            index_name="test-index"
        )
        
        # Mock upsert
        mock_index.return_value.upsert = AsyncMock()
        
        # Store embedding
        await provider.store_embedding(
            doc_id="doc-1",
            chunks=["Test content"],
            metadata={"title": "Test"}
        )
        
        mock_index.return_value.upsert.assert_called()


class TestProviderFactory:
    """Test provider factory pattern"""
    
    def test_create_storage_provider(self):
        """Test storage provider creation"""
        from ..providers.factory import create_storage_provider
        
        # Local provider
        config = {
            "storage_provider": "local",
            "local_storage_path": "/tmp/docflow"
        }
        provider = create_storage_provider(config)
        assert isinstance(provider, LocalStorageProvider)
        
        # OneDrive provider
        config = {
            "storage_provider": "onedrive",
            "onedrive": {
                "tenant_id": "test",
                "client_id": "test",
                "client_secret": "test"
            }
        }
        provider = create_storage_provider(config)
        assert isinstance(provider, OneDriveProvider)
    
    def test_create_llm_provider(self):
        """Test LLM provider creation"""
        from ..providers.factory import create_llm_provider
        
        # Anthropic provider
        config = {
            "llm_provider": "anthropic",
            "anthropic": {
                "api_key": "test-key"
            }
        }
        provider = create_llm_provider(config)
        assert isinstance(provider, AnthropicProvider)
    
    def test_invalid_provider(self):
        """Test invalid provider handling"""
        from ..providers.factory import create_storage_provider
        
        config = {
            "storage_provider": "invalid"
        }
        
        with pytest.raises(ValueError, match="Unknown storage provider"):
            create_storage_provider(config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])