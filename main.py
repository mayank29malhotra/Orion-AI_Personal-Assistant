#!/usr/bin/env python3
"""
Orion AI Personal Assistant - Main Entry Point
Production-ready entry point for all access channels.

Usage:
    python main.py                  # Start Telegram bot (default)
    python main.py telegram         # Start Telegram bot
    python main.py gradio           # Start Gradio web UI
    python main.py scheduler        # Start scheduler service
    python main.py test             # Run setup tests
"""

import os
import sys
import asyncio
import argparse

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="Orion AI Personal Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    Start Telegram bot (default)
  python main.py telegram           Start Telegram bot  
  python main.py gradio             Start Gradio web UI
  python main.py scheduler          Start scheduler service
  python main.py test               Run setup verification
        """
    )
    
    parser.add_argument(
        "mode",
        nargs="?",
        default="telegram",
        choices=["telegram", "gradio", "scheduler", "test", "info"],
        help="Run mode (default: telegram)"
    )
    
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--set-webhook", help="Set Telegram webhook URL")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Set debug mode if requested
    if args.debug:
        os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Import core after path setup
    from core.config import Config
    from core.utils import logger
    
    # Ensure directories exist
    Config.ensure_directories()
    
    # Run requested mode
    if args.mode == "telegram":
        run_telegram(args)
    elif args.mode == "gradio":
        run_gradio(args)
    elif args.mode == "scheduler":
        run_scheduler()
    elif args.mode == "test":
        run_tests()
    elif args.mode == "info":
        show_info()


def run_telegram(args):
    """Start Telegram bot server with Email bot and Scheduler in background."""
    import threading
    from integrations.telegram import start_telegram_server, set_webhook
    
    if args.set_webhook:
        asyncio.run(set_webhook(args.set_webhook))
        return
    
    # Start Email bot in background thread
    email_address = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_PASSWORD")
    if email_address and email_password:
        def _run_email_bot():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                from integrations.email_bot import email_bot_loop
                loop.run_until_complete(email_bot_loop())
            except Exception as e:
                print(f"❌ Email bot error: {e}")
        
        email_thread = threading.Thread(target=_run_email_bot, daemon=True)
        email_thread.start()
        print("📬 Email bot started in background")
    else:
        print("⚠️ Email bot not configured (EMAIL_ADDRESS/EMAIL_PASSWORD missing)")
    
    # Start Scheduler in background thread
    def _run_scheduler():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from integrations.scheduler import start_scheduler_loop
            loop.run_until_complete(start_scheduler_loop())
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
    
    scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
    scheduler_thread.start()
    print("⏰ Scheduler started in background")
    
    # Start Telegram server (blocking)
    start_telegram_server(args.host, args.port)


def run_gradio(args):
    """Start Gradio web UI."""
    from integrations.gradio_ui import create_gradio_ui
    
    print(f"🚀 Starting Orion Gradio UI on {args.host}:{args.port}")
    demo = create_gradio_ui()
    demo.launch(server_name=args.host, server_port=args.port)


def run_scheduler():
    """Start scheduler service."""
    from integrations.scheduler import start_scheduler
    start_scheduler()


def run_tests():
    """Run setup verification tests."""
    print("\n🧪 Running Orion Setup Tests\n")
    print("=" * 50)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Core imports
    print("\n1️⃣ Testing core imports...")
    try:
        from core.config import Config
        from core.utils import logger
        from core.memory import memory
        print("   ✅ Core imports: PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ Core imports: FAILED - {e}")
        tests_failed += 1
    
    # Test 2: Configuration
    print("\n2️⃣ Testing configuration...")
    try:
        from core.config import Config
        errors = Config.validate()
        if errors:
            print(f"   ⚠️  Configuration warnings: {', '.join(errors)}")
        print("   ✅ Configuration: PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ Configuration: FAILED - {e}")
        tests_failed += 1
    
    # Test 3: Tools import
    print("\n3️⃣ Testing tools import...")
    try:
        from tools import get_all_tools_sync
        tools = get_all_tools_sync()
        print(f"   ✅ Tools loaded: {len(tools)} tools")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ Tools import: FAILED - {e}")
        tests_failed += 1
    
    # Test 4: Orion agent
    print("\n4️⃣ Testing Orion agent...")
    try:
        from core.agent import Orion
        orion = Orion()
        print("   ✅ Orion agent: PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ Orion agent: FAILED - {e}")
        tests_failed += 1
    
    # Test 5: Integrations
    print("\n5️⃣ Testing integrations...")
    try:
        from integrations.telegram import app as telegram_app
        from integrations.scheduler import ScheduledTask
        from integrations.email_bot import EmailBot
        print("   ✅ Integrations: PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ Integrations: FAILED - {e}")
        tests_failed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"\n📊 Test Results: {tests_passed} passed, {tests_failed} failed")
    
    if tests_failed == 0:
        print("\n✅ All tests passed! Orion is ready to use.")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
    
    return tests_failed == 0


def show_info():
    """Show system and configuration info."""
    from core.config import Config
    
    print("\n🤖 Orion AI Personal Assistant")
    print("=" * 50)
    print(Config.get_info())
    
    # Show available integrations
    print("\n📡 Available Integrations:")
    print("  • telegram  - Telegram bot")
    print("  • gradio    - Web UI (Gradio)")
    print("  • scheduler - Background task scheduler")
    print("  • email_bot - Email-based commands")
    
    print("\n📖 Run 'python main.py --help' for usage info")


if __name__ == "__main__":
    main()
