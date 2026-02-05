"""
System Agent for Orion
======================

Specialized sub-agent for file operations, screenshots, and system tasks.

Capabilities:
- Screenshot capture
- Push notifications
- File read/write operations
- Directory listing
- System information
"""

from typing import List, Optional
from langchain_core.tools import tool, BaseTool
import os
import platform

from agents.base_agent import BaseSubAgent


class SystemAgent(BaseSubAgent):
    """
    System Agent - handles file operations, screenshots, and system tasks.
    
    This agent specializes in:
    - Taking screenshots
    - Sending push notifications
    - File read/write operations
    - Directory listing and navigation
    - System information retrieval
    """
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        if tools is None:
            tools = get_system_agent_tools()
        super().__init__(tools)
    
    def get_system_prompt(self) -> str:
        return """You are the System Agent, a specialized sub-agent of Orion AI.
Your expertise is in system operations, file management, and desktop interactions.

🎯 YOUR CAPABILITIES:

📸 SCREENSHOTS:
- Capture full screen
- Capture specific regions
- Save to custom paths
- Automatic timestamping

🔔 NOTIFICATIONS:
- Send desktop push notifications
- Alert for important events
- Configurable timeout

📁 FILE OPERATIONS:
- Read file contents
- Write/create files
- List directory contents
- Check file existence
- Get file metadata

💻 SYSTEM INFO:
- Get OS information
- Check disk space
- Memory usage
- CPU information
- Network status

🛡️ SECURITY:
- Only access sandbox directories by default
- Validate file paths
- Prevent access to sensitive system files

🔧 AVAILABLE TOOLS:
- take_screenshot: Capture screen
- send_push_notification: Desktop alerts
- read_file: Read file contents
- write_file: Write to files
- list_directory: List folder contents
- get_system_info: System details

⚠️ BEST PRACTICES:
- Always use absolute paths when possible
- Create directories before writing files
- Handle large files with care
- Backup before overwriting
- Validate file types before processing
"""

    def get_capabilities(self) -> List[str]:
        return [
            "Take full screen screenshots",
            "Capture specific screen regions",
            "Send desktop push notifications",
            "Read file contents",
            "Write and create files",
            "List directory contents",
            "Get system information",
            "Check disk space",
            "File existence checks",
            "Path operations"
        ]


def get_system_agent_tools() -> List[BaseTool]:
    """Get all tools for the System Agent."""
    tools = []
    
    try:
        from tools.utils import (
            take_screenshot,
            send_push_notification,
            read_file,
            write_file,
            list_directory,
            get_system_info
        )
        tools.extend([
            take_screenshot,
            send_push_notification,
            read_file,
            write_file,
            list_directory,
            get_system_info,
        ])
    except ImportError:
        pass
    
    return tools


# Additional system tools
@tool
def get_disk_usage(path: str = "/") -> str:
    """
    Get disk usage information for a specific path.
    
    Args:
        path: Path to check (default: root)
        
    Returns:
        Disk usage statistics
    """
    import shutil
    
    try:
        usage = shutil.disk_usage(path)
        
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        free_gb = usage.free / (1024**3)
        percent_used = (usage.used / usage.total) * 100
        
        # Status indicator
        if percent_used > 90:
            status = "🔴 CRITICAL"
        elif percent_used > 75:
            status = "🟡 WARNING"
        else:
            status = "🟢 HEALTHY"
        
        return f"""
💾 DISK USAGE: {path}
══════════════════════════════════════════

📊 Status: {status}

📁 Total:     {total_gb:.2f} GB
📦 Used:      {used_gb:.2f} GB ({percent_used:.1f}%)
📭 Free:      {free_gb:.2f} GB

{'▓' * int(percent_used / 5)}{'░' * (20 - int(percent_used / 5))} {percent_used:.1f}%

══════════════════════════════════════════
"""
    except Exception as e:
        return f"❌ Error checking disk usage: {e}"


@tool
def get_environment_info() -> str:
    """
    Get detailed environment and system information.
    
    Returns:
        System environment details
    """
    import sys
    
    info = {
        "OS": platform.system(),
        "OS Version": platform.version(),
        "Platform": platform.platform(),
        "Machine": platform.machine(),
        "Processor": platform.processor(),
        "Python Version": sys.version.split()[0],
        "Python Path": sys.executable,
        "Working Directory": os.getcwd(),
        "User": os.getenv("USER") or os.getenv("USERNAME", "Unknown"),
        "Home Directory": os.path.expanduser("~"),
    }
    
    # Format output
    output = """
💻 SYSTEM ENVIRONMENT
══════════════════════════════════════════

"""
    for key, value in info.items():
        output += f"📌 {key}: {value}\n"
    
    output += "\n══════════════════════════════════════════"
    
    return output


