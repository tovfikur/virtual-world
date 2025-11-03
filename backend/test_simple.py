"""
Simple API Test - Phase 2-4 Verification
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def test_all():
    """Run all tests."""
    print("=" * 60)
    print("Virtual Land World - API Test Suite")
    print("=" * 60)

    tests_passed = 0
    tests_total = 0

    # Test 1: Imports
    print("\n[1/6] Testing imports...")
    tests_total += 1
    try:
        from app.main import app
        from app.services.world_service import world_service
        from app.services.marketplace_service import marketplace_service
        from app.api.v1.endpoints import auth, users, lands, chunks, marketplace
        print("    PASS - All modules imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"    FAIL - {e}")

    # Test 2: Models
    print("\n[2/6] Testing models...")
    tests_total += 1
    try:
        from app.models.user import User, UserRole
        from app.models.land import Land, Biome
        from app.models.listing import Listing, ListingType
        from app.models.bid import Bid
        from app.models.transaction import Transaction

        biome_count = len(list(Biome))
        listing_types = len(list(ListingType))
        print(f"    PASS - Models loaded ({biome_count} biomes, {listing_types} listing types)")
        tests_passed += 1
    except Exception as e:
        print(f"    FAIL - {e}")

    # Test 3: Schemas
    print("\n[3/6] Testing schemas...")
    tests_total += 1
    try:
        from app.schemas.user_schema import UserCreate, UserResponse
        from app.schemas.land_schema import LandResponse
        from app.schemas.listing_schema import ListingCreate

        user = UserCreate(
            username="test",
            email="test@example.com",
            password="SecurePass123!@#"
        )
        print(f"    PASS - Schemas validated (user: {user.username})")
        tests_passed += 1
    except Exception as e:
        print(f"    FAIL - {e}")

    # Test 4: World Generation
    print("\n[4/6] Testing world generation...")
    tests_total += 1
    try:
        from app.services.world_service import world_service

        land = world_service.get_land_at(0, 0)
        assert "biome" in land
        assert "elevation" in land

        chunk = world_service.generate_chunk(0, 0, 16)
        assert len(chunk["lands"]) == 16 * 16

        # Test determinism
        land1 = world_service.get_land_at(5, 5)
        land2 = world_service.get_land_at(5, 5)
        assert land1 == land2

        print(f"    PASS - World generation working (chunk: {chunk['chunk_id']}, {len(chunk['lands'])} lands)")
        tests_passed += 1
    except Exception as e:
        print(f"    FAIL - {e}")

    # Test 5: Configuration
    print("\n[5/6] Testing configuration...")
    tests_total += 1
    try:
        from app.config import settings, CACHE_TTLS

        assert hasattr(settings, "WORLD_SEED")
        assert "chunk" in CACHE_TTLS

        print(f"    PASS - Config loaded (seed: {settings.WORLD_SEED}, {len(CACHE_TTLS)} cache TTLs)")
        tests_passed += 1
    except Exception as e:
        print(f"    FAIL - {e}")

    # Test 6: Endpoints
    print("\n[6/6] Testing endpoint registration...")
    tests_total += 1
    try:
        from app.main import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]

        required = [
            "/api/v1/auth/register",
            "/api/v1/users/{user_id}",
            "/api/v1/lands/{land_id}",
            "/api/v1/chunks/{chunk_x}/{chunk_y}",
            "/api/v1/marketplace/listings"
        ]

        found = sum(1 for r in required if r in routes)

        if found == len(required):
            print(f"    PASS - All {found} key endpoints registered ({len(routes)} total routes)")
            tests_passed += 1
        else:
            print(f"    FAIL - Only {found}/{len(required)} endpoints found")
    except Exception as e:
        print(f"    FAIL - {e}")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {tests_passed}/{tests_total}")

    if tests_passed == tests_total:
        print("\nSUCCESS - All tests passed!")
        print("\nNext steps:")
        print("  1. Start PostgreSQL and Redis")
        print("  2. Run: uvicorn app.main:app --reload")
        print("  3. Visit: http://localhost:8000/api/docs")
        return 0
    else:
        print(f"\nFAILED - {tests_total - tests_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(test_all())
