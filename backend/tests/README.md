# Backend Tests

## Running Tests

### Install test dependencies
```bash
pip install pytest pytest-asyncio httpx
```

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_auth.py
```

### Run with coverage
```bash
pip install pytest-cov
pytest --cov=app tests/
```

## Test Structure

- `test_auth.py` - Authentication tests (register, login, JWT)
- `test_chunks.py` - World generation and chunk tests
- More test files can be added for:
  - `test_marketplace.py` - Marketplace and bidding
  - `test_lands.py` - Land ownership and fencing
  - `test_payments.py` - Payment gateway webhooks
  - `test_chat.py` - WebSocket chat functionality

## Notes

- Tests use FastAPI's TestClient for HTTP testing
- Database is expected to be running (or use pytest fixtures with test database)
- Some tests may require environment variables from `.env`
