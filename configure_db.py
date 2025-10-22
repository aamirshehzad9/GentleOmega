"""
GentleΩ Database Configuration Helper
Helps set up PostgreSQL connection for production mode
"""

import os

def main():
    print("🧠 GentleΩ Database Configuration Helper")
    print("=" * 50)
    
    print("Current database environment:")
    print(f"PG_HOST: {os.getenv('PG_HOST', 'Not set')}")
    print(f"PG_PORT: {os.getenv('PG_PORT', 'Not set')}")
    print(f"PG_DB: {os.getenv('PG_DB', 'Not set')}")
    print(f"PG_USER: {os.getenv('PG_USER', 'Not set')}")
    print(f"PG_PASSWORD: {'*****' if os.getenv('PG_PASSWORD') else 'Not set'}")
    print(f"DATABASE_URL: {'Set' if os.getenv('DATABASE_URL') else 'Not set'}")
    
    print("\n" + "=" * 50)
    print("To configure PostgreSQL for production mode:")
    print("Copy and run these commands in PowerShell:")
    print("")
    print("$env:PG_HOST=\"127.0.0.1\"")
    print("$env:PG_PORT=\"5432\"")
    print("$env:PG_DB=\"metacity\"")
    print("$env:PG_USER=\"postgres\"")
    print("$env:PG_PASSWORD=\"YOUR_POSTGRES_PASSWORD\"")
    print("$env:DATABASE_URL=\"postgresql://postgres:YOUR_POSTGRES_PASSWORD@127.0.0.1:5432/metacity\"")
    print("")
    print("Replace YOUR_POSTGRES_PASSWORD with your actual PostgreSQL password")
    print("")
    print("Then run: python start_headquarters.py")

if __name__ == "__main__":
    main()