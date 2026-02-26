# DocFlow Developer Guide

**Getting started with DocFlow development and testing.**

---

## Setup

### Quick Start with Bootstrap

The fastest way to set up a complete development environment:

```bash
cd Neutron_OS/docs/_tools/docflow
./bootstrap.sh
pip install -e ".[dev]"
```

This automatically installs dependencies, creates a local K3D cluster, and deploys all infrastructure (PostgreSQL, Redis, Ollama).

Use `./bootstrap.sh --dry-run` to preview what will be done.

### Manual Setup

#### 1. Clone and Install

```bash
cd Neutron_OS/docs/_tools/docflow
pip install -e ".[dev]"
```

#### 2. Configure

Copy the template configuration:

```bash
cp .doc-workflow.yaml.template .doc-workflow.yaml
```

For **local testing**, edit `.doc-workflow.yaml`:

```yaml
storage:
  provider: local
  local:
    root: ./generated

llm:
  provider: anthropic
  model: claude-3-5-haiku-20241022
  anthropic_api_key: ${ANTHROPIC_API_KEY}
```

### 3. Set Environment Variables

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Project Structure

```
docflow/
├── src/docflow/
│   ├── core/              # State, config, registry, persistence
│   ├── providers/         # Storage, notification, embedding, LLM
│   ├── convert/           # Comment extraction, markdown parsing
│   ├── review/            # Review period management
│   ├── git/               # Git integration
│   ├── embedding/         # RAG pipeline
│   ├── meetings/          # Meeting intelligence
│   ├── workflow/          # LangGraph (TODO)
│   └── cli/               # CLI interface
├── tests/                 # Test suite (TODO)
├── .doc-workflow.yaml     # Configuration
├── pyproject.toml         # Packaging
└── README.md
```

---

## Core Modules Overview

### `core/state.py`
Defines all state objects:
```python
from docflow.core import DocumentState, ReviewPeriod, AutonomyLevel

# Create a document
doc = DocumentState(
    doc_id="experiment-manager-prd",
    source_path="docs/prd/experiment-manager-prd.md"
)

# Start a review
review = ReviewPeriod(
    review_id="exp-1",
    doc_id=doc.doc_id,
    started_at=datetime.now(),
    ends_at=datetime.now() + timedelta(days=7),
    required_reviewers=["alice@example.com", "bob@example.com"]
)
```

### `core/config.py`
Load and work with configuration:
```python
from docflow.core import load_config

config = load_config()
print(config.storage.provider)  # "local"
print(config.llm.model)         # "claude-3-5-haiku-20241022"
```

### `core/registry.py`
Manage document links:
```python
from docflow.core import LinkRegistry

registry = LinkRegistry()
registry.register("experiment-manager-prd", "docs/prd/experiment-manager-prd.md",
                  published_url="https://onedrive.../exp-prd.docx")

url = registry.resolve_link("experiment-manager-prd")
```

### `providers/`
Work with storage and LLM:
```python
from docflow.providers import get_storage_provider, get_llm_provider

config = load_config()
storage = get_storage_provider(config)
llm = get_llm_provider(config)

# Upload a document
result = storage.upload(Path("test.docx"), "/Documents/Published/test.docx")
print(result.url)

# Generate text
response = llm.complete("What is the capital of France?")
```

### `review/manager.py`
Manage review workflows:
```python
from docflow.review import ReviewManager

manager = ReviewManager(storage, notifications)

# Start review
review = manager.start_review(
    doc_state,
    reviewers=["alice@example.com", "bob@example.com"],
    days=7
)

# Fetch comments
comments = manager.fetch_draft_comments(review, file_id="abc123")

# Check promotion eligibility
ready, reasons = manager.check_promotion_readiness(review)
if ready:
    manager.promote_draft_to_published(review, doc_state)
```

---

## Testing Workflow

### 1. Unit Tests (Coming)

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_state.py::test_document_state_creation

# With coverage
pytest --cov=src/docflow tests/
```

### 2. Manual Testing

```bash
# Initialize DocFlow
export ANTHROPIC_API_KEY="sk-ant-..."
docflow status

# List available commands
docflow --help
```

### 3. Integration Testing (Local)

Using LocalProvider, you can test the complete workflow without cloud dependencies:

```python
from pathlib import Path
from docflow.core import Config, DocumentState
from docflow.providers import LocalProvider, AnthropicProvider
from docflow.review import ReviewManager
from docflow.convert import DocxCommentExtractor

