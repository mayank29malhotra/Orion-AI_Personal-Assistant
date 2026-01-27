"""
Windows Service Installer for Orion AI Assistant
Run as Administrator: python install_service.py install
"""
import os
import sys
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import time
import subprocess
from pathlib import Path


class OrionService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OrionAI"
    _svc_display_name_ = "Orion AI Personal Assistant"
    _svc_description_ = "Runs Orion AI Assistant as a Windows background service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True
        self.process = None

    def SvcStop(self):
        """Stop the service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        if self.process:
            self.process.terminate()

    def SvcDoRun(self):
        """Run the service"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        """Main service logic"""
        # Get the directory where this script is located
        service_dir = Path(__file__).parent
        app_path = service_dir / "app.py"
        
        # Check for virtual environment
        venv_python = service_dir / "venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        
        while self.is_running:
            try:
                servicemanager.LogInfoMsg(f"Starting Orion from {app_path}")
                
                # Start the application
                self.process = subprocess.Popen(
                    [python_exe, str(app_path)],
                    cwd=str(service_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait for process to complete or service to stop
                while self.is_running:
                    if self.process.poll() is not None:
                        # Process ended, restart it
                        servicemanager.LogWarningMsg("Orion process ended, restarting...")
                        time.sleep(5)
                        break
                    
                    # Check if service stop was requested
                    if win32event.WaitForSingleObject(self.hWaitStop, 1000) == win32event.WAIT_OBJECT_0:
                        break
                        
            except Exception as e:
                servicemanager.LogErrorMsg(f"Error in Orion service: {str(e)}")
                time.sleep(10)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        # If run without arguments, show help
        print("\n=== Orion AI Service Installer ===\n")
        print("Usage:")
        print("  Install:   python install_service.py install")
        print("  Start:     python install_service.py start")
        print("  Stop:      python install_service.py stop")
        print("  Remove:    python install_service.py remove")
        print("\nNote: Must run as Administrator!\n")
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(OrionService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Handle install/remove/start/stop commands
        win32serviceutil.HandleCommandLine(OrionService)
