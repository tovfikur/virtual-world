#!/usr/bin/env python3
"""Create test lands in the database for testing"""

import psycopg2
import uuid
from datetime import datetime

conn = psycopg2.connect(
    dbname="virtualworld",
    user="virtualworld",
    password="CHANGEME_STRONG_PASSWORD_HERE",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

seller_id = "00000000-0000-0000-0000-000000000001"
testplayer_id = "24d92451-0620-4d3c-82e9-2c77aca61e77"

# Create test lands from different biomes, owned by seller
biomes = ["OCEAN", "BEACH", "PLAINS", "FOREST", "DESERT", "MOUNTAIN", "SNOW"]
lands = []

print("Creating test lands owned by seller...")
for i, biome in enumerate(biomes):
    for j in range(3):  # 3 lands per biome
        land_id = str(uuid.uuid4())
        land = {
            "land_id": land_id,
            "x": i * 10 + j,
            "y": i * 10 + j,
            "biome": biome,
            "elevation": 0.5,
            "moisture": 0.5,
            "temperature": 0.5,
            "price_base_bdt": 100 + (i * 10),
            "owner_id": seller_id
        }
        
        cur.execute("""
            INSERT INTO lands (land_id, x, y, z, biome, elevation, color_hex, 
                             price_base_bdt, owner_id, created_at, updated_at, fenced, for_sale)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), false, false)
        """, (
            land_id,
            land["x"], land["y"], 0,  # z = 0
            biome,
            land["elevation"],
            "#808080",  # gray color
            land["price_base_bdt"],
            seller_id
        ))
        lands.append(land)

conn.commit()

# Verify
cur.execute("SELECT COUNT(*), biome FROM lands WHERE owner_id IS NOT NULL GROUP BY biome ORDER BY biome")
for count, biome in cur.fetchall():
    print(f"  {biome:10}: {count} lands")

print(f"\nTotal lands created: {len(lands)}")

# Get first few lands for listing
cur.execute("SELECT land_id FROM lands WHERE owner_id = %s ORDER BY biome LIMIT 5", (seller_id,))
listing_lands = [row[0] for row in cur.fetchall()]

print(f"\nUse these land IDs for creating a listing:")
for i, land_id in enumerate(listing_lands):
    print(f"  {i+1}. {land_id}")

cur.close()
conn.close()
