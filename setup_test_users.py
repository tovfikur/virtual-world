#!/usr/bin/env python3
"""Setup test users in database"""

import psycopg2
import sys

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
    
    # Create testplayer with 500K BDT
    cur.execute("""
        INSERT INTO users (user_id, username, email, password_hash, role, balance_bdt, verified, is_banned, is_suspended, failed_login_attempts, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
    """, (
        '24d92451-0620-4d3c-82e9-2c77aca61e77',
        'testplayer',
        'testplayer@example.com',
        '$2b$12$o6EPd.8k3Nm6c/2P6VpJjurFpvxWKf3T.vKJ1uHhEn9R1w6J6L9Z2',  # TestPassword123!
        'USER',  # role
        500000,  # balance
        True,    # verified
        False,   # is_banned
        False,   # is_suspended
        0        # failed_login_attempts
    ))
    
    # Create seller account with 1M BDT
    cur.execute("""
        INSERT INTO users (user_id, username, email, password_hash, role, balance_bdt, verified, is_banned, is_suspended, failed_login_attempts, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
    """, (
        '00000000-0000-0000-0000-000000000001',
        'seller',
        'seller@example.com',
        '$2b$12$o6EPd.8k3Nm6c/2P6VpJjurFpvxWKf3T.vKJ1uHhEn9R1w6J6L9Z2',  # TestPassword123!
        'USER',  # role
        1000000, # balance
        True,    # verified
        False,   # is_banned
        False,   # is_suspended
        0        # failed_login_attempts
    ))
    
    conn.commit()
    
    # Verify
    cur.execute("SELECT user_id, username, email, balance_bdt FROM users ORDER BY username")
    for row in cur.fetchall():
        print(f"{row[1]:20} | {row[2]:25} | {row[3]:>10} BDT | {row[0]}")
    
    cur.close()
    conn.close()
    print("\n✓ Test users created successfully!")
    
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
