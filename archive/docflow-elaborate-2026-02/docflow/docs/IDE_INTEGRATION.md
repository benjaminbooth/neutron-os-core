# DocFlow IDE Integration Guide

> Bringing DocFlow directly into VS Code and PyCharm for seamless documentation workflows.

## Overview

DocFlow IDE plugins provide:
- **Inline document search** - Find related docs without leaving your editor
- **Smart completions** - Auto-complete document references and links
- **Workflow chain visualization** - See requirement→spec chains in the sidebar
- **Agent chat** - Ask questions about documents in a side panel
- **Code↔Doc linking** - Connect code to its implementation specs

```
┌────────────────────────────────────────────────────────────────────────┐
│  IDE Integration Architecture                                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   ┌─────────────────────────────────────────────────────────────────┐ │
│   │                         IDE Plugins                              │ │
│   │  ┌──────────────────┐      ┌──────────────────────────────────┐│ │
│   │  │  VS Code         │      │  PyCharm / IntelliJ             ││ │
│   │  │  Extension       │      │  Plugin                          ││ │
│   │  │  (TypeScript)    │      │  (Kotlin)                        ││ │
│   │  └────────┬─────────┘      └─────────────┬────────────────────┘│ │
│   └───────────┼──────────────────────────────┼─────────────────────┘ │
│               │                              │                        │
│               │      WebSocket / JSON-RPC    │                        │
│               └──────────────┬───────────────┘                        │
│                              │                                        │
│   ┌──────────────────────────▼───────────────────────────────────────┐│
│   │                    DocFlow Agent Server                          ││
│   │                    (docflow serve --port 8765)                   ││
│   │                                                                  ││
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  ││
│   │  │ Agent Core  │  │  RAG        │  │  Document Operations    │  ││
│   │  │ (LLM)       │  │  (pgvector) │  │  (CRUD, Workflow)       │  ││
│   │  └─────────────┘  └─────────────┘  └─────────────────────────┘  ││
│   └──────────────────────────────────────────────────────────────────┘│
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## VS Code Extension

### Installation

```bash
# From marketplace (when published)
code --install-extension neutron-os.docflow

# From VSIX (development)
code --install-extension docflow-vscode-0.1.0.vsix

# From source
cd extensions/vscode
npm install
npm run build
npm run package
```

### Features

#### 1. Document Explorer Sidebar

A dedicated view showing your document hierarchy:

```
DOCFLOW
├── 📋 Requirements
│   ├── REQ-042 Data Capture ✓
│   ├── REQ-051 Safety Interlocks ◐
│   └── REQ-055 Calibration ○
├── 📄 PRDs
│   ├── PRD-017 Sensor Pipeline ✓
│   └── PRD-023 Safety System ◐
├── 📐 Designs
│   ├── DES-003 Pipeline Arch ✓
│   └── DES-019 Safety Controller ○
├── 📦 Specs
│   ├── SPC-089 Ingestion Service ✓
│   └── SPC-092 Processing Workers ◐
└── 📝 Recent
    └── DES-019 (edited 2 min ago)
```

#### 2. Workflow Chain View

Visualize document relationships:

```
REQ-042 ─────► PRD-017 ─────► DES-003 ─────► SPC-089 ✓
                 │                │
                 │                └─────────► SPC-092 ◐
                 │
                 └────► DES-007 ─────────────► SPC-103 ○
