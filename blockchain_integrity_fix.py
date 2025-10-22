"""
GentleΩ Blockchain Integrity Fix
Repairs hash verification and ensures chain integrity
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
from blockchain_client import blockchain_client
import json

def analyze_blockchain_integrity():
    """Analyze current blockchain integrity issues"""
    print("🔍 Analyzing blockchain integrity...")
    
    integrity_result = blockchain_client.verify_chain_integrity()
    
    print(f"Status: {integrity_result['status']}")
    print(f"Entries: {integrity_result.get('entries', 0)}")
    print(f"Verified: {integrity_result.get('verified', 0)}")
    print(f"Integrity: {integrity_result.get('integrity', 'unknown')}")
    
    if integrity_result.get('broken_links'):
        print("\n❌ Broken Links Found:")
        for link in integrity_result['broken_links']:
            print(f"  - {link}")
    else:
        print("\n✅ No broken links found")
    
    return integrity_result

def fix_hash_verification():
    """Fix the hash verification logic in blockchain_client.py"""
    
    # The issue is in the verify_chain_integrity method
    # It's popping _hash_timestamp from parsed_data, but the hash was computed with the timestamp included
    
    fix_code = '''    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verify the integrity of the blockchain ledger"""
        try:
            pg = self._get_db_connection()
            with pg.cursor() as cur:
                cur.execute("""
                    SELECT id, hash, previous_hash, block_data, created_at 
                    FROM blockchain_ledger 
                    ORDER BY created_at, id
                """)
                entries = cur.fetchall()
                
            if not entries:
                return {"status": "success", "message": "Empty chain is valid", "entries": 0}
            
            # Verify chain links
            verified_count = 0
            broken_links = []
            
            for i, (ledger_id, current_hash, previous_hash, block_data, created_at) in enumerate(entries):
                # First entry should have no previous hash
                if i == 0:
                    if previous_hash is not None:
                        broken_links.append(f"Genesis block {ledger_id} has unexpected previous_hash")
                else:
                    # Subsequent entries should link to previous
                    expected_previous = entries[i-1][1]  # hash of previous entry
                    if previous_hash != expected_previous:
                        broken_links.append(f"Block {ledger_id} previous_hash mismatch: expected {expected_previous}, got {previous_hash}")
                
                # Verify hash computation
                try:
                    # Parse block data
                    if isinstance(block_data, str):
                        parsed_data = json.loads(block_data)
                    else:
                        parsed_data = block_data
                    
                    # Extract timestamp but DON'T modify the original data
                    hash_timestamp = parsed_data.get("_hash_timestamp")
                    
                    # Create data copy without timestamp for hash computation
                    data_for_hash = {k: v for k, v in parsed_data.items() if k != "_hash_timestamp"}
                    
                    # Compute hash using the stored timestamp
                    computed_hash = self._compute_chain_hash(data_for_hash, previous_hash, hash_timestamp)
                    if current_hash != computed_hash:
                        broken_links.append(f"Block {ledger_id} hash verification failed: expected {computed_hash}, got {current_hash}")
                    else:
                        verified_count += 1
                except Exception as e:
                    broken_links.append(f"Block {ledger_id} hash computation error: {e}")
            
            return {
                "status": "success" if not broken_links else "error",
                "entries": len(entries),
                "verified": verified_count,
                "broken_links": broken_links,
                "integrity": "valid" if not broken_links else "compromised"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }'''
    
    print("🔧 Generated fix for hash verification logic")
    print("The issue was that verification was modifying the data before hash computation")
    print("Fixed by creating a copy without _hash_timestamp for verification")
    
    return fix_code

def main():
    """Main blockchain integrity analysis and fix"""
    print("🚀 GentleΩ Blockchain Integrity Analysis & Fix")
    print("=" * 50)
    
    # Step 1: Analyze current state
    integrity_result = analyze_blockchain_integrity()
    
    # Step 2: Generate fix
    if integrity_result.get('broken_links'):
        print("\n🔧 Generating integrity fix...")
        fix_code = fix_hash_verification()
        print("\nFix ready for application to blockchain_client.py")
    else:
        print("\n✅ Blockchain integrity is already valid!")
    
    print("\nIntegrity analysis complete.")

if __name__ == "__main__":
    main()