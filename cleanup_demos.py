"""
GentleΩ Demo Files Cleanup Script
Archives temporary demo files and cleans up for production
"""

import os
import shutil
from pathlib import Path

def create_archive_directory():
    """Create archive directory for demo files"""
    archive_dir = Path("archive") / "demo_files"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir

def main():
    print("🧠 GentleΩ Demo Files Cleanup")
    print("=" * 50)
    
    # Files to archive
    demo_files = [
        "simple_demo.py",
        "demo_phase5.py", 
        "demo_launch.py",
        "app/demo_simple.py",
        "app/demo_headquarters.py"
    ]
    
    archive_dir = create_archive_directory()
    print(f"📁 Archive directory: {archive_dir}")
    
    archived_count = 0
    
    for file_path in demo_files:
        path = Path(file_path)
        if path.exists():
            # Create archive path maintaining directory structure
            archive_path = archive_dir / path.name
            
            try:
                shutil.move(str(path), str(archive_path))
                print(f"✅ Archived: {file_path} → {archive_path}")
                archived_count += 1
            except Exception as e:
                print(f"❌ Failed to archive {file_path}: {e}")
        else:
            print(f"⚠️  Not found: {file_path}")
    
    print(f"\n📦 Archived {archived_count} demo files")
    
    # Show remaining launcher
    if Path("start_headquarters.py").exists():
        print("✅ Production launcher available: start_headquarters.py")
    
    print("\n🎯 Next steps:")
    print("1. Set database environment: python configure_db.py")
    print("2. Launch production mode: python start_headquarters.py") 
    print("3. Commit changes: git add . && git commit -m 'Cleaned up demo files'")

if __name__ == "__main__":
    main()