```

#### 3. Document References

Hover over document IDs to see details:

```markdown
This implements [SPC-089](docflow://spec/SPC-089).
                  └─── Hover shows: 
                       ┌────────────────────────────────┐
                       │ SPC-089: Sensor Ingestion      │
                       │ Status: Published ✓            │
                       │ Owner: @alice                  │
                       │ Last updated: 2 days ago       │
                       │                                │
                       │ [Open] [Show Chain] [History]  │
                       └────────────────────────────────┘
```

#### 4. Quick Actions (Cmd+Shift+D)

```
┌─────────────────────────────────────────────┐
│ DocFlow Quick Actions                       │
├─────────────────────────────────────────────┤
│ 🔍 Search documents...                      │
│ 📄 Create new document                      │
│ 🔗 Link current file to spec                │
│ 💬 Ask DocFlow Agent                        │
│ 📊 Show workflow dashboard                  │
│ ⏰ My pending reviews                       │
└─────────────────────────────────────────────┘
```

#### 5. Agent Chat Panel

Integrated chat with DocFlow agent:

```
┌─────────────────────────────────────────────────────────────────┐
│ DocFlow Agent                                            [−][×] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ You: What requirements does this code implement?                │
│                                                                 │
│ Agent: Based on the file sensor_ingestion/service.py,          │
│ this code implements:                                           │
│                                                                 │
│ • SPC-089: Sensor Ingestion Service                            │
│   └── DES-003: Sensor Pipeline Architecture                    │
│       └── PRD-017: Sensor Data Pipeline                        │
│           └── REQ-042: Loop Instrumentation Data Capture       │
│                                                                 │
│ The SensorIngestionService class directly implements:           │
│ - FR1 (Data Ingestion) from PRD-017                            │
│ - Section 4.1 (TCP Handler) from DES-003                       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ Type a message...                                    [Send]     │
└─────────────────────────────────────────────────────────────────┘
```

#### 6. Code Lens Annotations

Annotations appear above code linked to specs:

```python
# ▶ SPC-089 | REQ-042 | Last verified: 2 days ago
class SensorIngestionService:
    """Main service for ingesting sensor data."""
    
    # ▶ SPC-089 §4.2: TCP Handler
    async def handle_tcp_connection(self, reader, writer):
        ...
```

#### 7. Document Completion

Auto-complete document references:

```markdown
See [REQ-
      └─── Suggestions:
           REQ-042 Data Capture
           REQ-051 Safety Interlocks
           REQ-055 Calibration
```

### Configuration

```json
// .vscode/settings.json
{
  "docflow.serverUrl": "ws://localhost:8765",
  "docflow.autoConnect": true,
  "docflow.showCodeLens": true,
  "docflow.showHoverInfo": true,
  "docflow.workflowView.showStatus": true,
  "docflow.workflowView.groupBy": "type", // type, project, status
  "docflow.agent.model": "local", // local, anthropic
  "docflow.agent.maxContext": 10 // documents to include
}
```

### Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| `DocFlow: Search` | `Cmd+Shift+F D` | Search documents |
| `DocFlow: Quick Actions` | `Cmd+Shift+D` | Show quick actions |
| `DocFlow: Chat` | `Cmd+Shift+A` | Open agent chat |
| `DocFlow: Create Document` | `Cmd+Shift+N D` | Create new document |
| `DocFlow: Show Chain` | `Cmd+Shift+C` | Show workflow chain |
| `DocFlow: Link to Spec` | `Cmd+Shift+L` | Link file to spec |
| `DocFlow: Refresh` | `Cmd+Shift+R D` | Refresh document tree |

### Extension API

For other extensions to integrate with DocFlow:

```typescript
import * as vscode from 'vscode';

// Get DocFlow extension API
const docflow = vscode.extensions.getExtension('neutron-os.docflow');
const api = await docflow.activate();

// Search documents
const results = await api.search('sensor data pipeline');

// Get document details
const doc = await api.getDocument('SPC-089');

// Get workflow chain
const chain = await api.getWorkflowChain('SPC-089', 'upstream');

// Create document
const newDoc = await api.createDocument({
  type: 'spec',
  title: 'New Service Spec',
  parent: 'DES-003'
});

// Ask agent
const response = await api.askAgent('What does REQ-042 require?');
```

---

## PyCharm / IntelliJ Plugin

### Installation

```bash
# From JetBrains Marketplace (when published)
# Settings → Plugins → Marketplace → Search "DocFlow"

# From disk (development)
# Settings → Plugins → Install Plugin from Disk → docflow-intellij.zip
```

### Features

#### 1. Tool Window

```
┌─────────────────────────────────────────────────────────────────┐
│ DocFlow                                                 [⚙][−] │
├─────────────────────────────────────────────────────────────────┤
│ ▼ Requirements                                                  │
│   ├─ REQ-042 Data Capture ✓                                    │
│   ├─ REQ-051 Safety Interlocks ◐                               │
│   └─ REQ-055 Calibration ○                                     │
│ ▼ PRDs                                                          │
│   ├─ PRD-017 Sensor Pipeline ✓                                 │
│   └─ PRD-023 Safety System ◐                                   │
│ ▼ Designs                                                       │
│   └─ ...                                                        │
│ ▼ Specs                                                         │
│   └─ ...                                                        │
├─────────────────────────────────────────────────────────────────┤
│ [🔍 Search] [📄 New] [🔄 Refresh]                              │
└─────────────────────────────────────────────────────────────────┘
```

#### 2. Quick Documentation (Ctrl+Q / F1)

Hover over document references:

```python
# See SPC-089 for implementation details
#         └─── Press Ctrl+Q
#              ┌────────────────────────────────┐
#              │ SPC-089: Sensor Ingestion      │
#              │ ─────────────────────────────  │
#              │ Implementation spec for the    │
#              │ sensor data ingestion service. │
#              │                                │
#              │ Status: Published              │
#              │ Owner: @alice                  │
#              │ Parent: DES-003                │
#              │                                │
#              │ Sections:                      │
#              │ • 4.1 Service Architecture     │
#              │ • 4.2 TCP Handler              │
#              │ • 4.3 Data Validation          │
#              └────────────────────────────────┘
```

#### 3. Gutter Icons

```python
class SensorIngestionService:  # 📋 ← Click for linked specs
    """Main service."""
    
    async def handle_tcp(self):  # 📎 ← Click for related docs
        ...
```

#### 4. Intention Actions (Alt+Enter)

```python
class NewService:  # ← Alt+Enter
                   # ┌────────────────────────────────┐
                   # │ 📎 Link to DocFlow spec        │
                   # │ 📄 Create new spec for class   │
                   # │ 🔍 Find related documents      │
                   # └────────────────────────────────┘
```

#### 5. Find Action (Cmd+Shift+A)

```
┌─────────────────────────────────────────────────────────┐
│ docflow                                                 │
├─────────────────────────────────────────────────────────┤
│ 🔍 DocFlow: Search Documents                            │
│ 📄 DocFlow: Create Document                             │
│ 💬 DocFlow: Open Agent Chat                             │
│ 🔗 DocFlow: Link File to Spec                           │
│ 📊 DocFlow: Show Workflow Chain                         │
│ ⚙ DocFlow: Settings                                     │
└─────────────────────────────────────────────────────────┘
```

#### 6. Agent Tool Window

```
┌─────────────────────────────────────────────────────────────────┐
│ DocFlow Agent                                           [⚙][−] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 👤 What tests should I write for this class?                   │
│                                                                 │
│ 🤖 Based on SPC-089 Section 5 (Testing Requirements):          │
│                                                                 │
│    Unit Tests:                                                  │
│    • test_validate_reading_valid_data                          │
│    • test_validate_reading_invalid_sensor_id                   │
│    • test_batch_assembly_normal                                │
│    • test_batch_assembly_overflow                              │
│                                                                 │
│    Integration Tests:                                           │
│    • test_tcp_handler_connection                               │
│    • test_tcp_handler_disconnect                               │
│    • test_queue_publishing                                     │
│                                                                 │
│ Would you like me to generate test stubs?                      │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ Ask something...                                     [Send ➤]  │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration

```xml
<!-- .idea/docflow.xml -->
<component name="DocFlowSettings">
  <option name="serverUrl" value="ws://localhost:8765" />
  <option name="autoConnect" value="true" />
  <option name="showGutterIcons" value="true" />
  <option name="showQuickDoc" value="true" />
  <option name="agentModel" value="local" />
</component>
```

### Keymap

| Action | Default Shortcut | Description |
|--------|------------------|-------------|
| Search Documents | `Ctrl+Alt+D` | Open document search |
| Quick Actions | `Ctrl+Shift+D` | Show DocFlow popup |
| Agent Chat | `Ctrl+Alt+A` | Open agent panel |
| Show Chain | `Ctrl+Alt+C` | Show workflow chain |
| Link to Spec | `Ctrl+Alt+L` | Link current file |

---

## Server Protocol

Both plugins communicate with the DocFlow agent server using JSON-RPC 2.0 over WebSocket.

### Starting the Server

```bash
# Start server
docflow serve --port 8765

# With custom config
docflow serve --port 8765 --model "kimi-k2.5" --db "postgresql://..."
```

### Protocol Messages

#### Initialize

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "config": {
      "model": "local"
    }
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "initialized",
    "capabilities": ["search", "chat", "create", "workflow"]
  }
}
```

#### Search

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "search",
  "params": {
    "query": "sensor data pipeline",
    "filters": {
      "type": "spec",
      "status": "published",
      "limit": 10
    }
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "count": 3,
    "results": [
      {
        "doc_id": "SPC-089",
        "title": "Sensor Ingestion Service",
        "preview": "Implementation specification for...",
        "score": 0.92
      },
      ...
    ]
  }
}
```

