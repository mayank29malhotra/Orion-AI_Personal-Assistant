"""
Screenshot & System Tools for Orion
Screen capture and push notifications.
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger("Orion")

# Data directory
DATA_DIR = Path("sandbox/data")


def _ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


@tool
def take_screenshot(output_path: Optional[str] = None, region: Optional[str] = None) -> str:
    """
    Take a screenshot of the screen.
    
    Args:
        output_path: Output file path (optional, defaults to sandbox/data/screenshot.png)
        region: Screen region as "x,y,width,height" (optional, captures full screen by default)
    """
    try:
        from PIL import ImageGrab
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(_ensure_data_dir() / f"screenshot_{timestamp}.png")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        if region:
            try:
                x, y, w, h = map(int, region.split(','))
                bbox = (x, y, x + w, y + h)
                img = ImageGrab.grab(bbox=bbox)
            except:
                return f"❌ Invalid region format. Use: x,y,width,height"
        else:
            img = ImageGrab.grab()
        
        img.save(output_path)
        
        logger.info(f"Screenshot saved: {output_path}")
        return f"📸 Screenshot saved: {output_path}"
    
    except ImportError:
        return "❌ PIL not installed. Install with: pip install pillow"
    except Exception as e:
        error_msg = f"Screenshot failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
def send_push_notification(title: str, message: str) -> str:
    """
    Send a desktop push notification.
    
    Args:
        title: Notification title
        message: Notification message
    """
    try:
        from plyer import notification
        
        notification.notify(
            title=title,
            message=message,
            app_name="Orion",
            timeout=10
        )
        
        logger.info(f"Push notification sent: {title}")
        return f"🔔 Notification sent: {title}"
    
    except ImportError:
        # Fallback for Windows
        try:
            import subprocess
            
            # PowerShell toast notification
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $template = @"
            <toast>
                <visual>
                    <binding template="ToastText02">
                        <text id="1">{title}</text>
                        <text id="2">{message}</text>
                    </binding>
                </visual>
            </toast>
"@
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Orion").Show($toast)
            '''
            
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Push notification sent via PowerShell: {title}")
                return f"🔔 Notification sent: {title}"
            else:
                return f"❌ Notification failed: {result.stderr}"
        except Exception as e:
            return f"❌ plyer not installed and fallback failed: {str(e)}"
    
    except Exception as e:
        error_msg = f"Notification failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
def get_system_info() -> str:
    """Get system information."""
    try:
        import platform
        import psutil
        
        info = []
        info.append("💻 System Information:")
        info.append(f"  OS: {platform.system()} {platform.release()}")
        info.append(f"  Machine: {platform.machine()}")
        info.append(f"  Processor: {platform.processor()}")
        info.append(f"  Python: {platform.python_version()}")
        
        # Memory
        mem = psutil.virtual_memory()
        info.append(f"\n📊 Memory:")
        info.append(f"  Total: {mem.total / (1024**3):.2f} GB")
        info.append(f"  Available: {mem.available / (1024**3):.2f} GB")
        info.append(f"  Used: {mem.percent}%")
        
        # Disk
        disk = psutil.disk_usage('/')
        info.append(f"\n💾 Disk:")
        info.append(f"  Total: {disk.total / (1024**3):.2f} GB")
        info.append(f"  Free: {disk.free / (1024**3):.2f} GB")
        info.append(f"  Used: {disk.percent}%")
        
        # CPU
        info.append(f"\n🔧 CPU:")
        info.append(f"  Cores: {psutil.cpu_count()}")
        info.append(f"  Usage: {psutil.cpu_percent()}%")
        
        logger.info("System info retrieved")
        return "\n".join(info)
    
    except ImportError:
        # Fallback without psutil
        import platform
        info = []
        info.append("💻 System Information:")
        info.append(f"  OS: {platform.system()} {platform.release()}")
        info.append(f"  Machine: {platform.machine()}")
        info.append(f"  Processor: {platform.processor()}")
        info.append(f"  Python: {platform.python_version()}")
        return "\n".join(info)
    except Exception as e:
        return f"❌ Failed to get system info: {str(e)}"


@tool
def list_directory(path: str = ".") -> str:
    """
    List contents of a directory.
    
    Args:
        path: Directory path (default: current directory)
    """
    try:
        path = Path(path)
        
        if not path.exists():
            return f"❌ Directory not found: {path}"
        
        if not path.is_dir():
            return f"❌ Not a directory: {path}"
        
        items = list(path.iterdir())
        
        if not items:
            return f"📁 Directory is empty: {path}"
        
        # Sort: directories first, then files
        dirs = sorted([i for i in items if i.is_dir()], key=lambda x: x.name.lower())
        files = sorted([i for i in items if i.is_file()], key=lambda x: x.name.lower())
        
        output = [f"📁 Contents of: {path.absolute()}\n"]
        
        for d in dirs:
            output.append(f"  📂 {d.name}/")
        
        for f in files:
            size = f.stat().st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/(1024*1024):.1f} MB"
            
            output.append(f"  📄 {f.name} ({size_str})")
        
        output.append(f"\n  Total: {len(dirs)} folders, {len(files)} files")
        
        logger.info(f"Listed directory: {path}")
        return "\n".join(output)
    
    except Exception as e:
        error_msg = f"Failed to list directory: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
def read_file_content(file_path: str) -> str:
    """
    Read contents of a text file.
    
    Args:
        file_path: Path to the file
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            return f"❌ File not found: {file_path}"
        
        if not path.is_file():
            return f"❌ Not a file: {file_path}"
        
        # Check file size
        size = path.stat().st_size
        if size > 1024 * 1024:  # 1MB limit
            return f"❌ File too large ({size/(1024*1024):.1f} MB). Maximum is 1 MB."
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Truncate if still too long
        if len(content) > 10000:
            content = content[:10000] + "\n\n... (truncated, file is very long)"
        
        logger.info(f"File read: {file_path}")
        return f"📄 {file_path}:\n\n{content}"
    
    except UnicodeDecodeError:
        return f"❌ Cannot read binary file: {file_path}"
    except Exception as e:
        error_msg = f"Failed to read file: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
def write_file_content(file_path: str, content: str) -> str:
    """
    Write content to a file.
    
    Args:
        file_path: Path to the file
        content: Content to write
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"File written: {file_path}")
        return f"✅ File written: {file_path}"
    
    except Exception as e:
        error_msg = f"Failed to write file: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ TOOL EXPORTS ============

def get_screenshot_tools():
    """Get screenshot tools."""
    return [
        take_screenshot,
    ]


def get_notification_tools():
    """Get notification tools."""
    return [
        send_push_notification,
    ]


def get_system_tools():
    """Get system utility tools."""
    return [
        get_system_info,
        list_directory,
        read_file_content,
        write_file_content,
    ]


def get_utility_tools():
    """Get all utility tools."""
    return (
        get_screenshot_tools() +
        get_notification_tools() +
        get_system_tools()
    )
