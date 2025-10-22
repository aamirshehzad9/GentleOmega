-- migration_2025_10_22_blockchain_ledger.sql
-- Idempotent migration for Phase 4 blockchain ledger enhancements

-- Modify existing blockchain_ledger table to add EVM tracking columns
ALTER TABLE IF EXISTS blockchain_ledger
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'queued',
  ADD COLUMN IF NOT EXISTS tx_hash TEXT,
  ADD COLUMN IF NOT EXISTS block_number BIGINT,
  ADD COLUMN IF NOT EXISTS poe_hash TEXT,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Create the pods_poe table for off-chain PoE tracking
CREATE TABLE IF NOT EXISTS pods_poe (
  poe_hash TEXT PRIMARY KEY,
  pod_hash TEXT NOT NULL,
  content_type TEXT NOT NULL DEFAULT 'execution',
  execution_data JSONB,
  on_chain BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Update trigger function
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN 
  NEW.updated_at = now(); 
  RETURN NEW; 
END; 
$$ LANGUAGE plpgsql;

-- Drop and recreate triggers to ensure they exist
DROP TRIGGER IF EXISTS trg_touch_blockchain_ledger ON blockchain_ledger;
CREATE TRIGGER trg_touch_blockchain_ledger
  BEFORE UPDATE ON blockchain_ledger
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_touch_pods_poe ON pods_poe;
CREATE TRIGGER trg_touch_pods_poe
  BEFORE UPDATE ON pods_poe
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_blockchain_ledger_status    ON blockchain_ledger(status);
CREATE INDEX IF NOT EXISTS idx_blockchain_ledger_poe_hash  ON blockchain_ledger(poe_hash);
CREATE INDEX IF NOT EXISTS idx_blockchain_ledger_tx_hash   ON blockchain_ledger(tx_hash);
CREATE INDEX IF NOT EXISTS idx_pods_poe_on_chain          ON pods_poe(on_chain);
CREATE INDEX IF NOT EXISTS idx_pods_poe_created_at        ON pods_poe(created_at);

-- Add unique constraint on tx_hash if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'blockchain_ledger_tx_hash_key'
    ) THEN
        ALTER TABLE blockchain_ledger ADD CONSTRAINT blockchain_ledger_tx_hash_key UNIQUE (tx_hash);
    END IF;
END $$;

-- Migration marker (provide required hash value)
INSERT INTO blockchain_ledger (hash, poe_hash, status, block_data, content_type, created_at, updated_at) 
VALUES ('migration_phase_4_complete', 'migration_phase_4_complete', 'confirmed', '{"migration": true}'::jsonb, 'migration', now(), now()) 
ON CONFLICT (hash) DO NOTHING;