#### Chat

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "chat",
  "params": {
    "message": "What requirements does SPC-089 implement?",
    "conversation_id": "conv-123"
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "message": "SPC-089 implements requirements from...",
    "citations": [
      {"doc_id": "REQ-042", "title": "Data Capture"},
      {"doc_id": "PRD-017", "title": "Sensor Pipeline"}
    ],
    "suggestions": [
      "Show me the full workflow chain",
      "What tests are specified?"
    ],
    "tools_used": ["get_workflow_chain", "get_document"]
  }
}
```

#### Get Document

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "get_document",
  "params": {
    "doc_id": "SPC-089"
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "doc_id": "SPC-089",
    "title": "Sensor Ingestion Service",
    "type": "spec",
    "status": "published",
    "owner": "alice",
    "content": "# SPC-089: Sensor Ingestion Service\n\n...",
    "metadata": {
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-20T14:22:00Z",
      "parent": "DES-003"
    }
  }
}
```

#### Get Workflow Chain

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "get_workflow_chain",
  "params": {
    "doc_id": "SPC-089",
    "direction": "upstream"
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "root": "SPC-089",
    "direction": "upstream",
    "chain": [
      {
        "doc_id": "SPC-089",
        "type": "spec",
        "depth": 0,
        "children": []
      },
      {
        "doc_id": "DES-003",
        "type": "design",
        "depth": 1,
        "children": ["SPC-089"]
      },
      {
        "doc_id": "PRD-017",
        "type": "prd",
        "depth": 2,
        "children": ["DES-003"]
      },
      {
        "doc_id": "REQ-042",
        "type": "requirement",
        "depth": 3,
        "children": ["PRD-017"]
      }
    ]
  }
}
```

#### Create Document

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "create_document",
  "params": {
    "type": "spec",
    "title": "New Processing Service",
    "project": "bubble_flow_loop",
    "parent": "DES-003",
    "template": "spec"
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 6,
  "result": {
    "doc_id": "SPC-093",
    "title": "New Processing Service",
    "path": "/docs/specs/SPC-093.md",
    "status": "created"
  }
}
```

