-- GentleΩ Phase 4: Blockchain Integration Migration (Updated)
-- This migration adds new columns to existing blockchain_ledger table
-- And creates the pods_poe table for EVM chain integration

-- Check if the new columns exist, add them if they don't
DO $$
BEGIN
    -- Add poe_hash column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='blockchain_ledger' AND column_name='poe_hash') THEN
        ALTER TABLE blockchain_ledger ADD COLUMN poe_hash TEXT;
    END IF;
    
    -- Add tx_hash column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='blockchain_ledger' AND column_name='tx_hash') THEN
        ALTER TABLE blockchain_ledger ADD COLUMN tx_hash TEXT UNIQUE;
    END IF;
    
    -- Add block_number column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='blockchain_ledger' AND column_name='block_number') THEN
        ALTER TABLE blockchain_ledger ADD COLUMN block_number BIGINT;
    END IF;
    
    -- Add status column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='blockchain_ledger' AND column_name='status') THEN
        ALTER TABLE blockchain_ledger ADD COLUMN status TEXT NOT NULL DEFAULT 'queued';
    END IF;
    
    -- Add updated_at column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='blockchain_ledger' AND column_name='updated_at') THEN
        ALTER TABLE blockchain_ledger ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
    END IF;
END$$;

-- PoD/PoE cache table for off-chain verification
CREATE TABLE IF NOT EXISTS pods_poe (
  poe_hash TEXT PRIMARY KEY,
  pod_hash TEXT NOT NULL,
  content_type TEXT NOT NULL DEFAULT 'execution',
  execution_data JSONB,
  on_chain BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Track updates function (if not exists)
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN 
  NEW.updated_at = now(); 
  RETURN NEW; 
END;
$$ LANGUAGE plpgsql;

-- Update triggers
DROP TRIGGER IF EXISTS trg_touch_blockchain_ledger ON blockchain_ledger;
CREATE TRIGGER trg_touch_blockchain_ledger
  BEFORE UPDATE ON blockchain_ledger
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_touch_pods_poe ON pods_poe;
CREATE TRIGGER trg_touch_pods_poe
  BEFORE UPDATE ON pods_poe
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Helpful indexes for new columns
CREATE INDEX IF NOT EXISTS idx_blockchain_ledger_status ON blockchain_ledger(status);
CREATE INDEX IF NOT EXISTS idx_blockchain_ledger_poe_hash ON blockchain_ledger(poe_hash);
CREATE INDEX IF NOT EXISTS idx_blockchain_ledger_tx_hash ON blockchain_ledger(tx_hash);
CREATE INDEX IF NOT EXISTS idx_pods_poe_on_chain ON pods_poe(on_chain);
CREATE INDEX IF NOT EXISTS idx_pods_poe_created_at ON pods_poe(created_at);

-- Mark migration as completed
INSERT INTO blockchain_ledger (hash, content_type, block_data, poe_hash, status) 
VALUES ('migration_2025_10_22_phase4', 'migration', '{"migration": "phase4_completed"}', 'migration_2025_10_22_phase4', 'confirmed') 
ON CONFLICT (hash) DO NOTHING;

COMMENT ON TABLE blockchain_ledger IS 'Enhanced for EVM blockchain transaction tracking';
COMMENT ON TABLE pods_poe IS 'Off-chain PoD/PoE verification cache before blockchain commit';

-- Display current schema
\echo 'Phase 4 Migration Applied Successfully!'
\d blockchain_ledger
\d pods_poe