"""
WebSocket Integration Tests for Phase 2
Tests real-time messaging, presence, and typing indicators
"""
import asyncio
import json
import websockets
import requests
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000/api/v1"
WS_URL = "ws://localhost:8001/ws"

# Test user credentials
TIMESTAMP = int(datetime.now().timestamp())
TEST_USER_1 = {
    "username": f"wsuser1_{TIMESTAMP}",
    "email": f"wsuser1_{TIMESTAMP}@signalink.com",
    "password": "Test123!@#",
    "full_name": "WebSocket User 1"
}
TEST_USER_2 = {
    "username": f"wsuser2_{TIMESTAMP}",
    "email": f"wsuser2_{TIMESTAMP}@signalink.com",
    "password": "Test123!@#",
    "full_name": "WebSocket User 2"
}


def print_test(test_name: str):
    """Print test header"""
    print(f"\n{'='*60}")
    print(f"[TEST] {test_name}")
    print('='*60)


def register_and_login(user_data: dict) -> str:
    """Register user and get JWT token"""
    # Try to register (might already exist)
    resp = requests.post(f"{API_URL}/users/register", json=user_data)
    # Ignore if already exists, just try to login

    # Login
    login_data = {
        "username": user_data["username"],
        "password": user_data["password"]
    }
    resp = requests.post(f"{API_URL}/users/login", json=login_data)
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return None

    token_data = resp.json()
    return token_data["access_token"]


def create_test_channel(token: str, channel_name: str) -> str:
    """Create a test channel and return channel_id"""
    headers = {"Authorization": f"Bearer {token}"}
    channel_data = {
        "name": channel_name,
        "description": "WebSocket test channel",
        "is_private": False
    }
    resp = requests.post(f"{API_URL}/channels/", json=channel_data, headers=headers)
    if resp.status_code not in [200, 201]:
        print(f"Channel creation failed (status {resp.status_code}): {resp.text}")
        return None

    channel = resp.json()
    return channel["id"]


async def test_websocket_connection():
    """Test 1: Basic WebSocket connection"""
    print_test("Test 1: WebSocket Connection")

    # Setup
    token = register_and_login(TEST_USER_1)
    if not token:
        print("[FAIL] Failed to get token")
        return False

    # Connect to WebSocket
    try:
        async with websockets.connect(f"{WS_URL}?token={token}") as websocket:
            print("[OK] WebSocket connected successfully")

            # Send ping
            ping_msg = {"type": "ping"}
            await websocket.send(json.dumps(ping_msg))
            print("--> Sent: ping")

            # Receive pong
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"<-- Received: {data}")

            if data.get("type") == "pong":
                print("[OK] Ping/Pong successful")
                return True
            else:
                print("[FAIL] Expected pong, got:", data)
                return False

    except Exception as e:
        print(f"[FAIL] Connection failed: {e}")
        return False


async def test_channel_subscription():
    """Test 2: Channel subscription"""
    print_test("Test 2: Channel Subscription")

    token = register_and_login(TEST_USER_1)
    channel_id = create_test_channel(token, f"test_channel_{TIMESTAMP}")

    if not token or not channel_id:
        print("[FAIL] Setup failed")
        return False

    try:
        async with websockets.connect(f"{WS_URL}?token={token}") as websocket:
            # Subscribe to channel
            subscribe_msg = {
                "type": "channel.subscribe",
                "channel_id": channel_id
            }
            await websocket.send(json.dumps(subscribe_msg))
            print(f"--> Sent: channel.subscribe to {channel_id}")

            # Wait for success response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"<-- Received: {data}")

            if data.get("type") == "success":
                print("[OK] Channel subscription successful")
                return True
            else:
                print("[FAIL] Subscription failed:", data)
                return False

    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        return False


