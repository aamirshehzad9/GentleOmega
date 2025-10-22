import sys, os
sys.path.append(os.path.dirname(__file__))  # adds D:\GentleOmega\app to import path

# psycopg_fix.py
# Fixes libpq library not found error on Windows for Python 3.14+

import os

# Skip Windows PostgreSQL 18 binaries to avoid version conflict with WSL PostgreSQL 17
# Use pure Python implementation to avoid libpq version mismatch
os.environ["PSYCOPG_IMPL"] = "python"
print("INFO: Using pure Python psycopg to avoid PostgreSQL version conflict")

import psycopg
# Note: psycopg 3.x uses different adapter configuration syntax
# psycopg.adapters.set_default("client_encoding", "utf8")

def connect_pg(host, port, dbname, user, password):
    """Return a psycopg connection using pure Python mode."""
    conn = psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )
    conn.autocommit = True
    return conn
