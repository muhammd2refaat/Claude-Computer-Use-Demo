#!/usr/bin/env python3
"""
Comprehensive Test Suite for Computer-Use Agent

This test suite verifies:
1. API functionality (health, sessions, messages)
2. Firefox automation
3. Concurrent sessions (parallel execution)
4. SSE streaming
5. VNC connection info
6. File management

Run with: python run_all_tests.py
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

API_BASE = "http://localhost:8000"

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def log(message: str, level: str = "INFO"):
    """Pretty print log messages."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    colors = {
        "INFO": Colors.CYAN,
        "SUCCESS": Colors.GREEN,
        "ERROR": Colors.RED,
        "WARN": Colors.YELLOW,
        "HEADER": Colors.HEADER,
    }
    color = colors.get(level, Colors.RESET)
    print(f"{color}{timestamp} [{level}]{Colors.RESET} {message}")


def print_header(title: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}{Colors.RESET}\n")


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests: List[Dict] = []

    def add(self, name: str, passed: bool, message: str = ""):
        self.tests.append({"name": name, "passed": passed, "message": message})
        if passed:
            self.passed += 1
            log(f"✅ PASS: {name}", "SUCCESS")
        else:
            self.failed += 1
            log(f"❌ FAIL: {name} - {message}", "ERROR")

    def summary(self):
        print_header("TEST SUMMARY")
        for test in self.tests:
            status = "✅" if test["passed"] else "❌"
            print(f"  {status} {test['name']}")
            if not test["passed"] and test["message"]:
                print(f"     └─ {test['message']}")
        print(f"\n{Colors.BOLD}Total: {self.passed + self.failed} | Passed: {self.passed} | Failed: {self.failed}{Colors.RESET}")
        return self.failed == 0


results = TestResults()


# ==================== API TESTS ====================

async def test_health_endpoint():
    """Test the health check endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE}/health")
            if resp.status_code == 200:
                data = resp.json()
                if "status" in data and "active_sessions" in data:
                    results.add("Health Endpoint", True)
                    return True
                else:
                    results.add("Health Endpoint", False, f"Invalid response: {data}")
            else:
                results.add("Health Endpoint", False, f"Status code: {resp.status_code}")
    except Exception as e:
        results.add("Health Endpoint", False, str(e))
    return False


async def test_create_session():
    """Test creating a new session."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{API_BASE}/api/sessions", json={"title": "Test Session"})
            if resp.status_code == 201:
                data = resp.json()
                if "id" in data and "vnc_info" in data:
                    results.add("Create Session", True)
                    return data
                else:
                    results.add("Create Session", False, f"Invalid response: {data}")
            else:
                results.add("Create Session", False, f"Status: {resp.status_code}")
    except Exception as e:
        results.add("Create Session", False, str(e))
    return None


async def test_list_sessions():
    """Test listing sessions."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE}/api/sessions")
            if resp.status_code == 200:
                data = resp.json()
                if "sessions" in data:
                    results.add("List Sessions", True)
                    return data["sessions"]
                else:
                    results.add("List Sessions", False, "No sessions key")
            else:
                results.add("List Sessions", False, f"Status: {resp.status_code}")
    except Exception as e:
        results.add("List Sessions", False, str(e))
    return []


async def test_vnc_info(session_id: str):
    """Test getting VNC info for a session."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE}/api/sessions/{session_id}/vnc")
            if resp.status_code == 200:
                data = resp.json()
                if "display_num" in data and "vnc_port" in data:
                    results.add("VNC Info", True)
                    return data
                else:
                    results.add("VNC Info", False, f"Invalid response: {data}")
            else:
                results.add("VNC Info", False, f"Status: {resp.status_code}")
    except Exception as e:
        results.add("VNC Info", False, str(e))
    return None


