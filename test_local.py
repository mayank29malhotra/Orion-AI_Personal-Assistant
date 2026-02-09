#!/usr/bin/env python3
"""
Orion AI Assistant - Local CLI Tester
Test Orion capabilities directly from the terminal without Telegram.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Disable verbose HTTP logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment
from dotenv import load_dotenv
load_dotenv()


async def test_single_task(orion, task: str, test_num: int = 0) -> dict:
    """Test a single task and return results."""
    print(f"\n{'='*60}")
    print(f"TEST {test_num}: {task[:80]}...")
    print(f"{'='*60}")
    
    start_time = datetime.now()
    
    try:
        # Process the task using run_superstep (Orion's actual API)
        results = await orion.run_superstep(
            task,
            success_criteria="",
            history=[],
            user_id="local_test",
            channel="cli"
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Extract the final response from results
        if results and len(results) > 0:
            final_response = results[-1][1] if len(results[-1]) > 1 else "Task completed"
            success = True
        else:
            final_response = "No response received"
            success = False
        
        print(f"\n--- RESULT ---")
        print(f"Status: {'PASS' if success else 'FAIL'}")
        print(f"Time: {elapsed:.2f}s")
        response_str = str(final_response)
        print(f"Response: {response_str[:500]}..." if len(response_str) > 500 else f"Response: {response_str}")
        
        return {
            "test_num": test_num,
            "task": task,
            "status": "PASS" if success else "FAIL",
            "response": final_response,
            "elapsed": elapsed,
            "error": None
        }
        
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n--- ERROR ---")
        print(f"Status: ERROR")
        print(f"Time: {elapsed:.2f}s")
        print(f"Error: {str(e)}")
        
        return {
            "test_num": test_num,
            "task": task,
            "status": "ERROR",
            "response": None,
            "elapsed": elapsed,
            "error": str(e)
        }


async def run_tests(tasks: list, delay_between: int = 5):
    """Run multiple tests with delay between them."""
    from core.agent import Orion
    
    print("\n" + "="*60)
    print("ORION LOCAL TEST RUNNER")
    print("="*60)
    
    # Initialize Orion
    print("\nInitializing Orion...")
    orion = Orion()
    await orion.setup()
    print(f"Orion ready with {len(orion.tools)} tools")
    print(f"Worker Model: {os.getenv('WORKER_MODEL', 'default')}")
    print(f"Evaluator Model: {os.getenv('EVALUATOR_MODEL', 'default')}")
    
    results = []
    
    for i, task in enumerate(tasks, 1):
        result = await test_single_task(orion, task, i)
        results.append(result)
        
        # Delay between tests (rate limiting)
        if i < len(tasks):
            print(f"\n--- Waiting {delay_between}s before next test (rate limiting)... ---")
            await asyncio.sleep(delay_between)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    
    print(f"\nTotal: {len(results)} | PASS: {passed} | FAIL: {failed} | ERROR: {errors}")
    print(f"Success Rate: {passed/len(results)*100:.1f}%")
    
    print("\n--- DETAILED RESULTS ---")
    for r in results:
        status_icon = "✓" if r["status"] == "PASS" else "✗" if r["status"] == "FAIL" else "!"
        print(f"[{status_icon}] Test {r['test_num']}: {r['status']} ({r['elapsed']:.1f}s) - {r['task'][:50]}...")
        if r["error"]:
            print(f"    Error: {r['error'][:100]}")
    
    return results


async def interactive_mode():
    """Interactive testing mode - type tasks and see results."""
    from core.agent import Orion
    
    print("\n" + "="*60)
    print("ORION INTERACTIVE TEST MODE")
    print("Type your tasks and press Enter. Type 'quit' to exit.")
    print("="*60)
    
    print("\nInitializing Orion...")
    orion = Orion()
    await orion.setup()
    print(f"Orion ready with {len(orion.tools)} tools")
    print(f"Worker Model: {os.getenv('WORKER_MODEL', 'default')}")
    print(f"Evaluator Model: {os.getenv('EVALUATOR_MODEL', 'default')}")
    
    test_num = 0
    while True:
        print("\n" + "-"*40)
        try:
            task = input("Enter task (or 'quit'): ").strip()
        except EOFError:
            break
        
        if task.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        if not task:
            continue
        
        test_num += 1
        await test_single_task(orion, task, test_num)


# Pre-defined test tasks
TEST_TASKS = [
    # Basic Tests (1-5)
    "What is the capital of Japan?",
    "Create a note called test_note with content: This is a test note created by Orion",
    "Search YouTube for Python programming tutorials",
    "Search GitHub for langchain repositories", 
    "What's the current time?",
    
    # Medium Tests (6-15)
    "Create a task: Buy groceries tomorrow with priority high",
    "Search Google for latest AI news",
    "What is 25 * 47?",
    "List all my notes",
    "List all my tasks",
    "Define the word 'serendipity'",
    "Search for flights from Delhi to Mumbai",
    "What's the weather like today?",
    "Tell me a joke",
    "Summarize the Wikipedia page about Python programming",
    
    # Complex Tests (16-20)
    "Create a task called 'Meeting prep' with description 'Prepare slides for Monday meeting' and priority high",
    "Search GitHub for Python AI projects with more than 1000 stars",
    "Find YouTube videos about machine learning for beginners",
    "Create a note with today's date as title and list 3 productivity tips",
    "What are the top trending topics on GitHub?",
]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Orion Local Test Runner")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--task", "-t", type=str, help="Run a single task")
    parser.add_argument("--all", "-a", action="store_true", help="Run all predefined tests")
    parser.add_argument("--quick", "-q", action="store_true", help="Run first 5 basic tests")
    parser.add_argument("--delay", "-d", type=int, default=5, help="Delay between tests in seconds")
    
    args = parser.parse_args()
    
    if args.interactive:
        asyncio.run(interactive_mode())
    elif args.task:
        asyncio.run(run_tests([args.task], args.delay))
    elif args.all:
        asyncio.run(run_tests(TEST_TASKS, args.delay))
    elif args.quick:
        asyncio.run(run_tests(TEST_TASKS[:5], args.delay))
    else:
        # Default: interactive mode
        print("Usage:")
        print("  python test_local.py -i          # Interactive mode")
        print("  python test_local.py -t 'task'   # Run single task")
        print("  python test_local.py -q          # Run 5 quick tests")
        print("  python test_local.py -a          # Run all 20 tests")
        print("  python test_local.py -d 10       # Set delay between tests")
        print("\nStarting interactive mode...\n")
        asyncio.run(interactive_mode())
