-- Extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Memories store
CREATE TABLE IF NOT EXISTS memories (
  id BIGSERIAL PRIMARY KEY,
  agent TEXT NOT NULL,
  user_id TEXT NOT NULL,
  source TEXT NOT NULL,
  content TEXT NOT NULL,
  meta JSONB DEFAULT '{}'::jsonb,
  embedding VECTOR(384),          -- 384 dims for all-MiniLM-L6-v2 (adjust if you change model)
  importance REAL DEFAULT 0,
  recency TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mem_emb ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_mem_agent ON memories (agent);
CREATE INDEX IF NOT EXISTS idx_mem_user ON memories (user_id);

-- Items table for blockchain integration
CREATE TABLE IF NOT EXISTS items (
  id BIGSERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  user_id TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);

-- Episodic rolling buffer
CREATE TABLE IF NOT EXISTS episodes (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn INT NOT NULL,
  role TEXT NOT NULL,
  text TEXT NOT NULL,
  meta JSONB DEFAULT '{}'::jsonb,
  embedding VECTOR(384),          -- match embedding dimension
  created_at TIMESTAMP DEFAULT now()
);