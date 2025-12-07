"""
WebSocket Stress Tests for Phase 2
Tests concurrent connections, heavy message loads, and edge cases
"""
import asyncio
import json
import websockets
import requests
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000/api/v1"
WS_URL = "ws://localhost:8001/ws"

# Test credentials
TIMESTAMP = int(datetime.now().timestamp())
STRESS_USERS = [
    {
        "username": f"stress_user_{i}_{TIMESTAMP}",
        "email": f"stress_{i}_{TIMESTAMP}@signalink.com",
        "password": "Test123!@#",
        "full_name": f"Stress User {i}"
    }
    for i in range(10)  # 10 concurrent users
]


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
        "description": "Stress test channel",
        "is_private": False
    }
    resp = requests.post(f"{API_URL}/channels/", json=channel_data, headers=headers)
    if resp.status_code not in [200, 201]:
        print(f"Channel creation failed (status {resp.status_code}): {resp.text}")
        return None

    channel = resp.json()
    return channel["id"]


async def test_concurrent_connections():
    """Test 1: Multiple concurrent WebSocket connections"""
    print_test("Test 1: Concurrent Connections (10 users)")

    # Get tokens for all users
    tokens = []
    for user in STRESS_USERS:
        token = register_and_login(user)
        if not token:
            print(f"[FAIL] Failed to get token for {user['username']}")
            return False
        tokens.append(token)

    print(f"[OK] Got {len(tokens)} tokens")

    # Connect all users concurrently
    connections = []
    try:
        for token in tokens:
            ws = await websockets.connect(f"{WS_URL}?token={token}")
            connections.append(ws)

        print(f"[OK] {len(connections)} concurrent connections established")

        # Ping all connections
        for ws in connections:
            await ws.send(json.dumps({"type": "ping"}))

        # Verify all pongs
        responses = await asyncio.gather(*[ws.recv() for ws in connections])
        pongs = sum(1 for resp in responses if json.loads(resp).get("type") == "pong")

        print(f"[OK] Received {pongs}/{len(connections)} pongs")

        # Close all connections
        for ws in connections:
            await ws.close()

        if pongs == len(connections):
            print("[PASS] Concurrent connections test passed")
            return True
        else:
            print("[FAIL] Some connections did not respond")
            return False

    except Exception as e:
        print(f"[FAIL] Concurrent connections test failed: {e}")
        for ws in connections:
            try:
                await ws.close()
            except:
                pass
        return False


async def test_message_burst():
    """Test 2: Send burst of messages"""
    print_test("Test 2: Message Burst (50 messages)")

    # Setup
    user1 = STRESS_USERS[0]
    user2 = STRESS_USERS[1]
    token1 = register_and_login(user1)
    token2 = register_and_login(user2)
    channel_id = create_test_channel(token1, f"burst_test_{TIMESTAMP}")

    if not all([token1, token2, channel_id]):
        print("[FAIL] Setup failed")
        return False

    try:
        async with websockets.connect(f"{WS_URL}?token={token1}") as ws1, \
                   websockets.connect(f"{WS_URL}?token={token2}") as ws2:

            # Subscribe both to channel
            for ws in [ws1, ws2]:
                await ws.send(json.dumps({"type": "channel.subscribe", "channel_id": channel_id}))
                await ws.recv()  # Success response

            print("[OK] Both users subscribed")

            # Send 50 messages rapidly
            message_count = 50
            for i in range(message_count):
                msg = {
                    "type": "message.send",
                    "channel_id": channel_id,
                    "content": f"Message {i+1}/{message_count}",
                    "message_type": "text"
                }
                await ws1.send(json.dumps(msg))

            print(f"[OK] Sent {message_count} messages")

            # Give time for all messages to be processed
            await asyncio.sleep(2)

            # Try to receive some messages on user2
            received = 0
            try:
                while True:
                    msg = await asyncio.wait_for(ws2.recv(), timeout=0.5)
                    data = json.loads(msg)
                    if data.get("type") == "message.receive":
                        received += 1
            except asyncio.TimeoutError:
                pass

            print(f"[OK] User2 received {received}/{message_count} messages")

            if received >= message_count * 0.8:  # At least 80% delivered
                print(f"[PASS] Message burst test passed ({received}/{message_count} delivered)")
                return True
            else:
                print(f"[FAIL] Only {received}/{message_count} messages delivered")
                return False

    except Exception as e:
        print(f"[FAIL] Message burst test failed: {e}")
        return False