async def test_real_time_messaging():
    """Test 3: Real-time message broadcasting"""
    print_test("Test 3: Real-Time Message Broadcasting")

    # Setup two users
    token1 = register_and_login(TEST_USER_1)
    token2 = register_and_login(TEST_USER_2)
    channel_id = create_test_channel(token1, f"test_msg_channel_{TIMESTAMP}")

    if not all([token1, token2, channel_id]):
        print("[FAIL] Setup failed")
        return False

    try:
        # Connect both users
        async with websockets.connect(f"{WS_URL}?token={token1}") as ws1, \
                   websockets.connect(f"{WS_URL}?token={token2}") as ws2:

            print("[OK] Both users connected")

            # Subscribe both to channel
            for ws, user in [(ws1, "User1"), (ws2, "User2")]:
                subscribe_msg = {
                    "type": "channel.subscribe",
                    "channel_id": channel_id
                }
                await ws.send(json.dumps(subscribe_msg))
                # Wait for success
                resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(resp)
                print(f"[OK] {user} subscribed: {data.get('message', 'OK')}")

            # User 1 sends a message
            message_content = f"Hello from WebSocket at {datetime.now().isoformat()}"
            send_msg = {
                "type": "message.send",
                "channel_id": channel_id,
                "content": message_content,
                "message_type": "text"
            }
            await ws1.send(json.dumps(send_msg))
            print(f"--> User1 sent message: {message_content}")

            # Wait a moment for Redis pub/sub to propagate
            await asyncio.sleep(0.5)

            # User 2 should receive the broadcast
            response = await asyncio.wait_for(ws2.recv(), timeout=10.0)
            received = json.loads(response)
            print(f"<-- User2 received: {json.dumps(received, indent=2)}")

            if received.get("type") == "message.receive" and received.get("content") == message_content:
                print("[OK] Real-time messaging works!")
                return True
            else:
                print("[FAIL] Did not receive expected message")
                return False

    except asyncio.TimeoutError:
        print("[FAIL] Timeout waiting for message")
        return False
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        return False


async def test_typing_indicators():
    """Test 4: Typing indicators"""
    print_test("Test 4: Typing Indicators")

    token1 = register_and_login(TEST_USER_1)
    token2 = register_and_login(TEST_USER_2)
    channel_id = create_test_channel(token1, f"test_typing_{TIMESTAMP}")

    if not all([token1, token2, channel_id]):
        print("[FAIL] Setup failed")
        return False

    try:
        async with websockets.connect(f"{WS_URL}?token={token1}") as ws1, \
                   websockets.connect(f"{WS_URL}?token={token2}") as ws2:

            # Subscribe both users
            for ws in [ws1, ws2]:
                await ws.send(json.dumps({"type": "channel.subscribe", "channel_id": channel_id}))
                await ws.recv()  # Success response

            print("[OK] Both users subscribed")

            # User 1 starts typing
            typing_msg = {
                "type": "typing.start",
                "channel_id": channel_id
            }
            await ws1.send(json.dumps(typing_msg))
            print("--> User1 started typing")

            # User 2 should receive typing indicator
            response = await asyncio.wait_for(ws2.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"<-- User2 received: {data}")

            if data.get("type") == "typing.indicator" and data.get("is_typing") == True:
                print("[OK] Typing indicators work!")
                return True
            else:
                print("[FAIL] Did not receive typing indicator")
                return False

    except asyncio.TimeoutError:
        print("[FAIL] Timeout waiting for typing indicator")
        return False
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        return False


async def test_presence_tracking():
    """Test 5: User presence (online/offline)"""
    print_test("Test 5: Presence Tracking")

    token = register_and_login(TEST_USER_1)

    # Check stats before connection
    resp = requests.get("http://localhost:8001/stats")
    stats_before = resp.json()
    print(f"[STATS] Stats before: {stats_before['unique_users_online']} users online")

    try:
        async with websockets.connect(f"{WS_URL}?token={token}") as websocket:
            # Wait a moment for presence update
            await asyncio.sleep(1)

            # Check stats during connection
            resp = requests.get("http://localhost:8001/stats")
            stats_during = resp.json()
            print(f"[STATS] Stats during: {stats_during['unique_users_online']} users online")

        # Wait for disconnect to propagate
        await asyncio.sleep(1)

        # Check stats after disconnect
        resp = requests.get("http://localhost:8001/stats")
        stats_after = resp.json()
        print(f"[STATS] Stats after: {stats_after['unique_users_online']} users online")

        if stats_during['unique_users_online'] > stats_before['unique_users_online']:
            print("[OK] Presence tracking works!")
            return True
        else:
            print("[FAIL] Presence not updated correctly")
            return False

    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        return False


async def run_all_tests():
    """Run all WebSocket tests"""
    print("\n" + "="*60)
    print("SIGNALINK WEBSOCKET INTEGRATION TESTS - PHASE 2")
    print("="*60)

    tests = [
        ("WebSocket Connection", test_websocket_connection),
        ("Channel Subscription", test_channel_subscription),
        ("Real-Time Messaging", test_real_time_messaging),
        ("Typing Indicators", test_typing_indicators),
        ("Presence Tracking", test_presence_tracking),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
            await asyncio.sleep(1)  # Brief pause between tests
        except Exception as e:
            print(f"[FAIL] {test_name} crashed: {e}")
            results.append((test_name, False))

    # Print summary
    print("\n" + "="*60)
    print("[STATS] TEST SUMMARY")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
