#!/usr/bin/env python3
"""
Pre-Flight Environment Health Check
Validates connectivity to PostgreSQL, Redis, and MinIO.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_status(component: str, ok: bool, details: str = ""):
    status = f"{GREEN}[OK]{RESET}" if ok else f"{RED}[FAILED]{RESET}"
    print(f"  {status} {BOLD}{component:<25}{RESET} {details}")

def check_postgres():
    db_url = os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        print_status("PostgreSQL", False, "DATABASE_URL not configured")
        return False
    # Convert asyncpg to psycopg2 if needed
    if "postgresql+asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    
    try:
        import psycopg2
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        conn = psycopg2.connect(
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432,
            connect_timeout=3
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        ver = cur.fetchone()[0].split()[1]
        
        # Check extensions
        cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('btree_gist', 'uuid-ossp');")
        exts = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        
        ext_str = f"(Extensions: {', '.join(exts) if exts else 'none'})"
        if "btree_gist" in exts:
            print_status("PostgreSQL 16", True, f"v{ver} connected. {ext_str}")
            return True
        else:
            print_status("PostgreSQL 16", False, f"Connected, but missing btree_gist extension! {ext_str}")
            return False
    except Exception as e:
        print_status("PostgreSQL 16", False, f"Connection failed: {e}")
        return False

def check_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis
        client = redis.from_url(redis_url, socket_timeout=3)
        res = client.ping()
        info = client.info("server")
        ver = info.get("redis_version", "unknown")
        print_status("Redis 7", True, f"v{ver} PING successful")
        return True
    except Exception as e:
        print_status("Redis 7", False, f"Connection failed: {e}")
        return False

def check_minio():
    endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
    try:
        import boto3
        from botocore.client import Config
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name=os.getenv("S3_REGION", "ap-south-1")
        )
        buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        print_status("MinIO / S3", True, f"Connected. Buckets: {', '.join(buckets) if buckets else 'none'}")
        return True
    except Exception as e:
        print_status("MinIO / S3", False, f"Connection failed: {e}")
        return False

def main():
    print(f"\n{BOLD}======================================================{RESET}")
    print(f"{BOLD} Healthcare Platform — Pre-Flight Environment Check{RESET}")
    print(f"{BOLD}======================================================{RESET}\n")
    
    pg_ok = check_postgres()
    rd_ok = check_redis()
    s3_ok = check_minio()
    
    print()
    if pg_ok and rd_ok and s3_ok:
        print(f"{GREEN}{BOLD}✓ All infrastructure services are online and ready!{RESET}\n")
        sys.exit(0)
    else:
        print(f"{YELLOW}{BOLD}! Some services are not reachable. Start them via:{RESET}")
        print(f"   docker compose up -d\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
