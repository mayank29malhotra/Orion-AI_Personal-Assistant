"""
Task & Note Management Tools for Orion
File-based task lists and notes with markdown support.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from langchain_core.tools.simple import Tool

logger = logging.getLogger("Orion")

# Default data directory
DATA_DIR = Path("sandbox/data")


def _ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _get_tasks_file():
    """Get path to tasks file."""
    return _ensure_data_dir() / "tasks.json"


def _get_notes_dir():
    """Get path to notes directory."""
    notes_dir = _ensure_data_dir() / "notes"
    notes_dir.mkdir(exist_ok=True)
    return notes_dir


def _load_tasks() -> list:
    """Load tasks from JSON file."""
    tasks_file = _get_tasks_file()
    if tasks_file.exists():
        try:
            with open(tasks_file, 'r') as f:
                return json.load(f)
        except:
            return []
    return []


def _save_tasks(tasks: list):
    """Save tasks to JSON file."""
    tasks_file = _get_tasks_file()
    with open(tasks_file, 'w') as f:
        json.dump(tasks, f, indent=2, default=str)


def create_task(
    title: str,
    description: str = "",
    due_date: str = None,
    priority: str = "medium"
) -> str:
    """
    Create a new task.
    
    Args:
        title: Task title
        description: Task description (optional)
        due_date: Due date in YYYY-MM-DD format (optional)
        priority: Priority level: low, medium, high (default medium)
    """
    try:
        tasks = _load_tasks()
        
        task_id = max([t.get('id', 0) for t in tasks], default=0) + 1
        
        task = {
            'id': task_id,
            'title': title,
            'description': description,
            'due_date': due_date,
            'priority': priority.lower(),
            'completed': False,
            'created_at': datetime.now().isoformat(),
            'completed_at': None
        }
        
        tasks.append(task)
        _save_tasks(tasks)
        
        logger.info(f"Task created: {title} (ID: {task_id})")
        
        priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}.get(priority.lower(), '🟡')
        due_str = f" | 📅 Due: {due_date}" if due_date else ""
        
        return f"✅ Task created!\n{priority_emoji} [{task_id}] {title}{due_str}"
    
    except Exception as e:
        error_msg = f"Failed to create task: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def list_tasks(show_completed: bool = False, priority: str = None) -> str:
    """
    List all tasks.
    
    Args:
        show_completed: Include completed tasks (default False)
        priority: Filter by priority (low, medium, high)
    """
    try:
        tasks = _load_tasks()
        
        if not tasks:
            return "📋 No tasks found. Create one with create_task!"
        
        # Filter tasks
        filtered = tasks
        if not show_completed:
            filtered = [t for t in filtered if not t.get('completed')]
        if priority:
            filtered = [t for t in filtered if t.get('priority', '').lower() == priority.lower()]
        
        if not filtered:
            return "📋 No tasks match your criteria"
        
        # Sort by priority, then due date
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        filtered.sort(key=lambda t: (
            priority_order.get(t.get('priority', 'medium'), 1),
            t.get('due_date') or '9999-99-99'
        ))
        
        result = ["📋 Your Tasks:"]
        for task in filtered:
            status = "✅" if task.get('completed') else "⬜"
            priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}.get(
                task.get('priority', 'medium'), '🟡'
            )
            due_str = f" | 📅 {task.get('due_date')}" if task.get('due_date') else ""
            
            result.append(f"{status} {priority_emoji} [{task['id']}] {task['title']}{due_str}")
            if task.get('description'):
                result.append(f"   💬 {task['description'][:50]}...")
        
        logger.info(f"Listed {len(filtered)} tasks")
        return "\n".join(result)
    
    except Exception as e:
        error_msg = f"Failed to list tasks: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def complete_task(task_id: int) -> str:
    """
    Mark a task as completed.
    
    Args:
        task_id: The task ID to complete
    """
    try:
        tasks = _load_tasks()
        
        for task in tasks:
            if task.get('id') == task_id:
                if task.get('completed'):
                    return f"ℹ️ Task [{task_id}] is already completed"
                
                task['completed'] = True
                task['completed_at'] = datetime.now().isoformat()
                _save_tasks(tasks)
                
                logger.info(f"Task completed: {task['title']} (ID: {task_id})")
                return f"✅ Task completed: [{task_id}] {task['title']}"
        
        return f"❌ Task [{task_id}] not found"
    
    except Exception as e:
        error_msg = f"Failed to complete task: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def delete_task(task_id: int) -> str:
    """
    Delete a task.
    
    Args:
        task_id: The task ID to delete
    """
    try:
        tasks = _load_tasks()
        original_len = len(tasks)
        
        tasks = [t for t in tasks if t.get('id') != task_id]
        
        if len(tasks) == original_len:
            return f"❌ Task [{task_id}] not found"
        
        _save_tasks(tasks)
        logger.info(f"Task deleted: ID {task_id}")
        return f"🗑️ Task [{task_id}] deleted"
    
    except Exception as e:
        error_msg = f"Failed to delete task: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def create_note(title: str, content: str, tags: str = "") -> str:
    """
    Create a new note.
    
    Args:
        title: Note title (will be used as filename)
        content: Note content in markdown format
        tags: Comma-separated tags (optional)
    """
    try:
        notes_dir = _get_notes_dir()
        
        # Sanitize filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_title}.md"
        filepath = notes_dir / filename
        
        # Handle duplicate names
        counter = 1
        while filepath.exists():
            filename = f"{safe_title}_{counter}.md"
            filepath = notes_dir / filename
            counter += 1
        
        # Create markdown content with frontmatter
        tags_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
        
        note_content = f"""---
