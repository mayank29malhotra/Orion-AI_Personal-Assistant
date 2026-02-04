"""
Scheduled Tasks / Cron-like Automation for Orion
FREE - Run tasks automatically at specified times

Features:
- Schedule recurring tasks (daily, weekly, etc.)
- One-time scheduled tasks
- Natural language scheduling
- Task persistence (survives restarts)
- Self-ping keep-alive for HuggingFace Spaces

Examples:
- "Every day at 9am: Check my emails and summarize"
- "Every Monday: Create weekly task list"
- "At 5pm: Remind me to take a break"
"""
import os
import json
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3

# Add parent directory for core imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config
from core.agent import Orion
from core.utils import Logger

logger = Logger().logger

# Database path - use sandbox directory for persistence
DATA_DIR = os.getenv("ORION_DATA_DIR", os.getcwd())
SCHEDULER_DB = os.path.join(DATA_DIR, "sandbox", "data", "scheduled_tasks.db")

# HuggingFace Space URL (for self-ping)
HF_SPACE_URL = os.getenv("HF_SPACE_URL", "")  # e.g., https://username-orion.hf.space
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "300"))  # 5 minutes default

# Global Orion instance
orion_instance: Optional[Orion] = None


class Frequency(Enum):
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class ScheduledTask:
    id: int
    name: str
    command: str
    frequency: str
    hour: int  # 0-23
    minute: int  # 0-59
    day_of_week: Optional[int]  # 0-6 (Monday-Sunday) for weekly
    day_of_month: Optional[int]  # 1-31 for monthly
    enabled: bool
    last_run: Optional[str]
    next_run: Optional[str]
    created_at: str


