"""
GentleΩ Safe Git Commit Script
Creates a snapshot branch before committing to avoid overwriting local progress
"""

import subprocess
import sys
from datetime import datetime

def run_git_command(cmd, description):
    """Run a git command safely"""
    try:
        print(f"🔧 {description}...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {description} successful")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False

def main():
    print("🧠 GentleΩ Safe Git Commit")
    print("=" * 50)
    
    # Check git status first
    print("📋 Checking current git status...")
    if not run_git_command("git status --porcelain", "Git status check"):
        print("❌ Git status check failed")
        return
    
    # Create timestamp for branch name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"gentlehq-real-mode-{timestamp}"
    
    print(f"🌿 Creating snapshot branch: {branch_name}")
    
    # Create and switch to new branch
    if not run_git_command(f"git checkout -b {branch_name}", f"Create branch {branch_name}"):
        print("❌ Failed to create branch")
        return
    
    # Add all changes
    if not run_git_command("git add .", "Stage all changes"):
        print("❌ Failed to stage changes")
        return
    
    # Commit with descriptive message
    commit_msg = "GentleΩ HQ: switched from demo to live DB mode + fixed Pylance pathing"
    if not run_git_command(f'git commit -m "{commit_msg}"', "Commit changes"):
        print("❌ Failed to commit changes")
        return
    
    # Show what was committed
    run_git_command("git show --stat HEAD", "Show commit summary")
    
    print("\n" + "=" * 50)
    print("✅ Safe commit completed!")
    print(f"📂 Branch: {branch_name}")
    print(f"💾 Commit: {commit_msg}")
    print("\n🚀 Next steps:")
    print(f"1. Push to remote: git push origin {branch_name}")
    print("2. Verify on GitHub")
    print("3. Merge to main when ready:")
    print("   git checkout main")
    print(f"   git merge {branch_name}")
    print("   git push origin main")
    print("=" * 50)

if __name__ == "__main__":
    main()