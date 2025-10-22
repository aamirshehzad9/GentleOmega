# GentleΩ (GentleOmega) AI Agent Instructions

## Architecture Overview

**GentleΩ** is a memory-augmented AI orchestrator that combines RAG (Retrieval-Augmented Generation) with blockchain-based proof systems. The system has three main architectural layers:

1. **Memory Layer**: PostgreSQL with pgvector for semantic memory storage and retrieval
2. **Orchestration Layer**: FastAPI service handling AI operations and blockchain integration  
3. **Proof Layer**: PoD (Proof of Data) → PoE (Proof of Execution) blockchain transactions

## Key Components

### Memory System (`app/app.py`)
- **Embeddings**: Configurable local (sentence-transformers) or remote (OpenAI-compatible) 
- **Vector storage**: pgvector with cosine similarity search combining recency, importance, and semantic relevance
- **Retrieval scoring**: `0.60 * similarity + 0.15 * importance + 0.25 * recency_decay`
- **Mock mode**: When `HF_TOKEN` not configured, uses mock embeddings `[0.1] * 384`

### Database Schema (`db/001_schema.sql`)
- `memories` table: Core RAG storage with 384-dim vectors (adjust for your embedding model)
- `items` table: Simple content storage with blockchain integration hooks
- `episodes` table: Session-based conversational memory buffer

### Blockchain Integration (`app/blockchain_client.py`)
**Critical Pattern**: All data operations follow PoD → PoE flow:
1. **PoD (Proof of Data)**: Record input data hash before processing
2. **Processing**: Execute the actual operation (embedding, retrieval, etc.)
3. **PoE (Proof of Execution)**: Record execution results linked to original PoD hash

**Simulation Mode**: When `CHAIN_RPC=https://your-chain-endpoint`, blockchain calls are simulated with console output.

### Database Compatibility (`app/psycopg_fix.py`)
**Windows PostgreSQL Issue**: Uses `PSYCOPG_IMPL=python` to avoid libpq version conflicts between local PostgreSQL 18 and WSL PostgreSQL 17. Always import this module first in database-dependent files.

## Development Workflows

### Environment Setup
1. Copy `env/example.env` to `env/.env` and configure:
   - `HF_TOKEN`: Hugging Face API token for remote generation/embeddings
   - `PG_*`: PostgreSQL connection parameters
   - `EMBEDDINGS_BACKEND`: "local" or "remote"
2. Database initialization: Run `db/001_schema.sql` on PostgreSQL with pgvector extension

### Running Services
- **Main app**: `uvicorn app:app --host 127.0.0.1 --port 8000 --reload`
- **Test versions**: `minimal_app.py`, `simple_app.py`, `test_app.py` for isolated testing
- **Event listener**: `python app/events/listener.py` for blockchain event monitoring

### Testing Patterns
```powershell
# Health check
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"

# Create item (triggers PoD/PoE flow)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/items" -Method POST -Body (@{content="test"; user_id="dev"} | ConvertTo-Json) -ContentType "application/json"

# PostgreSQL direct connection test
$env:PGPASSWORD='postgres'; & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -U postgres -d metacity -c "\dx"
```

## Project-Specific Conventions

### Import Pattern
All app modules start with:
```python
import sys, os
sys.path.append(os.path.dirname(__file__))
from psycopg_fix import connect_pg
```

### Error Handling Strategy
- Database operations return `{"status": "error", "error": str(e)}` format
- Mock mode for external dependencies when tokens/URLs not configured
- Graceful degradation: app continues with limited functionality if components fail

### Blockchain Integration Points
- `/embed` endpoint: Full PoD→PoE cycle for embedding generation
- `/items/{id}` GET: PoD for retrieval operations with PoE recording
- Event listener: Automatic PoD/PoE for database inserts via triggers or polling

### Memory Operations
- `upsert_memory()`: Stores content with metadata, importance scoring
- `retrieve()`: Multi-factor scoring for context selection
- `live_session()`: Goal-directed autonomous reasoning loops with session tracking

## Integration Dependencies

- **PostgreSQL + pgvector**: Core vector similarity search
- **Hugging Face/OpenAI**: Remote generation and embeddings  
- **sentence-transformers**: Local embedding fallback
- **Blockchain RPC**: External proof recording (simulated by default)

## Debugging Notes

- Check database connection first: PostgreSQL version compatibility is common issue
- Mock modes available for all external APIs - useful for offline development
- Event listener has both trigger-based and polling fallback modes
- FastAPI automatic docs at `/docs` when service running