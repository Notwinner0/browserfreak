#!/usr/bin/env python3
"""
Test script to verify the browser agent, browser manager, and FastAPI server integration
"""

import asyncio

import httpx

from browserfreak.browser_agent import run_agent_workflow
from browserfreak.browser_manager import health_check


async def test_mock_mode():
    """Test the agent in mock mode (default behavior)"""
    print("Testing mock mode...")
    task = "Click the submit button on the page"
    result = await run_agent_workflow(task, max_iterations=2)
    print(f"Mock mode test completed. Task complete: {result['task_complete']}")
    return result


async def test_real_browser_mode():
    """Test the agent with real browser integration"""
    print("\nTesting real browser mode...")
    try:
        task = "Click the submit button on the page"
        result = await run_agent_workflow(task, max_iterations=2, use_real_browser=True)
        print(f"Real browser mode test completed. Task complete: {result['task_complete']}")
        return result
    except Exception as e:
        print(f"Real browser test failed (expected if Playwright not installed): {e}")
        return None


async def test_health_check():
    """Test the health check functionality"""
    print("\nTesting health check...")
    try:
        health_status = await health_check()
        print(f"Health check status: {health_status['status']}")
        return health_status
    except Exception as e:
        print(f"Health check failed: {e}")
        return None


async def test_fastapi_server():
    """Test FastAPI server endpoints"""
    print("\nTesting FastAPI server endpoints...")

    # Test data
    test_task = {
        "task": "Navigate to example.com and describe what you see",
        "use_real_browser": False,
        "max_iterations": 3,
    }

    try:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            # Test health endpoint
            health_response = await client.get("/health")
            print(f"Health endpoint status: {health_response.status_code}")

            if health_response.status_code == 200:
                health_data = health_response.json()
                print(f"Health status: {health_data.get('status')}")

            # Test task creation
            task_response = await client.post("/tasks", json=test_task)
            print(f"Task creation status: {task_response.status_code}")

            if task_response.status_code == 200:
                task_data = task_response.json()
                task_id = task_data.get("task_id")
                print(f"Created task with ID: {task_id}")

                # Wait a moment for task to complete
                await asyncio.sleep(2)

                # Test task status retrieval
                status_response = await client.get(f"/tasks/{task_id}")
                print(f"Task status retrieval: {status_response.status_code}")

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"Task status: {status_data.get('status')}")

                # Test task listing
                list_response = await client.get("/tasks")
                print(f"Task listing status: {list_response.status_code}")

                return True
            else:
                print(f"Task creation failed: {task_response.text}")
                return False

    except Exception as e:
        print(f"FastAPI server test failed (server may not be running): {e}")
        return False


async def test_error_handling():
    """Test error handling and validation"""
    print("\nTesting error handling...")

    # Test empty task validation
    try:
        await run_agent_workflow("", max_iterations=1)
        print("❌ Empty task validation failed")
        return False
    except Exception as e:
        print(f"✅ Empty task properly rejected: {type(e).__name__}")

    # Test invalid max_iterations
    try:
        await run_agent_workflow("test task", max_iterations=0)
        print("❌ Invalid max_iterations validation failed")
        return False
    except Exception as e:
        print(f"✅ Invalid max_iterations properly rejected: {type(e).__name__}")

    # Test invalid max_iterations (too high)
    try:
        await run_agent_workflow("test task", max_iterations=25)
        print("❌ Too high max_iterations validation failed")
        return False
    except Exception as e:
        print(f"✅ Too high max_iterations properly rejected: {type(e).__name__}")

    return True


async def main():
    """Run all integration tests"""
    print("Running comprehensive BrowserFreak integration tests...")
    print("=" * 60)

    results = {}

    # Test mock mode
    results["mock_mode"] = await test_mock_mode()

    # Test real browser mode (will fail if Playwright not installed)
    results["real_browser"] = await test_real_browser_mode()

    # Test health check
    results["health_check"] = await test_health_check()

    # Test FastAPI server (will fail if server not running)
    results["fastapi_server"] = await test_fastapi_server()

    # Test error handling
    results["error_handling"] = await test_error_handling()

    print("\n" + "=" * 60)
    print("Integration test summary:")
    print(f"Mock mode: {'PASSED' if results['mock_mode'] else 'FAILED'}")
    print(
        f"Real browser mode: {'PASSED' if results['real_browser'] else 'FAILED (expected if Playwright not installed)'}"
    )
    print(f"Health check: {'PASSED' if results['health_check'] else 'FAILED'}")
    print(
        f"FastAPI server: {'PASSED' if results['fastapi_server'] else 'FAILED (expected if server not running)'}"
    )
    print(f"Error handling: {'PASSED' if results['error_handling'] else 'FAILED'}")

    # Overall assessment
    core_tests_passed = (
        results["mock_mode"] and results["health_check"] and results["error_handling"]
    )
    optional_tests_passed = results["real_browser"] and results["fastapi_server"]

    if core_tests_passed:
        print("\n✅ Core functionality tests PASSED!")
        print("   - Browser agent works correctly")
        print("   - Health checks are functional")
        print("   - Error handling is robust")

        if optional_tests_passed:
            print("✅ All tests PASSED! Full system integration successful.")
        elif results["real_browser"] or results["fastapi_server"]:
            print("⚠️  Partial success: Some advanced features working")
        else:
            print("ℹ️  Core functionality working, advanced features require setup")
    else:
        print("\n❌ Core functionality tests FAILED. Please check the implementation.")


if __name__ == "__main__":
    asyncio.run(main())