title: {title}
created: {datetime.now().isoformat()}
tags: [{', '.join(tags_list)}]
---

# {title}

{content}
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        
        logger.info(f"Note created: {filename}")
        return f"📝 Note created: {filename}"
    
    except Exception as e:
        error_msg = f"Failed to create note: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def list_notes() -> str:
    """List all notes."""
    try:
        notes_dir = _get_notes_dir()
        notes = list(notes_dir.glob("*.md"))
        
        if not notes:
            return "📝 No notes found. Create one with create_note!"
        
        result = ["📝 Your Notes:"]
        for note in sorted(notes, key=lambda x: x.stat().st_mtime, reverse=True):
            mod_time = datetime.fromtimestamp(note.stat().st_mtime)
            result.append(f"  📄 {note.stem} | Modified: {mod_time.strftime('%Y-%m-%d %H:%M')}")
        
        logger.info(f"Listed {len(notes)} notes")
        return "\n".join(result)
    
    except Exception as e:
        error_msg = f"Failed to list notes: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def read_note(title: str) -> str:
    """
    Read a note by title.
    
    Args:
        title: Note title (without .md extension)
    """
    try:
        notes_dir = _get_notes_dir()
        
        # Try exact match first
        filepath = notes_dir / f"{title}.md"
        
        if not filepath.exists():
            # Try case-insensitive search
            for note in notes_dir.glob("*.md"):
                if note.stem.lower() == title.lower():
                    filepath = note
                    break
            else:
                return f"❌ Note '{title}' not found"
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"Note read: {title}")
        return content
    
    except Exception as e:
        error_msg = f"Failed to read note: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def search_notes(query: str) -> str:
    """
    Search notes by content or tags.
    
    Args:
        query: Search query
    """
    try:
        notes_dir = _get_notes_dir()
        notes = list(notes_dir.glob("*.md"))
        
        if not notes:
            return "📝 No notes found"
        
        matches = []
        query_lower = query.lower()
        
        for note in notes:
            try:
                with open(note, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                
                if query_lower in content or query_lower in note.stem.lower():
                    # Find context around match
                    idx = content.find(query_lower)
                    if idx != -1:
                        start = max(0, idx - 30)
                        end = min(len(content), idx + len(query) + 30)
                        context = content[start:end].replace('\n', ' ')
                        matches.append(f"  📄 {note.stem}\n     ...{context}...")
                    else:
                        matches.append(f"  📄 {note.stem} (title match)")
            except:
                continue
        
        if not matches:
            return f"🔍 No notes found matching '{query}'"
        
        logger.info(f"Found {len(matches)} notes matching '{query}'")
        return f"🔍 Found {len(matches)} notes:\n" + "\n".join(matches)
    
    except Exception as e:
        error_msg = f"Failed to search notes: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def delete_note(title: str) -> str:
    """
    Delete a note by title.
    
    Args:
        title: Note title (without .md extension)
    """
    try:
        notes_dir = _get_notes_dir()
        filepath = notes_dir / f"{title}.md"
        
        if not filepath.exists():
            # Try case-insensitive
            for note in notes_dir.glob("*.md"):
                if note.stem.lower() == title.lower():
                    filepath = note
                    break
            else:
                return f"❌ Note '{title}' not found"
        
        filepath.unlink()
        logger.info(f"Note deleted: {title}")
        return f"🗑️ Note '{title}' deleted"
    
    except Exception as e:
        error_msg = f"Failed to delete note: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def get_task_tools():
    """Get all task-related tools."""
    return [
        Tool(
            name="create_task",
            func=create_task,
            description="Create a new task. Args: title, description (optional), due_date (YYYY-MM-DD, optional), priority (low/medium/high)"
        ),
        Tool(
            name="list_tasks",
            func=list_tasks,
            description="List all tasks. Args: show_completed (True/False), priority (low/medium/high filter)"
        ),
        Tool(
            name="complete_task",
            func=complete_task,
            description="Mark a task as completed. Args: task_id (integer)"
        ),
        Tool(
            name="delete_task",
            func=delete_task,
            description="Delete a task. Args: task_id (integer)"
        ),
    ]


def get_note_tools():
    """Get all note-related tools."""
    return [
        Tool(
            name="create_note",
            func=create_note,
            description="Create a new markdown note. Args: title, content, tags (comma-separated, optional)"
        ),
        Tool(
            name="list_notes",
            func=list_notes,
            description="List all notes"
        ),
        Tool(
            name="read_note",
            func=read_note,
            description="Read a note by title. Args: title (without .md extension)"
        ),
        Tool(
            name="search_notes",
            func=search_notes,
            description="Search notes by content or tags. Args: query"
        ),
        Tool(
            name="delete_note",
            func=delete_note,
            description="Delete a note. Args: title (without .md extension)"
        ),
    ]
