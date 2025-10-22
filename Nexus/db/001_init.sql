CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS agents (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  owner_wallet TEXT NOT NULL,
  meta_uri TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS blockchain_ledger (
  id BIGSERIAL PRIMARY KEY,
  poe_hash TEXT NOT NULL,
  tx_hash TEXT,
  block_number BIGINT,
  status TEXT NOT NULL DEFAULT 'queued',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);