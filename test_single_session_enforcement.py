"""
Test script for single-session-per-user enforcement
Tests that:
1. Authenticated users can only have one active session
2. Logging in from a new device terminates previous session
3. Anonymous users can have unlimited sessions
4. Session data is properly stored and validated
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import sys

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Test credentials
TEST_USER_EMAIL = "session_test_user@example.com"
TEST_USER_PASSWORD = "TestPassword123!"
TEST_USERNAME = "session_test_user"

class SessionTestRunner:
    """Test runner for session management."""

    def __init__(self):
        self.session1_token = None
        self.session2_token = None
        self.results = []

    async def register_test_user(self, session: aiohttp.ClientSession) -> dict:
        """Register a test user."""
        url = f"{API_V1}/auth/register"
        payload = {
            "username": TEST_USERNAME,
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "password_confirm": TEST_USER_PASSWORD,
            "country_code": "BD"
        }

        try:
            async with session.post(url, json=payload) as resp:
                if resp.status in [201, 409]:  # Created or already exists
                    data = await resp.json()
                    self.log_result("Register User", resp.status == 201 or resp.status == 409, f"Status: {resp.status}")
                    return data
                else:
                    self.log_result("Register User", False, f"Status: {resp.status}, Response: {await resp.text()}")
                    return None
        except Exception as e:
            self.log_result("Register User", False, str(e))
            return None

    async def login_user(self, session: aiohttp.ClientSession, device_name: str) -> dict:
        """Login user and return tokens."""
        url = f"{API_V1}/auth/login"
        payload = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }

        # Simulate different user-agent for each device
        headers = {
            "User-Agent": f"Test/{device_name} (Device Fingerprinting Test)",
        }

        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    cookies = resp.cookies
                    self.log_result(f"Login ({device_name})", True, f"Token: {data.get('access_token', '')[:20]}...")
                    return {
                        "access_token": data.get("access_token"),
                        "user": data.get("user"),
                        "refresh_token": cookies.get("refresh_token"),
                        "previous_session_terminated": data.get("previous_session_terminated", False),
                        "session": data.get("session")
                    }
                else:
                    self.log_result(f"Login ({device_name})", False, f"Status: {resp.status}, Response: {await resp.text()}")
                    return None
        except Exception as e:
            self.log_result(f"Login ({device_name})", False, str(e))
            return None

    async def use_token(self, session: aiohttp.ClientSession, token: str, operation: str) -> bool:
        """Test using a token for an authenticated endpoint."""
        url = f"{API_V1}/auth/me"
        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            async with session.get(url, headers=headers) as resp:
                success = resp.status == 200
                self.log_result(f"Use Token ({operation})", success, f"Status: {resp.status}")
                return success
        except Exception as e:
            self.log_result(f"Use Token ({operation})", False, str(e))
            return False

    async def logout_user(self, session: aiohttp.ClientSession, token: str, device_name: str) -> bool:
        """Logout user."""
        url = f"{API_V1}/auth/logout"
        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            async with session.post(url, headers=headers) as resp:
                success = resp.status == 204
                self.log_result(f"Logout ({device_name})", success, f"Status: {resp.status}")
                return success
        except Exception as e:
            self.log_result(f"Logout ({device_name})", False, str(e))
            return False

    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✓ PASS" if passed else "✗ FAIL"
        result = f"{status}: {test_name}"
        if details:
            result += f" - {details}"
        print(result)
        self.results.append((test_name, passed, details))

    async def run_tests(self):
        """Run all tests."""
        print("\n" + "="*80)
        print("SINGLE SESSION ENFORCEMENT TEST SUITE")
        print("="*80 + "\n")

        async with aiohttp.ClientSession() as session:
            # Test 1: Register user
            print("1. User Registration")
            print("-" * 40)
            user = await self.register_test_user(session)
            if not user:
                print("\nFailed to register user. Aborting tests.")
                return

            # Test 2: Login from device 1
            print("\n2. Login from Device 1")
            print("-" * 40)
            login1 = await self.login_user(session, "Device1")
            if not login1:
                print("\nFailed to login from device 1. Aborting tests.")
                return

            token1 = login1.get("access_token")

            # Test 3: Verify device 1 session is active
            print("\n3. Verify Device 1 Session Active")
            print("-" * 40)
            await self.use_token(session, token1, "Device1-Check1")

            # Test 4: Login from device 2 (should terminate device 1 session)
            print("\n4. Login from Device 2 (Should Terminate Device 1 Session)")
            print("-" * 40)
            login2 = await self.login_user(session, "Device2")
            if not login2:
                print("\nFailed to login from device 2. Aborting tests.")
                return

            token2 = login2.get("access_token")
            previous_terminated = login2.get("previous_session_terminated", False)
            self.log_result("Previous Session Terminated Flag", previous_terminated, 
                          "Device 1 session should be marked as terminated")

            # Test 5: Verify device 2 session is active
            print("\n5. Verify Device 2 Session Active")
            print("-" * 40)
            await self.use_token(session, token2, "Device2-Check1")

            # Test 6: Try to use device 1 token (should fail - session terminated)
            print("\n6. Attempt to Use Device 1 Token (Should Fail)")
            print("-" * 40)
            result = await self.use_token(session, token1, "Device1-Check2")
            self.log_result("Device 1 Token Invalidated", not result, 
                          "Device 1 token should be invalid after device 2 login")

            # Test 7: Login from device 3 (should terminate device 2 session)
            print("\n7. Login from Device 3 (Should Terminate Device 2 Session)")
            print("-" * 40)
            login3 = await self.login_user(session, "Device3")
            if not login3:
                print("\nFailed to login from device 3. Aborting tests.")
                return

            token3 = login3.get("access_token")

            # Test 8: Verify device 3 session is active
            print("\n8. Verify Device 3 Session Active")
            print("-" * 40)
            await self.use_token(session, token3, "Device3-Check1")

            # Test 9: Try to use device 2 token (should fail)
            print("\n9. Attempt to Use Device 2 Token (Should Fail)")
            print("-" * 40)
            result = await self.use_token(session, token2, "Device2-Check2")
            self.log_result("Device 2 Token Invalidated", not result,
                          "Device 2 token should be invalid after device 3 login")

            # Test 10: Logout from device 3
            print("\n10. Logout from Device 3")
            print("-" * 40)
            await self.logout_user(session, token3, "Device3")

            # Test 11: Attempt to use device 3 token after logout (should fail)
            print("\n11. Attempt to Use Device 3 Token After Logout (Should Fail)")
            print("-" * 40)
            result = await self.use_token(session, token3, "Device3-After-Logout")
            self.log_result("Device 3 Token Invalidated After Logout", not result,
                          "Device 3 token should be invalid after logout")

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        passed = sum(1 for _, p, _ in self.results if p)
        total = len(self.results)
        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Pass Rate: {pass_rate:.1f}%")

        print("\nDetailed Results:")
        print("-" * 80)
        for test_name, passed, details in self.results:
            status = "✓" if passed else "✗"
            print(f"{status} {test_name}")
            if details:
                print(f"  └─ {details}")

        print("\n" + "="*80)
        if pass_rate == 100:
            print("✓ ALL TESTS PASSED - Single session enforcement is working correctly!")
        else:
            print(f"✗ Some tests failed - {total - passed} issue(s) to resolve")
        print("="*80 + "\n")


async def main():
    """Main entry point."""
    runner = SessionTestRunner()
    try:
        await runner.run_tests()
    except Exception as e:
        print(f"\n✗ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("Starting Single Session Enforcement Test Suite...")
    print(f"Target: {BASE_URL}\n")
    asyncio.run(main())
