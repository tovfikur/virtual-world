#!/usr/bin/env python3
import psycopg2
import uuid

conn = psycopg2.connect(
    dbname="virtualworld",
    user="virtualworld",
    password="CHANGEME_STRONG_PASSWORD_HERE",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

seller_id = "2da2eab8-fe1f-4d5d-b179-344a40121519"  # Current admin user

# Simple: just create 3 lands in different biomes
lands_to_create = [
    ("PLAINS", 100),
    ("DESERT", 150),
    ("FOREST", 120),
]

print("Creating test lands...")
land_ids = []

for biome, price in lands_to_create:
    for i in range(2):  # 2 per biome
        land_id = str(uuid.uuid4())
        land_ids.append(land_id)
        x = len(land_ids) * 10  # Use incrementing x coordinates
        y = len(land_ids) * 10
        
        cur.execute(
            "INSERT INTO lands (land_id, x, y, z, biome, elevation, color_hex, shape, width, height, price_base_bdt, owner_id, created_at, updated_at, fenced, for_sale) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), false, false)",
            (land_id, x, y, 0, biome, 0.5, "#808080", "SQUARE", 1.0, 1.0, price, seller_id)
        )
        print(f"  Created {land_id[:8]}... ({biome} @ {price} BDT) at ({x}, {y})")

conn.commit()
print(f"\n✓ Created {len(land_ids)} test lands")
print(f"Land IDs: {land_ids}")
cur.close()
conn.close()
