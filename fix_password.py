#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    dbname="virtualworld",
    user="virtualworld",
    password="CHANGEME_STRONG_PASSWORD_HERE",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# Create or update testplayer
password_hash = "$2b$12$WlkHUhuoca3u5CR3R8aRc.YW3x6oF90feFphkT9dk/S/0LgBvAuNO"

# Delete if exists
cur.execute("DELETE FROM users WHERE username = 'testplayer'")

# Create new
cur.execute("""
    INSERT INTO users (user_id, username, email, password_hash, role, balance_bdt, verified, is_banned, is_suspended, failed_login_attempts, created_at, updated_at)
    VALUES ('24d92451-0620-4d3c-82e9-2c77aca61e77', 'testplayer', 'testplayer@example.com', %s, 'USER', 500000, true, false, false, 0, NOW(), NOW())
""", (password_hash,))

conn.commit()

# Verify
cur.execute("SELECT username, email, balance_bdt FROM users WHERE username = 'testplayer'")
user = cur.fetchone()
if user:
    print(f"✓ testplayer created: {user[1]}, balance: {user[2]:,} BDT")
else:
    print("✗ Failed to create testplayer")

cur.close()
conn.close()