async def test_delete_session(session_id: str):
    """Test deleting a session."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(f"{API_BASE}/api/sessions/{session_id}")
            if resp.status_code in [200, 204]:
                results.add("Delete Session", True)
                return True
            else:
                results.add("Delete Session", False, f"Status: {resp.status_code}")
    except Exception as e:
        results.add("Delete Session", False, str(e))
    return False


# ==================== FIREFOX AUTOMATION TEST ====================

async def test_firefox_automation():
    """Test Firefox automation - creates a session and tests browser launch."""
    print_header("FIREFOX AUTOMATION TEST")

    session = None
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Create session
            log("Creating session for Firefox test...")
            resp = await client.post(f"{API_BASE}/api/sessions", json={"title": "Firefox Test"})
            if resp.status_code != 201:
                results.add("Firefox - Session Creation", False, f"Status: {resp.status_code}")
                return False

            session = resp.json()
            session_id = session["id"]
            display_num = session["vnc_info"]["display_num"]
            log(f"Session created: {session_id[:8]} on display :{display_num}", "SUCCESS")

            # Send Firefox task
            log("Sending Firefox automation task...")
            resp = await client.post(
                f"{API_BASE}/api/sessions/{session_id}/messages",
                json={"text": "Open Firefox browser and go to google.com. Take a screenshot when loaded."}
            )

            if resp.status_code != 202:
                results.add("Firefox - Send Message", False, f"Status: {resp.status_code}")
                return False

            results.add("Firefox - Send Message", True)

            # Monitor SSE stream
            log("Monitoring task execution...")
            tool_used = False
            task_completed = False
            firefox_launched = False

            async with client.stream("GET", f"{API_BASE}/api/sessions/{session_id}/stream") as response:
                event_type = None
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data = json.loads(line[5:].strip())

                        if event_type == "tool_use":
                            tool_used = True
                            tool_name = data.get("name", "")
                            log(f"🔧 Tool: {tool_name}", "INFO")
                            if tool_name in ["bash", "computer"]:
                                # Check if Firefox is being launched
                                input_data = data.get("input", {})
                                if "firefox" in str(input_data).lower():
                                    firefox_launched = True
                                    log("Firefox launch detected!", "SUCCESS")

                        elif event_type == "tool_result":
                            output = data.get("output", "")
                            if "firefox" in output.lower() or data.get("has_screenshot"):
                                firefox_launched = True

                        elif event_type == "done":
                            task_completed = True
                            log("Task completed!", "SUCCESS")
                            break

                        elif event_type == "error":
                            log(f"Error: {data.get('message', 'Unknown')}", "ERROR")
                            break

            results.add("Firefox - Tool Execution", tool_used)
            results.add("Firefox - Task Completion", task_completed)

            # Check files endpoint for screenshots
            resp = await client.get(f"{API_BASE}/api/sessions/{session_id}/files")
            if resp.status_code == 200:
                files = resp.json().get("files", [])
                screenshots = [f for f in files if f["name"].endswith((".png", ".jpg"))]
                results.add("Firefox - Screenshot Captured", len(screenshots) > 0)

            return task_completed

    except asyncio.TimeoutError:
        results.add("Firefox - Timeout", False, "Task timed out after 120s")
        return False
    except Exception as e:
        results.add("Firefox - Exception", False, str(e))
        return False
    finally:
        # Cleanup
        if session:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.delete(f"{API_BASE}/api/sessions/{session['id']}")
            except:
                pass


# ==================== CONCURRENT SESSIONS TEST ====================

async def test_concurrent_sessions():
    """Test that multiple sessions run in parallel (not sequentially)."""
    print_header("CONCURRENT SESSIONS TEST (CRITICAL)")

    sessions = []
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            # Create two sessions
            log("Creating two concurrent sessions...")

            session1_resp = await client.post(f"{API_BASE}/api/sessions", json={"title": "Tokyo Weather"})
            session2_resp = await client.post(f"{API_BASE}/api/sessions", json={"title": "New York Weather"})

            if session1_resp.status_code != 201 or session2_resp.status_code != 201:
                results.add("Concurrent - Create Sessions", False, "Failed to create sessions")
                return False

            session1 = session1_resp.json()
            session2 = session2_resp.json()
            sessions = [session1, session2]

            # Verify different displays
            display1 = session1["vnc_info"]["display_num"]
            display2 = session2["vnc_info"]["display_num"]

            if display1 == display2:
                results.add("Concurrent - Display Isolation", False, f"Same display: {display1}")
                return False

            results.add("Concurrent - Display Isolation", True)
            log(f"Session 1: Display :{display1}", "SUCCESS")
            log(f"Session 2: Display :{display2}", "SUCCESS")

            # Send messages simultaneously
            log("Sending concurrent tasks...")
            start_time = time.time()

            task1 = asyncio.create_task(client.post(
                f"{API_BASE}/api/sessions/{session1['id']}/messages",
                json={"text": "Search the weather in Tokyo on Google"}
            ))
            task2 = asyncio.create_task(client.post(
                f"{API_BASE}/api/sessions/{session2['id']}/messages",
                json={"text": "Search the weather in New York on Google"}
            ))

            resp1, resp2 = await asyncio.gather(task1, task2)
            send_time = time.time() - start_time

            if resp1.status_code != 202 or resp2.status_code != 202:
                results.add("Concurrent - Send Messages", False, "Failed to send messages")
                return False

            results.add("Concurrent - Send Messages", True)
            log(f"Both messages sent in {send_time:.2f}s", "SUCCESS")

            # Monitor both streams and track first tool execution time
            first_tool_time = {}

            async def monitor_stream(session_id: str, label: str):
                try:
                    async with client.stream("GET", f"{API_BASE}/api/sessions/{session_id}/stream") as response:
                        event_type = None
                        async for line in response.aiter_lines():
                            if line.startswith("event:"):
                                event_type = line[6:].strip()
                            elif line.startswith("data:"):
                                data = json.loads(line[5:].strip())

                                if event_type == "tool_use" and label not in first_tool_time:
                                    first_tool_time[label] = time.time()
                                    log(f"[{label}] First tool execution", "INFO")

                                elif event_type == "done":
                                    log(f"[{label}] Task completed", "SUCCESS")
                                    return True

                                elif event_type == "error":
                                    log(f"[{label}] Error: {data.get('message')}", "ERROR")
                                    return False
                except Exception as e:
                    log(f"[{label}] Stream error: {e}", "ERROR")
                    return False

            # Run both monitors
            log("Monitoring parallel execution...")
            monitor1 = asyncio.create_task(monitor_stream(session1['id'], "Tokyo"))
            monitor2 = asyncio.create_task(monitor_stream(session2['id'], "NewYork"))

            try:
                await asyncio.wait_for(asyncio.gather(monitor1, monitor2), timeout=180.0)
            except asyncio.TimeoutError:
                log("Monitoring timed out", "WARN")

            # Analyze timing
            if len(first_tool_time) >= 2:
                times = list(first_tool_time.values())
                time_delta = abs(times[0] - times[1])
                log(f"Time delta between first tool executions: {time_delta:.2f}s", "INFO")

                # If time delta > 30s, sessions are running sequentially
                is_parallel = time_delta < 30
                results.add("Concurrent - Parallel Execution", is_parallel,
                           f"Delta: {time_delta:.1f}s (should be < 30s)")
                return is_parallel
            else:
                results.add("Concurrent - Parallel Execution", False, "Could not measure timing")
                return False

    except Exception as e:
        results.add("Concurrent - Exception", False, str(e))
        return False
    finally:
        # Cleanup
        for session in sessions:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.delete(f"{API_BASE}/api/sessions/{session['id']}")
            except:
                pass


# ==================== UI TESTS ====================

async def test_frontend_accessible():
    """Test that the frontend is accessible."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE}/")
            if resp.status_code == 200:
                content = resp.text
                # Check for key UI elements
                has_energent = "Energent" in content or "Computer Use" in content
                has_vnc = "vnc" in content.lower()
                has_chat = "chat" in content.lower() or "message" in content.lower()

                if has_energent and has_vnc and has_chat:
                    results.add("Frontend - Accessible", True)
                    return True
                else:
                    results.add("Frontend - Accessible", False, "Missing UI elements")
            else:
                results.add("Frontend - Accessible", False, f"Status: {resp.status_code}")
    except Exception as e:
        results.add("Frontend - Accessible", False, str(e))
    return False