---

## Development Setup

### VS Code Extension

```bash
# Prerequisites
node >= 18
npm >= 9

# Setup
cd extensions/vscode
npm install

# Development
npm run watch  # Compile in watch mode
# Press F5 in VS Code to launch extension host

# Build
npm run build
npm run package  # Creates .vsix

# Test
npm test
```

**Project Structure:**

```
extensions/vscode/
├── package.json           # Extension manifest
├── tsconfig.json
├── src/
│   ├── extension.ts       # Entry point
│   ├── client.ts          # WebSocket client
│   ├── views/
│   │   ├── documentTree.ts
│   │   ├── workflowChain.ts
│   │   └── agentChat.ts
│   ├── providers/
│   │   ├── hoverProvider.ts
│   │   ├── completionProvider.ts
│   │   ├── codeLensProvider.ts
│   │   └── definitionProvider.ts
│   ├── commands/
│   │   ├── search.ts
│   │   ├── create.ts
│   │   └── link.ts
│   └── utils/
│       └── protocol.ts
├── resources/
│   └── icons/
└── test/
    └── extension.test.ts
```

### PyCharm Plugin

```bash
# Prerequisites
JDK 17+
IntelliJ IDEA (for development)

# Setup
cd extensions/intellij
./gradlew build

# Development
# Open in IntelliJ IDEA
# Run → Run Plugin

# Build
./gradlew buildPlugin  # Creates build/distributions/*.zip

# Test
./gradlew test
```

**Project Structure:**

```
extensions/intellij/
├── build.gradle.kts
├── settings.gradle.kts
├── src/main/
│   ├── kotlin/
│   │   └── com/neutronos/docflow/
│   │       ├── DocFlowPlugin.kt
│   │       ├── client/
│   │       │   └── WebSocketClient.kt
│   │       ├── toolwindow/
│   │       │   ├── DocumentTreePanel.kt
│   │       │   └── AgentChatPanel.kt
│   │       ├── actions/
│   │       │   ├── SearchAction.kt
│   │       │   └── CreateAction.kt
│   │       ├── annotators/
│   │       │   └── DocRefAnnotator.kt
│   │       ├── completion/
│   │       │   └── DocRefCompletionContributor.kt
│   │       └── settings/
│   │           └── DocFlowSettingsConfigurable.kt
│   └── resources/
│       ├── META-INF/
│       │   └── plugin.xml
│       └── icons/
└── src/test/
    └── kotlin/
```

---

## Troubleshooting

### Server Connection Issues

```
❌ Cannot connect to DocFlow server

1. Check if server is running:
   $ docflow serve --port 8765
   
2. Check port availability:
   $ lsof -i :8765
   
3. Check firewall settings

4. Verify server URL in settings:
   VS Code: docflow.serverUrl
   PyCharm: Settings → DocFlow → Server URL
```

### Slow Search

```
❌ Search taking too long

1. Check database connection:
   $ docflow db status
   
2. Rebuild search index:
   $ docflow index rebuild
   
3. Check pgvector index:
   $ docflow db check-indexes
```

### Agent Not Responding

```
❌ Agent not providing responses

1. Check LLM service:
   $ docflow agent status
   
2. Check model availability:
   $ docflow agent models
   
3. Try fallback model:
   Settings → docflow.agent.model → "anthropic"
```

---

## Next Steps

- **[Collaborative Workflow Guide](./COLLABORATIVE_WORKFLOW.md)**: Learn team workflows
- **[API Reference](./API_REFERENCE.md)**: Full protocol documentation
- **[Contributing](./CONTRIBUTING.md)**: Help improve the plugins
