-- Create a seller user
INSERT INTO users (user_id, username, email, password_hash, balance_bdt, role)
VALUES ('12345678-1234-1234-1234-123456789abc', 'seller', 'seller@example.com', 'hashed_pwd', 100000, 'user')
ON CONFLICT (user_id) DO NOTHING;

-- Create some sample lands for Plains biome with owner
INSERT INTO lands (land_id, x, y, biome, elevation, owner_id, price_base_bdt)
VALUES 
  ('aaaaaaaa-aaaa-aaaa-aaaa-000000000001', 10, 10, 'plains', 50, '12345678-1234-1234-1234-123456789abc', 1000),
  ('aaaaaaaa-aaaa-aaaa-aaaa-000000000002', 11, 10, 'plains', 51, '12345678-1234-1234-1234-123456789abc', 1010),
  ('aaaaaaaa-aaaa-aaaa-aaaa-000000000003', 12, 10, 'plains', 49, '12345678-1234-1234-1234-123456789abc', 990),
  ('aaaaaaaa-aaaa-aaaa-aaaa-000000000004', 13, 10, 'plains', 52, '12345678-1234-1234-1234-123456789abc', 1020),
  ('aaaaaaaa-aaaa-aaaa-aaaa-000000000005', 14, 10, 'plains', 48, '12345678-1234-1234-1234-123456789abc', 980)
ON CONFLICT (land_id) DO NOTHING;

-- Create some sample lands for Desert biome with owner
INSERT INTO lands (land_id, x, y, biome, elevation, owner_id, price_base_bdt)
VALUES 
  ('bbbbbbbb-bbbb-bbbb-bbbb-000000000001', 20, 20, 'desert', 30, '12345678-1234-1234-1234-123456789abc', 800),
  ('bbbbbbbb-bbbb-bbbb-bbbb-000000000002', 21, 20, 'desert', 31, '12345678-1234-1234-1234-123456789abc', 810),
  ('bbbbbbbb-bbbb-bbbb-bbbb-000000000003', 22, 20, 'desert', 29, '12345678-1234-1234-1234-123456789abc', 790),
  ('bbbbbbbb-bbbb-bbbb-bbbb-000000000004', 23, 20, 'desert', 32, '12345678-1234-1234-1234-123456789abc', 820),
  ('bbbbbbbb-bbbb-bbbb-bbbb-000000000005', 24, 20, 'desert', 28, '12345678-1234-1234-1234-123456789abc', 780)
ON CONFLICT (land_id) DO NOTHING;

-- Create a simple listing (fixed price)
INSERT INTO listings (listing_id, seller_id, type, status, price_bdt)
VALUES ('11111111-1111-1111-1111-111111111111', '12345678-1234-1234-1234-123456789abc', 'fixed_price', 'active', 5000)
ON CONFLICT (listing_id) DO NOTHING;

-- Add lands to the listing
INSERT INTO listing_lands (listing_id, land_id)
VALUES 
  ('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'),
  ('11111111-1111-1111-1111-111111111111', 'bbbbbbbb-bbbb-bbbb-bbbb-000000000001')
ON CONFLICT (listing_id, land_id) DO NOTHING;

-- Check what we have
SELECT biome, COUNT(*) as land_count, AVG(price_base_bdt) as avg_price 
FROM lands 
WHERE owner_id = '12345678-1234-1234-1234-123456789abc'
GROUP BY biome;
