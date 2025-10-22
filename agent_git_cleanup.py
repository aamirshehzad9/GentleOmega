import subprocess
import os

def run_cmd(cmd):
    """Run bash command safely"""
    print(f"\n🧩 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error:\n{result.stderr}")
    else:
        print(f"✅ Success:\n{result.stdout}")

# === STEP 1: Remove .env & update .gitignore ===
if os.path.exists("env/.env"):
    run_cmd("git rm --cached env/.env")
    with open(".gitignore", "a") as f:
        f.write("\n# Ignore environment files\nenv/.env\n")
    run_cmd("git add .gitignore")
    run_cmd('git commit -m "Removed .env and added to .gitignore"')

# === STEP 2: Install filter-repo if missing ===
run_cmd("pip install git-filter-repo")

# === STEP 3: Clean history ===
run_cmd("git filter-repo --path env/.env --invert-paths --force")

# === STEP 4: Force push to GitHub ===
run_cmd("git push origin main --force")

print("\n🎯 Cleanup complete. Repo pushed safely without secrets.")