# Create a mock document
test_docx = Path("test_document.docx")  # Create this in advance

# Extract comments
extractor = DocxCommentExtractor(test_docx)
comments = extractor.extract()

print(f"Found {len(comments)} comments")
for comment in comments:
    print(f"  - {comment['author']}: {comment['text']}")
```

---

## Common Development Tasks

### Add a New Provider

1. Inherit from base class:

```python
from docflow.providers import StorageProvider, UploadResult

class S3Provider(StorageProvider):
    def upload(self, file_path, destination_path):
        # Implementation
        return UploadResult(success=True, file_id="s3://...", url="...")
    
    def download(self, file_id, dest_path):
        # Implementation
        return True
    
    # ... implement other required methods
```

2. Register it:

```python
from docflow.providers import register_storage_provider

register_storage_provider("s3", S3Provider)
```

3. Use it in config:

```yaml
storage:
  provider: s3
```

### Add a New CLI Command

1. Edit `cli/main.py`:

```python
@app.command()
def my_command(
    arg: str = typer.Argument(...),
    option: bool = typer.Option(False, "--option")
):
    """Command description."""
    console.print(f"[blue]Doing work...[/blue]")
    # Implementation
    console.print("[green]✓ Done[/green]")
```

2. Access via CLI:

```bash
docflow my-command myarg --option
```

### Debug State

```python
from docflow.core.persistence import StatePersistence

persistence = StatePersistence()

# Get mutation history
mutations = persistence.get_mutations(doc_id="my-doc")
for m in mutations:
    print(f"{m['timestamp']}: {m['mutation_type']} by {m['actor']}")

# Load document state
state = persistence.load_document_state("my-doc")
print(f"Published: {state.published_record}")
print(f"In review: {state.is_in_review()}")
```

---

## Important Code Patterns

### Error Handling

Use logging throughout:

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = storage.upload(file_path, destination)
except Exception as e:
    logger.error(f"Upload failed: {e}")
    return False
```

### Configuration Access

```python
from docflow.core import load_config

config = load_config()

# Check if feature is enabled
if config.embedding.enabled:
    embedding = get_embedding_provider(config)
```

### State Persistence

```python
from docflow.core.persistence import StatePersistence

persistence = StatePersistence()

# Save state
persistence.save_document_state(doc_state)
persistence.record_mutation(
    doc_id="my-doc",
    mutation_type="published",
    old_value="",
    new_value=json.dumps({"url": "..."}),
    actor="alice@example.com"
)

# Load state
doc_state = persistence.load_document_state("my-doc")
```

---

## Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

### Inspect Database

```bash
# Open SQLite database
sqlite3 .docflow/state.db

# List tables
.tables

# Query mutations
SELECT * FROM mutations ORDER BY timestamp DESC LIMIT 10;

# Check document state
SELECT doc_id, updated_at FROM document_state;
```

### Inspect Configurations

```python
from docflow.core import load_config
import json

config = load_config()
print(json.dumps({
    "storage": config.storage.provider,
    "llm": config.llm.model,
    "autonomy": config.autonomy.default_level,
}, indent=2))
```

---

## Performance Considerations

### Chunking Documents

The embedding pipeline chunks by sections (headers):
- Default chunk size: 512 chars
- Overlap: 50 chars

```python
from docflow.embedding import DocumentChunker

chunker = DocumentChunker(chunk_size=512, overlap=50)
chunks = chunker.chunk_by_sections(markdown_content)
print(f"Created {len(chunks)} chunks")
```

### Batch Operations

For multiple documents, use batch operations:

```python
# Good: Batch requests
documents = [doc1, doc2, doc3, ...]
embeddings_list = embedding.embed_texts([d.content for d in documents])

# Bad: Individual requests (slower)
for doc in documents:
    embedding.embed_texts([doc.content])
```

---

## Next Steps

1. **Write tests** — See TODO #17-18
2. **Implement LangGraph** — See TODO #13
3. **Add error handling** — Graceful degradation
4. **Profile performance** — Identify bottlenecks
5. **Documentation** — Usage examples and guides

---

## References

- [python-docx](https://python-docx.readthedocs.io/)
- [Anthropic API](https://docs.anthropic.com/)
- [MS Graph API](https://learn.microsoft.com/en-us/graph/api/overview)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Typer](https://typer.tiangolo.com/)

---

**Happy coding! Questions? Check the spec or open an issue.**
