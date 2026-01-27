"""
Orion Multi-Channel Launcher
Start all or specific integrations from one place
"""
import os
import sys
import argparse
import asyncio
from multiprocessing import Process
from typing import List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def start_telegram():
    """Start Telegram bot"""
    from integrations.telegram import main as telegram_main
    import asyncio
    asyncio.run(telegram_main())


def start_email_bot():
    """Start Email bot"""
    from integrations.email_bot import start_email_bot
    start_email_bot()


def start_scheduler():
    """Start Task Scheduler"""
    from integrations.scheduler import start_scheduler
    start_scheduler()


def start_gradio():
    """Start Gradio web UI"""
    from integrations.gradio_ui import main
    main()


INTEGRATIONS = {
    "telegram": {
        "func": start_telegram,
        "desc": "Telegram Bot (messaging from anywhere)",
        "port": 8000,
        "env": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_ID"]
    },
    "email": {
        "func": start_email_bot,
        "desc": "Email Bot (send commands via email)",
        "port": None,
        "env": ["EMAIL_ADDRESS", "EMAIL_PASSWORD"]
    },
    "scheduler": {
        "func": start_scheduler,
        "desc": "Task Scheduler (automated recurring tasks)",
        "port": None,
        "env": []
    },
    "gradio": {
        "func": start_gradio,
        "desc": "Web UI (Gradio interface)",
        "port": 7860,
        "env": []
    }
}


def check_env_vars(integration: str) -> bool:
    """Check if required environment variables are set"""
    required = INTEGRATIONS[integration]["env"]
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        print(f"⚠️  Missing environment variables for {integration}:")
        for var in missing:
            print(f"   - {var}")
        return False
    return True


def show_status():
    """Show status of all integrations"""
    print("\n" + "=" * 60)
    print("🤖 ORION AI - Integration Status")
    print("=" * 60 + "\n")
    
    for name, info in INTEGRATIONS.items():
        env_ok = check_env_vars(name) if info["env"] else True
        status = "✅ Ready" if env_ok else "❌ Missing config"
        port_info = f" (port {info['port']})" if info['port'] else ""
        
        print(f"  {name.upper():12} - {info['desc']}")
        print(f"               Status: {status}{port_info}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Orion Multi-Channel Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launcher.py telegram           # Start Telegram bot only
  python launcher.py api telegram       # Start API + Telegram
  python launcher.py --all              # Start all integrations
  python launcher.py --status           # Show configuration status
        """
    )
    
    parser.add_argument("integrations", nargs="*", 
                       help="Integrations to start: " + ", ".join(INTEGRATIONS.keys()))
    parser.add_argument("--all", action="store_true",
                       help="Start all integrations")
    parser.add_argument("--status", action="store_true",
                       help="Show integration status")
    parser.add_argument("--list", action="store_true",
                       help="List available integrations")
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
        return
    
    if args.list:
        print("\nAvailable integrations:")
        for name, info in INTEGRATIONS.items():
            print(f"  {name:12} - {info['desc']}")
        return
    
    # Determine which integrations to start
    to_start: List[str] = []
    
    if args.all:
        to_start = list(INTEGRATIONS.keys())
    elif args.integrations:
        for name in args.integrations:
            if name.lower() in INTEGRATIONS:
                to_start.append(name.lower())
            else:
                print(f"Unknown integration: {name}")
                print(f"Available: {', '.join(INTEGRATIONS.keys())}")
                return
    else:
        parser.print_help()
        return
    
    if not to_start:
        print("No integrations specified")
        return
    
    # Check environment variables
    print("\n🔍 Checking configuration...")
    all_ok = True
    for name in to_start:
        if not check_env_vars(name):
            all_ok = False
    
    if not all_ok:
        print("\n⚠️  Some integrations have missing configuration.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return
    
    # Start integrations
    print(f"\n🚀 Starting integrations: {', '.join(to_start)}")
    print("=" * 50)
    
    if len(to_start) == 1:
        # Single integration - run directly
        name = to_start[0]
        print(f"Starting {name}...")
        INTEGRATIONS[name]["func"]()
    else:
        # Multiple integrations - use multiprocessing
        processes = []
        for name in to_start:
            print(f"Starting {name}...")
            p = Process(target=INTEGRATIONS[name]["func"], name=name)
            p.start()
            processes.append(p)
        
        print(f"\n✅ Started {len(processes)} integrations")
        print("Press Ctrl+C to stop all\n")
        
        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            print("\nStopping all integrations...")
            for p in processes:
                p.terminate()
            print("Goodbye! 👋")


if __name__ == "__main__":
    main()
