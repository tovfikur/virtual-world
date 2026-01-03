#!/usr/bin/env python3
"""Setup test users with proper password hashing"""

import sys
import psycopg2
from passlib.context import CryptContext

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)

try:
    conn = psycopg2.connect(
        dbname="virtualworld",
        user="virtualworld",
        password="CHANGEME_STRONG_PASSWORD_HERE",
        host="localhost",
        port="5432"
    )
    cur = conn.cursor()
    
    # Clear test users
    cur.execute("DELETE FROM users WHERE username IN ('testplayer', 'seller')")
    
    # Hash passwords
    testplayer_hash = hash_password("TestPassword123!")
    seller_hash = hash_password("SellerPassword123!")
    
    print(f"testplayer hash: {testplayer_hash}")
    print(f"seller hash: {seller_hash}")
    
    # Create testplayer with 500K BDT
    cur.execute("""
        INSERT INTO users (user_id, username, email, password_hash, role, balance_bdt, verified, is_banned, is_suspended, failed_login_attempts, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
    """, (
        '24d92451-0620-4d3c-82e9-2c77aca61e77',
        'testplayer',
        'testplayer@example.com',
        testplayer_hash,
        'USER',
        500000,
        True,
        False,
        False,
        0
    ))
    
    # Create seller account with 1M BDT
    cur.execute("""
        INSERT INTO users (user_id, username, email, password_hash, role, balance_bdt, verified, is_banned, is_suspended, failed_login_attempts, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
    """, (
        '00000000-0000-0000-0000-000000000001',
        'seller',
        'seller@example.com',
        seller_hash,
        'USER',
        1000000,
        True,
        False,
        False,
        0
    ))
    
    conn.commit()
    
    # Verify
    cur.execute("SELECT user_id, username, email, balance_bdt FROM users ORDER BY username")
    print("\nUsers created:")
    for row in cur.fetchall():
        print(f"  {row[1]:20} | {row[2]:25} | {row[3]:>10} BDT")
    
    cur.close()
    conn.close()
    print("\n✓ Test users created successfully!")
    
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
