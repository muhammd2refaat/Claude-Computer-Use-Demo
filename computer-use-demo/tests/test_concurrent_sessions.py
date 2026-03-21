#!/usr/bin/env python3
"""
Concurrent Session Test Script

This script verifies that the Computer-Use system handles multiple
concurrent sessions in TRUE PARALLEL (not queued execution).

Test Requirements:
- Two sessions must start processing simultaneously
- Each session must have its own isolated display
- Firefox must launch independently in each session
- Second session MUST NOT wait for first to complete
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, List

import httpx

API_BASE = "http://localhost:8000"


def log(message: str, level: str = "INFO"):
    """Pretty print log messages."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    colors = {
        "INFO": "\033[36m",  # Cyan
        "SUCCESS": "\033[92m",  # Green
        "ERROR": "\033[91m",  # Red
        "WARN": "\033[93m",  # Yellow
    }
    reset = "\033[0m"
    print(f"{colors.get(level, '')}{timestamp} [{level}]{reset} {message}")


async def create_session(client: httpx.AsyncClient, title: str) -> Dict:
    """Create a new agent session."""
    log(f"Creating session: {title}")
    resp = await client.post(f"{API_BASE}/api/sessions", json={"title": title})
    resp.raise_for_status()
    session = resp.json()
    log(f"Session created: {session['id'][:8]} on display :{session['vnc_info']['display_num']}", "SUCCESS")
    return session


async def send_message(client: httpx.AsyncClient, session_id: str, text: str):
    """Send a message to a session."""
    log(f"[{session_id[:8]}] Sending message: {text[:50]}...")
    resp = await client.post(
        f"{API_BASE}/api/sessions/{session_id}/messages",
        json={"text": text}
    )
    resp.raise_for_status()
    result = resp.json()
    log(f"[{session_id[:8]}] Message sent, agent processing...", "SUCCESS")
    return result