async def test_static_files():
    """Test that static files are served."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test CSS
            css_resp = await client.get(f"{API_BASE}/static/style.css")
            if css_resp.status_code == 200:
                results.add("Static Files - CSS", True)
            else:
                results.add("Static Files - CSS", False, f"Status: {css_resp.status_code}")

            # Test JS
            js_resp = await client.get(f"{API_BASE}/static/app.js")
            if js_resp.status_code == 200:
                results.add("Static Files - JavaScript", True)
            else:
                results.add("Static Files - JavaScript", False, f"Status: {js_resp.status_code}")

            return css_resp.status_code == 200 and js_resp.status_code == 200
    except Exception as e:
        results.add("Static Files", False, str(e))
    return False


# ==================== MAIN TEST RUNNER ====================

async def run_all_tests():
    """Run all tests."""
    print(f"""
{Colors.BOLD}{Colors.HEADER}
╔══════════════════════════════════════════════════════════════════════╗
║          COMPUTER-USE AGENT - COMPREHENSIVE TEST SUITE               ║
╠══════════════════════════════════════════════════════════════════════╣
║  This suite verifies all functionality including:                    ║
║  • API endpoints (health, sessions, messages)                        ║
║  • Firefox automation                                                ║
║  • Concurrent parallel sessions (CRITICAL)                           ║
║  • Real-time SSE streaming                                           ║
║  • Frontend and static files                                         ║
╚══════════════════════════════════════════════════════════════════════╝
{Colors.RESET}
""")

    # Check if server is running
    print_header("CONNECTIVITY CHECK")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(f"{API_BASE}/health")
        log("Server is reachable", "SUCCESS")
    except:
        log("Server is not reachable at " + API_BASE, "ERROR")
        log("Please start the server with: docker-compose up", "INFO")
        return False

    # Run API tests
    print_header("API ENDPOINT TESTS")
    await test_health_endpoint()
    session = await test_create_session()
    await test_list_sessions()

    if session:
        await test_vnc_info(session["id"])
        await test_delete_session(session["id"])

    # Run UI tests
    print_header("FRONTEND TESTS")
    await test_frontend_accessible()
    await test_static_files()

    # Run Firefox automation test
    await test_firefox_automation()

    # Run concurrent sessions test (CRITICAL)
    await test_concurrent_sessions()

    # Print summary
    success = results.summary()

    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.RESET}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ SOME TESTS FAILED{Colors.RESET}\n")

    return success


def main():
    """Entry point."""
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest suite crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