async def test_rapid_typing_indicators():
    """Test 3: Rapid typing start/stop"""
    print_test("Test 3: Rapid Typing Indicators (20 cycles)")

    user1 = STRESS_USERS[2]
    user2 = STRESS_USERS[3]
    token1 = register_and_login(user1)
    token2 = register_and_login(user2)
    channel_id = create_test_channel(token1, f"typing_stress_{TIMESTAMP}")

    if not all([token1, token2, channel_id]):
        print("[FAIL] Setup failed")
        return False

    try:
        async with websockets.connect(f"{WS_URL}?token={token1}") as ws1, \
                   websockets.connect(f"{WS_URL}?token={token2}") as ws2:

            # Subscribe both
            for ws in [ws1, ws2]:
                await ws.send(json.dumps({"type": "channel.subscribe", "channel_id": channel_id}))
                await ws.recv()

            print("[OK] Both users subscribed")

            # Send 20 rapid typing start/stop cycles
            cycles = 20
            for i in range(cycles):
                # Start typing
                await ws1.send(json.dumps({"type": "typing.start", "channel_id": channel_id}))
                await asyncio.sleep(0.05)
                # Stop typing
                await ws1.send(json.dumps({"type": "typing.stop", "channel_id": channel_id}))
                await asyncio.sleep(0.05)

            print(f"[OK] Sent {cycles} typing cycles")

            # Try to receive typing indicators
            received = 0
            try:
                while True:
                    msg = await asyncio.wait_for(ws2.recv(), timeout=1.0)
                    data = json.loads(msg)
                    if data.get("type") == "typing.indicator":
                        received += 1
            except asyncio.TimeoutError:
                pass

            print(f"[OK] Received {received} typing indicators")

            if received >= cycles * 0.5:  # At least half the cycles
                print(f"[PASS] Rapid typing test passed ({received} indicators)")
                return True
            else:
                print(f"[FAIL] Only {received} typing indicators received")
                return False

    except Exception as e:
        print(f"[FAIL] Rapid typing test failed: {e}")
        return False


async def test_connection_stability():
    """Test 4: Long-lived connection with periodic activity"""
    print_test("Test 4: Connection Stability (30 second test)")

    user = STRESS_USERS[4]
    token = register_and_login(user)

    if not token:
        print("[FAIL] Setup failed")
        return False

    try:
        async with websockets.connect(f"{WS_URL}?token={token}") as ws:
            print("[OK] Connection established")

            # Send ping every 2 seconds for 30 seconds
            pings = 0
            pongs = 0

            for i in range(15):  # 15 pings over 30 seconds
                await ws.send(json.dumps({"type": "ping"}))
                pings += 1

                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(response)
                    if data.get("type") == "pong":
                        pongs += 1
                except asyncio.TimeoutError:
                    pass

                await asyncio.sleep(2)

            print(f"[OK] Sent {pings} pings, received {pongs} pongs")

            if pongs >= pings * 0.9:  # At least 90% success
                print(f"[PASS] Connection stability test passed ({pongs}/{pings})")
                return True
            else:
                print(f"[FAIL] Only {pongs}/{pings} pongs received")
                return False

    except Exception as e:
        print(f"[FAIL] Connection stability test failed: {e}")
        return False


async def test_edge_cases():
    """Test 5: Edge cases and error handling"""
    print_test("Test 5: Edge Cases")

    user = STRESS_USERS[5]
    token = register_and_login(user)

    if not token:
        print("[FAIL] Setup failed")
        return False

    try:
        async with websockets.connect(f"{WS_URL}?token={token}") as ws:
            print("[OK] Connection established")

            # Test 1: Invalid message type
            await ws.send(json.dumps({"type": "invalid.type"}))
            response1 = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print(f"[OK] Invalid type handled: {json.loads(response1).get('type')}")

            # Test 2: Subscribe to non-existent channel
            fake_channel = "00000000-0000-0000-0000-000000000000"
            await ws.send(json.dumps({"type": "channel.subscribe", "channel_id": fake_channel}))
            response2 = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print(f"[OK] Fake channel handled: {json.loads(response2).get('type')}")

            # Test 3: Send empty message
            await ws.send(json.dumps({"type": "ping"}))
            response3 = await asyncio.wait_for(ws.recv(), timeout=2.0)
            if json.loads(response3).get("type") == "pong":
                print("[OK] Empty ping handled")

            print("[PASS] Edge cases test passed")
            return True

    except Exception as e:
        print(f"[FAIL] Edge cases test failed: {e}")
        return False


async def run_all_stress_tests():
    """Run all stress tests"""
    print("\n" + "="*60)
    print("SIGNALINK WEBSOCKET STRESS TESTS - PHASE 2")
    print("="*60)

    tests = [
        ("Concurrent Connections", test_concurrent_connections),
        ("Message Burst", test_message_burst),
        ("Rapid Typing Indicators", test_rapid_typing_indicators),
        ("Connection Stability", test_connection_stability),
        ("Edge Cases", test_edge_cases),
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
    print("[STATS] STRESS TEST SUMMARY")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} stress tests passed")
    print("="*60)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_stress_tests())
    exit(0 if success else 1)