def init_database():
    """Initialize the scheduler database"""
    conn = sqlite3.connect(SCHEDULER_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            frequency TEXT NOT NULL,
            hour INTEGER DEFAULT 9,
            minute INTEGER DEFAULT 0,
            day_of_week INTEGER,
            day_of_month INTEGER,
            enabled BOOLEAN DEFAULT 1,
            last_run TEXT,
            next_run TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            run_at TEXT,
            status TEXT,
            result TEXT,
            FOREIGN KEY (task_id) REFERENCES scheduled_tasks(id)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Scheduler database initialized")


async def get_orion() -> Orion:
    """Get or create Orion instance"""
    global orion_instance
    if orion_instance is None:
        orion_instance = Orion()
        await orion_instance.setup()
        logger.info("Scheduler: Orion initialized")
    return orion_instance


def add_task(name: str, command: str, frequency: str, hour: int = 9, minute: int = 0,
             day_of_week: int = None, day_of_month: int = None) -> int:
    """Add a new scheduled task"""
    conn = sqlite3.connect(SCHEDULER_DB)
    cursor = conn.cursor()
    
    now = datetime.now()
    next_run = calculate_next_run(frequency, hour, minute, day_of_week, day_of_month)
    
    cursor.execute('''
        INSERT INTO scheduled_tasks 
        (name, command, frequency, hour, minute, day_of_week, day_of_month, enabled, next_run, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    ''', (name, command, frequency, hour, minute, day_of_week, day_of_month, 
          next_run.isoformat(), now.isoformat()))
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Task added: {name} (ID: {task_id})")
    return task_id


def calculate_next_run(frequency: str, hour: int, minute: int, 
                       day_of_week: int = None, day_of_month: int = None) -> datetime:
    """Calculate the next run time for a task"""
    now = datetime.now()
    today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if frequency == Frequency.ONCE.value:
        return today if today > now else today + timedelta(days=1)
    
    elif frequency == Frequency.HOURLY.value:
        next_run = now.replace(minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(hours=1)
        return next_run
    
    elif frequency == Frequency.DAILY.value:
        return today if today > now else today + timedelta(days=1)
    
    elif frequency == Frequency.WEEKLY.value:
        days_ahead = day_of_week - now.weekday()
        if days_ahead < 0 or (days_ahead == 0 and today <= now):
            days_ahead += 7
        return today + timedelta(days=days_ahead)
    
    elif frequency == Frequency.MONTHLY.value:
        target = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            # Move to next month
            if now.month == 12:
                target = target.replace(year=now.year + 1, month=1)
            else:
                target = target.replace(month=now.month + 1)
        return target
    
    return today


def get_all_tasks() -> List[Dict[str, Any]]:
    """Get all scheduled tasks"""
    conn = sqlite3.connect(SCHEDULER_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM scheduled_tasks WHERE enabled = 1')
    rows = cursor.fetchall()
    conn.close()
    
    tasks = []
    for row in rows:
        tasks.append({
            'id': row[0],
            'name': row[1],
            'command': row[2],
            'frequency': row[3],
            'hour': row[4],
            'minute': row[5],
            'day_of_week': row[6],
            'day_of_month': row[7],
            'enabled': row[8],
            'last_run': row[9],
            'next_run': row[10],
            'created_at': row[11]
        })
    return tasks


def get_due_tasks() -> List[Dict[str, Any]]:
    """Get tasks that are due to run"""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(SCHEDULER_DB)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM scheduled_tasks 
        WHERE enabled = 1 AND next_run <= ?
    ''', (now,))
    rows = cursor.fetchall()
    conn.close()
    
    tasks = []
    for row in rows:
        tasks.append({
            'id': row[0],
            'name': row[1],
            'command': row[2],
            'frequency': row[3],
            'hour': row[4],
            'minute': row[5],
            'day_of_week': row[6],
            'day_of_month': row[7]
        })
    return tasks


def update_task_after_run(task_id: int, task: Dict[str, Any], result: str, status: str):
    """Update task after it runs"""
    conn = sqlite3.connect(SCHEDULER_DB)
    cursor = conn.cursor()
    
    now = datetime.now()
    
    # Calculate next run
    if task['frequency'] == Frequency.ONCE.value:
        # Disable one-time tasks after running
        cursor.execute('UPDATE scheduled_tasks SET enabled = 0, last_run = ? WHERE id = ?',
                      (now.isoformat(), task_id))
    else:
        next_run = calculate_next_run(
            task['frequency'], task['hour'], task['minute'],
            task['day_of_week'], task['day_of_month']
        )
        cursor.execute('''
            UPDATE scheduled_tasks 
            SET last_run = ?, next_run = ?
            WHERE id = ?
        ''', (now.isoformat(), next_run.isoformat(), task_id))
    
    # Log to history
    cursor.execute('''
        INSERT INTO task_history (task_id, run_at, status, result)
        VALUES (?, ?, ?, ?)
    ''', (task_id, now.isoformat(), status, result[:1000] if result else None))
    
    conn.commit()
    conn.close()


async def run_task(task: Dict[str, Any]):
    """Execute a scheduled task"""
    logger.info(f"Running scheduled task: {task['name']}")
    
    try:
        orion = await get_orion()
        results = await orion.run_superstep(task['command'], success_criteria="", history=[])
        
        if results and len(results) > 0:
            result = results[-1][1] if len(results[-1]) > 1 else "Task completed"
        else:
            result = "Task completed successfully"
        
        update_task_after_run(task['id'], task, result, "success")
        logger.info(f"Task completed: {task['name']}")
        
    except Exception as e:
        logger.error(f"Task failed: {task['name']} - {e}")
        update_task_after_run(task['id'], task, str(e), "failed")


async def scheduler_loop():
    """Main scheduler loop - checks for due tasks every minute"""
    logger.info("Scheduler started")
    
    while True:
        try:
            due_tasks = get_due_tasks()
            
            for task in due_tasks:
                await run_task(task)
            
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        
        # Check every minute
        await asyncio.sleep(60)


async def keep_alive_ping():
    """
    Self-ping to keep HuggingFace Space alive.
    Pings the Space URL every KEEP_ALIVE_INTERVAL seconds.
    """
    if not HF_SPACE_URL:
        logger.info("Keep-alive disabled: HF_SPACE_URL not set")
        return
    
    logger.info(f"Keep-alive enabled: pinging {HF_SPACE_URL} every {KEEP_ALIVE_INTERVAL}s")
    
    while True:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(HF_SPACE_URL)
                if response.status_code == 200:
                    logger.debug(f"Keep-alive ping successful: {HF_SPACE_URL}")
                else:
                    logger.warning(f"Keep-alive ping returned {response.status_code}")
        except Exception as e:
            logger.error(f"Keep-alive ping failed: {e}")
        
        await asyncio.sleep(KEEP_ALIVE_INTERVAL)


async def process_pending_requests():
    """
    Check and process pending requests when bot is online.
    Runs every minute alongside the scheduler.
    """
    try:
        from core.memory import pending_queue, process_pending_queue
        
        # Check if there are pending requests
        pending_count = pending_queue.get_pending_count()
        
        if pending_count > 0:
            logger.info(f"Found {pending_count} pending requests, processing...")
            orion = await get_orion()
            pending_queue.set_bot_status("online")
            await process_pending_queue(orion)
    except Exception as e:
        logger.error(f"Error processing pending requests: {e}")


async def start_scheduler_loop():
    """Start scheduler loop with keep-alive and pending request processing - for use in app_both.py"""
    init_database()
    
    # Mark bot as online
    try:
        from core.memory import pending_queue
        pending_queue.set_bot_status("online")
    except Exception as e:
        logger.warning(f"Could not update bot status: {e}")
    
    # Start all background tasks concurrently
    tasks = [
        asyncio.create_task(scheduler_loop()),
        asyncio.create_task(keep_alive_ping()),
    ]
    
    # Also run pending request processor once at startup
    await process_pending_requests()
    
    # Wait for all tasks (they run forever)
    await asyncio.gather(*tasks)


def list_tasks():
    """Print all scheduled tasks"""
    tasks = get_all_tasks()
    
    if not tasks:
        print("No scheduled tasks")
        return
    
    print("\n📅 Scheduled Tasks")
    print("=" * 60)
    
    for task in tasks:
        print(f"\nID: {task['id']}")
        print(f"  Name: {task['name']}")
        print(f"  Command: {task['command'][:50]}...")
        print(f"  Frequency: {task['frequency']}")
        print(f"  Time: {task['hour']:02d}:{task['minute']:02d}")
        print(f"  Next Run: {task['next_run']}")
        print(f"  Last Run: {task['last_run'] or 'Never'}")


def delete_task(task_id: int):
    """Delete a scheduled task"""
    conn = sqlite3.connect(SCHEDULER_DB)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM scheduled_tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    logger.info(f"Task {task_id} deleted")


def start_scheduler():
    """Start the scheduler"""
    init_database()
    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Orion Task Scheduler")
    parser.add_argument("--list", action="store_true", help="List all tasks")
    parser.add_argument("--add", nargs=4, metavar=("NAME", "COMMAND", "FREQUENCY", "TIME"),
                       help="Add a task (TIME format: HH:MM)")
    parser.add_argument("--delete", type=int, help="Delete a task by ID")
    parser.add_argument("--run", action="store_true", help="Start the scheduler")
    
    args = parser.parse_args()
    
    init_database()
    
    if args.list:
        list_tasks()
    elif args.add:
        name, command, frequency, time_str = args.add
        hour, minute = map(int, time_str.split(":"))
        task_id = add_task(name, command, frequency, hour, minute)
        print(f"Task added with ID: {task_id}")
    elif args.delete:
        delete_task(args.delete)
        print(f"Task {args.delete} deleted")
    elif args.run:
        start_scheduler()
    else:
        parser.print_help()
