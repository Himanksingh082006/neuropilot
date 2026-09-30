"""
==============================================================================
NeuroPilot — System Monitor Module (monitor.py)
==============================================================================
Reads hardware metrics (RAM, CPU, disk, battery) and running processes via
`psutil`, and provides safe process termination with safeguards against
killing critical system processes or NeuroPilot itself.
==============================================================================
"""

import sys
import os

# Fix encoding for Windows terminals that default to cp1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import psutil

# Protected system processes that should never be terminated
PROTECTED_NAMES = {
    "system", "system idle process", "registry", "smss.exe",
    "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "winlogon.exe", "svchost.exe", "explorer.exe",
}


def get_system_metrics():
    memory_stats = psutil.virtual_memory()
    cpu_usage = psutil.cpu_percent(interval=0.5)
    disk_usage = psutil.disk_usage(path='C:\\').percent
    sensor_usage = psutil.sensors_battery()

    metrics = {
        'mem_total': (memory_stats.total / (1024 ** 2)),
        'mem_avail': (memory_stats.available / (1024 ** 2)),
        'mem_percent': memory_stats.percent,
        'cpu_percent': cpu_usage,
        'disk_percent': disk_usage,
        'batt_percent': sensor_usage.percent if sensor_usage else 100,
        'batt_plugin': sensor_usage.power_plugged if sensor_usage else True,
    }
    return metrics


def get_top_processes(limit=5):
    listOfProcObjects = []
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=['pid', 'name', 'username'])
            pinfo['vms'] = proc.memory_info().vms / (1024 * 1024)
            listOfProcObjects.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    listOfProcObjects = sorted(listOfProcObjects, key=lambda procObj: procObj['vms'], reverse=True)
    return listOfProcObjects[:limit]


def terminate_process(pid=None, name=None):
    """
    Safely terminates a process by PID or by name.
    Includes safeguards against critical system processes, invalid PIDs, and self-termination.
    Returns: (bool, str) -> (success_status, message)
    """
    if pid is None and name is None:
        msg = "[!] Please provide a valid PID or process name to terminate."
        print(msg)
        return False, msg

    # Termination by process name
    if name is not None:
        name_clean = str(name).strip().lower()
        if name_clean in PROTECTED_NAMES or f"{name_clean}.exe" in PROTECTED_NAMES:
            msg = f"[!] Refusing to terminate critical system process: '{name}'"
            print(msg)
            return False, msg

        matched_procs = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                p_name = proc.info.get('name')
                if p_name and (p_name.lower() == name_clean or p_name.lower() == f"{name_clean}.exe"):
                    if proc.pid not in (0, 4, os.getpid()):
                        matched_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not matched_procs:
            msg = f"[!] No running process found matching '{name}'."
            print(msg)
            return False, msg

        success_count = 0
        for proc in matched_procs:
            try:
                proc.terminate()
                proc.wait(timeout=3)
                print(f"[*] Process {proc.pid} ({proc.name()}) terminated successfully.")
                success_count += 1
            except psutil.TimeoutExpired:
                print(f"[!] Process {proc.pid} did not terminate in time. Forcing kill...")
                try:
                    proc.kill()
                    success_count += 1
                except Exception as e:
                    print(f"[!] Force kill failed for PID {proc.pid}: {e}")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"[!] Could not terminate PID {proc.pid}: {e}")

        if success_count > 0:
            msg = f"Terminated {success_count} process(es) matching '{name}'."
            return True, msg
        else:
            msg = f"Failed to terminate processes matching '{name}'."
            return False, msg

    # Termination by PID
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        msg = f"[!] Invalid PID: {pid}"
        print(msg)
        return False, msg

    if pid in (0, 4):
        msg = f"[!] Refusing to terminate critical Windows System PID {pid}."
        print(msg)
        return False, msg

    if pid == os.getpid():
        msg = "[!] Refusing to terminate NeuroPilot's own process."
        print(msg)
        return False, msg

    try:
        p = psutil.Process(pid)
        p_name = p.name()

        if p_name.lower() in PROTECTED_NAMES:
            msg = f"[!] Refusing to terminate critical system process: {p_name} (PID: {pid})"
            print(msg)
            return False, msg

        p.terminate()
        p.wait(timeout=3)
        msg = f"Process {pid} ({p_name}) terminated successfully."
        print(f"[*] {msg}")
        return True, msg

    except psutil.NoSuchProcess:
        msg = f"Process {pid} does not exist."
        print(f"[!] {msg}")
        return False, msg
    except psutil.AccessDenied:
        msg = f"Permission denied to terminate process {pid}. (Try running terminal as Administrator)"
        print(f"[!] {msg}")
        return False, msg
    except psutil.TimeoutExpired:
        print(f"[!] Process {pid} did not terminate in time. Forcing kill...")
        try:
            p.kill()
            msg = f"Process {pid} force killed."
            print(f"[*] {msg}")
            return True, msg
        except Exception as e:
            msg = f"Force kill failed for PID {pid}: {e}"
            print(f"[!] {msg}")
            return False, msg
    except Exception as e:
        msg = f"Error terminating process {pid}: {e}"
        print(f"[!] {msg}")
        return False, msg


# ── DEMO TEST BLOCK ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    import subprocess
    import time

    print("=" * 60)
    print("🧠 NeuroPilot — System Monitor & Kill Command Test")
    print("=" * 60)

    # 1. Test live hardware stats
    print("\n[1] Live System Metrics:")
    metrics = get_system_metrics()
    for key, val in metrics.items():
        print(f"    • {key:<12}: {val}")

    # 2. Test top memory processes
    print("\n[2] Top 5 Memory Consuming Processes:")
    top_apps = get_top_processes()
    for rank, app in enumerate(top_apps, start=1):
        print(f"    {rank}. {app['name']:<25} (PID: {app['pid']:<6}) — {app.get('vms', 0):>7.1f} MB")

    # 3. Test Process Termination safeguards
    print("\n[3] Testing terminate_process() safeguards:")
    print("    • Testing None PID:")
    terminate_process()
    print("    • Testing PID 0 (System Idle):")
    terminate_process(pid=0)
    print("    • Testing PID 4 (System):")
    terminate_process(pid=4)
    print("    • Testing self PID:")
    terminate_process(pid=os.getpid())
    print("    • Testing protected name (csrss.exe):")
    terminate_process(name="csrss.exe")
    print("    • Testing non-existent PID:")
    terminate_process(pid=99999999)

    # 4. Test real termination by PID with a spawned dummy process
    print("\n[4] Testing real termination by PID:")
    dummy = subprocess.Popen(
        ["cmd.exe", "/c", "timeout /t 60"],
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    )
    time.sleep(0.5)
    print(f"    • Spawned dummy test process (PID: {dummy.pid})")
    terminate_process(pid=dummy.pid)

    # 5. Test real termination by Name with a spawned dummy process
    print("\n[5] Testing real termination by Name:")
    dummy2 = subprocess.Popen(
        ["notepad.exe"],
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    )
    time.sleep(0.8)
    print(f"    • Spawned notepad.exe test process (PID: {dummy2.pid})")
    terminate_process(name="notepad.exe")

    print("\n" + "=" * 60)
    print("✅ All System Monitor & Kill Command Tests Completed!")
    print("=" * 60)