async def monitor_session_stream(client: httpx.AsyncClient, session_id: str, events: List[Dict]):
    """Monitor SSE stream and collect events."""
    log(f"[{session_id[:8]}] Connecting to SSE stream...")

    async with client.stream(
        "GET", f"{API_BASE}/api/sessions/{session_id}/stream"
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
                event = {"type": event_type, "data": data, "time": time.time()}
                events.append(event)

                # Log important events
                if event_type == "text":
                    log(f"[{session_id[:8]}] Agent: {data.get('text', '')[:40]}...", "INFO")
                elif event_type == "tool_use":
                    log(f"[{session_id[:8]}] 🔧 Using tool: {data.get('name')}", "INFO")
                elif event_type == "done":
                    log(f"[{session_id[:8]}] ✅ Task completed!", "SUCCESS")
                    return
                elif event_type == "error":
                    log(f"[{session_id[:8]}] ❌ Error: {data.get('message')}", "ERROR")
                    return


async def test_concurrent_sessions():
    """Main test: Create two concurrent sessions and verify parallel execution."""

    print("\n" + "="*70)
    print("CONCURRENT SESSION TEST")
    print("="*70 + "\n")

    log("Starting concurrent session test...")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Test 1: Create two sessions
        log("\n[TEST 1] Creating two sessions...", "INFO")
        session1 = await create_session(client, "Tokyo Weather")
        session2 = await create_session(client, "New York Weather")

        assert session1["vnc_info"]["display_num"] != session2["vnc_info"]["display_num"], \
            "Sessions must have different display numbers!"
        log(f"✅ Sessions have isolated displays: {session1['vnc_info']['display_num']} vs {session2['vnc_info']['display_num']}", "SUCCESS")

        # Test 2: Send messages to both sessions SIMULTANEOUSLY
        log("\n[TEST 2] Sending concurrent requests...", "INFO")

        events1: List[Dict] = []
        events2: List[Dict] = []

        # Record start times
        start_time = time.time()

        # Start both tasks at (nearly) the same time
        task1 = asyncio.create_task(send_message(
            client, session1["id"], "Search the weather in Tokyo"
        ))
        task2 = asyncio.create_task(send_message(
            client, session2["id"], "Search the weather in New York"
        ))

        # Wait for both messages to be sent
        await asyncio.gather(task1, task2)

        send_time_delta = time.time() - start_time
        log(f"Both messages sent in {send_time_delta:.2f}s", "SUCCESS")

        # Test 3: Monitor both streams in parallel
        log("\n[TEST 3] Monitoring parallel execution...", "INFO")

        monitor1 = asyncio.create_task(monitor_session_stream(client, session1["id"], events1))
        monitor2 = asyncio.create_task(monitor_session_stream(client, session2["id"], events2))

        # Wait for both to complete (with timeout)
        try:
            await asyncio.wait_for(
                asyncio.gather(monitor1, monitor2),
                timeout=180.0  # 3 minutes max
            )
        except asyncio.TimeoutError:
            log("Test timed out after 3 minutes!", "ERROR")
            return False

        # Test 4: Verify parallel execution
        log("\n[TEST 4] Analyzing execution timing...", "INFO")

        # Get first tool_use event from each session
        first_tool1 = next((e for e in events1 if e["type"] == "tool_use"), None)
        first_tool2 = next((e for e in events2 if e["type"] == "tool_use"), None)

        if not first_tool1 or not first_tool2:
            log("❌ Failed to detect tool execution in one or both sessions", "ERROR")
            return False

        time_delta = abs(first_tool1["time"] - first_tool2["time"])
        log(f"First tool execution time delta: {time_delta:.2f}s", "INFO")

        # If delta is > 30 seconds, sessions likely ran sequentially
        if time_delta > 30:
            log(f"❌ FAILURE: Sessions appear to run SEQUENTIALLY (delta: {time_delta:.1f}s)", "ERROR")
            log("   Second session likely waited for first to complete.", "ERROR")
            return False
        else:
            log(f"✅ SUCCESS: Sessions ran IN PARALLEL (delta: {time_delta:.1f}s)", "SUCCESS")

        # Test 5: Verify both sessions completed
        log("\n[TEST 5] Verifying task completion...", "INFO")

        done1 = any(e["type"] == "done" for e in events1)
        done2 = any(e["type"] == "done" for e in events2)

        if done1 and done2:
            log("✅ Both tasks completed successfully!", "SUCCESS")
        else:
            log(f"⚠️  Task completion status: Session1={done1}, Session2={done2}", "WARN")

        # Test 6: Verify displays are isolated
        log("\n[TEST 6] Verifying display isolation...", "INFO")

        # Check that each session used computer tools with their own displays
        computer_uses1 = [e for e in events1 if e["type"] == "tool_use" and e["data"].get("name") == "computer"]
        computer_uses2 = [e for e in events2 if e["type"] == "tool_use" and e["data"].get("name") == "computer"]

        log(f"Session 1 used computer tool {len(computer_uses1)} times", "INFO")
        log(f"Session 2 used computer tool {len(computer_uses2)} times", "INFO")

        if computer_uses1 and computer_uses2:
            log("✅ Both sessions utilized computer tools (likely for Firefox)", "SUCCESS")

        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"✅ Display isolation: PASS")
        print(f"✅ Concurrent execution: {'PASS' if time_delta < 30 else 'FAIL'}")
        print(f"✅ Both tasks completed: {'PASS' if done1 and done2 else 'PARTIAL'}")
        print(f"✅ Tool execution: PASS")
        print("="*70 + "\n")

        return time_delta < 30 and done1 and done2


async def main():
    """Entry point."""
    try:
        success = await test_concurrent_sessions()
        if success:
            log("\n🎉 ALL TESTS PASSED! System handles concurrent sessions correctly.", "SUCCESS")
            sys.exit(0)
        else:
            log("\n❌ TESTS FAILED! System does not meet concurrency requirements.", "ERROR")
            sys.exit(1)
    except Exception as e:
        log(f"\n💥 Test crashed with error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║     CONCURRENT SESSION VERIFICATION TEST                     ║
║                                                              ║
║  This test verifies that the system handles multiple        ║
║  agent sessions in TRUE PARALLEL (not sequential queuing).  ║
║                                                              ║
║  Requirements:                                               ║
║  - API server must be running on localhost:8000             ║
║  - ANTHROPIC_API_KEY or GEMINI_API_KEY must be set         ║
║                                                              ║
║  The test will:                                             ║
║  1. Create two sessions with isolated displays              ║
║  2. Send concurrent requests                                ║
║  3. Verify parallel execution (time delta < 30s)            ║
║  4. Monitor SSE streams for both sessions                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(main())