@tool
def find_files(
    directory: str,
    pattern: str = "*",
    recursive: bool = True
) -> str:
    """
    Find files matching a pattern in a directory.
    
    Args:
        directory: Directory to search
        pattern: File pattern (e.g., "*.py", "*.txt")
        recursive: Search subdirectories (default: True)
        
    Returns:
        List of matching files
    """
    from pathlib import Path
    
    try:
        path = Path(directory)
        if not path.exists():
            return f"❌ Directory not found: {directory}"
        
        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))
        
        if not files:
            return f"📂 No files matching '{pattern}' found in {directory}"
        
        # Sort by modification time (newest first)
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        output = f"""
🔍 FILES FOUND: {pattern}
══════════════════════════════════════════
📁 Directory: {directory}
📊 Count: {len(files)}

"""
        
        for f in files[:50]:  # Limit to 50 files
            size = f.stat().st_size
            if size > 1024*1024:
                size_str = f"{size/(1024*1024):.1f} MB"
            elif size > 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size} B"
            
            output += f"📄 {f.relative_to(directory)} ({size_str})\n"
        
        if len(files) > 50:
            output += f"\n... and {len(files) - 50} more files"
        
        output += "\n══════════════════════════════════════════"
        
        return output
        
    except Exception as e:
        return f"❌ Error finding files: {e}"


@tool
def get_file_info(file_path: str) -> str:
    """
    Get detailed information about a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File metadata and information
    """
    import stat
    from datetime import datetime
    from pathlib import Path
    
    try:
        path = Path(file_path)
        
        if not path.exists():
            return f"❌ File not found: {file_path}"
        
        file_stat = path.stat()
        
        # File type
        if path.is_file():
            file_type = "📄 File"
        elif path.is_dir():
            file_type = "📁 Directory"
        elif path.is_symlink():
            file_type = "🔗 Symlink"
        else:
            file_type = "❓ Unknown"
        
        # Size formatting
        size = file_stat.st_size
        if size > 1024*1024*1024:
            size_str = f"{size/(1024*1024*1024):.2f} GB"
        elif size > 1024*1024:
            size_str = f"{size/(1024*1024):.2f} MB"
        elif size > 1024:
            size_str = f"{size/1024:.2f} KB"
        else:
            size_str = f"{size} bytes"
        
        # Timestamps
        created = datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        modified = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        accessed = datetime.fromtimestamp(file_stat.st_atime).strftime("%Y-%m-%d %H:%M:%S")
        
        return f"""
📋 FILE INFO
══════════════════════════════════════════

📛 Name: {path.name}
📁 Directory: {path.parent}
{file_type}

📊 Size: {size_str}
🔤 Extension: {path.suffix or 'None'}

📅 Created: {created}
✏️ Modified: {modified}
👁️ Accessed: {accessed}

══════════════════════════════════════════
"""
        
    except Exception as e:
        return f"❌ Error getting file info: {e}"


@tool
def create_directory(dir_path: str) -> str:
    """
    Create a directory (and parent directories if needed).
    
    Args:
        dir_path: Path to the directory to create
        
    Returns:
        Confirmation of directory creation
    """
    from pathlib import Path
    
    try:
        path = Path(dir_path)
        
        if path.exists():
            return f"📁 Directory already exists: {dir_path}"
        
        path.mkdir(parents=True, exist_ok=True)
        
        return f"✅ Directory created: {dir_path}"
        
    except Exception as e:
        return f"❌ Error creating directory: {e}"


@tool
def copy_file(source: str, destination: str) -> str:
    """
    Copy a file from source to destination.
    
    Args:
        source: Source file path
        destination: Destination file path
        
    Returns:
        Confirmation of copy operation
    """
    import shutil
    from pathlib import Path
    
    try:
        src = Path(source)
        dst = Path(destination)
        
        if not src.exists():
            return f"❌ Source file not found: {source}"
        
        # Create destination directory if needed
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(src, dst)
        
        return f"✅ File copied: {source} → {destination}"
        
    except Exception as e:
        return f"❌ Error copying file: {e}"


@tool
def move_file(source: str, destination: str) -> str:
    """
    Move a file from source to destination.
    
    Args:
        source: Source file path
        destination: Destination file path
        
    Returns:
        Confirmation of move operation
    """
    import shutil
    from pathlib import Path
    
    try:
        src = Path(source)
        dst = Path(destination)
        
        if not src.exists():
            return f"❌ Source file not found: {source}"
        
        # Create destination directory if needed
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.move(str(src), str(dst))
        
        return f"✅ File moved: {source} → {destination}"
        
    except Exception as e:
        return f"❌ Error moving file: {e}"


if __name__ == "__main__":
    # Test the agent
    agent = SystemAgent()
    print("System Agent initialized")
    print(f"Tools: {[t.name for t in agent.tools]}")
    print(f"\nCapabilities:\n" + "\n".join(f"  • {c}" for c in agent.get_capabilities()))
