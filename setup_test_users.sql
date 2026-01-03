-- Clear test users if they exist
DELETE FROM users WHERE username IN ('testplayer', 'seller');

-- Create testplayer with 500K BDT
-- Password: TestPassword123!
INSERT INTO users (user_id, username, email, password_hash, balance_bdt, email_verified, created_at, updated_at)
VALUES (
    '24d92451-0620-4d3c-82e9-2c77aca61e77',
    'testplayer',
    'testplayer@example.com',
    '$2b$12$o6EPd.8k3Nm6c/2P6VpJjurFpvxWKf3T.vKJ1uHhEn9R1w6J6L9Z2',
    500000,
    true,
    NOW(),
    NOW()
);

-- Create seller account
INSERT INTO users (user_id, username, email, password_hash, balance_bdt, email_verified, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'seller',
    'seller@example.com',
    '$2b$12$o6EPd.8k3Nm6c/2P6VpJjurFpvxWKf3T.vKJ1uHhEn9R1w6J6L9Z2',
    1000000,
    true,
    NOW(),
    NOW()
);

-- Verify
SELECT user_id, username, email, balance_bdt FROM users ORDER BY username;
