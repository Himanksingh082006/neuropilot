"""
==============================================================================
NeuroPilot — Main CLI Copilot Application (app.py)
==============================================================================
The central runner connecting `monitor.py` and `brain.py`:
- Displays real-time hardware health and top processes in the terminal.
- Calls `brain.analyze_system()` to check for anomalies via Gemini.
- Runs an interactive CLI prompt where you can chat or type `kill <pid>`.
==============================================================================
"""

import sys

# Fix encoding for Windows terminals that default to cp1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import monitor
import brain


# ── Dashboard Display ────────────────────────────────────────────────────────

def display_dashboard(metrics, top_processes, ai_report):
    """Print a clean formatted status summary to the terminal."""

    # Determine badge
    is_anomaly = ai_report.get("is_anomaly", False)
    severity = ai_report.get("severity", "normal")
    if is_anomaly and severity != "normal":
        badge = f"[!] {severity.upper()} ANOMALY DETECTED"
    else:
        badge = "[OK] HEALTHY"

    print()
    print("=" * 60)
    print("        NEUROPILOT  --  System Health Dashboard")
    print("=" * 60)

    # Hardware metrics
    batt = metrics.get("batt_percent", "?")
    plugged = "Plugged In" if metrics.get("batt_plugin") else "On Battery"
    print(f"  CPU   : {metrics.get('cpu_percent', 0):.1f}%")
    print(f"  RAM   : {metrics.get('mem_percent', 0):.1f}%  "
          f"({metrics.get('mem_avail', 0):.0f} MB free / {metrics.get('mem_total', 0):.0f} MB)")
    print(f"  Disk  : {metrics.get('disk_percent', 0):.1f}%")
    print(f"  Power : {batt}% ({plugged})")
    print("-" * 60)

    # Top processes
    print("  Top Processes:")
    for i, p in enumerate(top_processes, 1):
        print(f"    {i}. {p['name']:<25} PID: {p['pid']:<8} {p.get('vms', 0):.1f} MB")
    print("-" * 60)

    # AI assessment
    print(f"  Status : {badge}")
    print(f"  AI Says: {ai_report.get('reason', 'No diagnosis available.')}")
    rec_action = ai_report.get("recommended_action", "none")
    if rec_action and rec_action.lower() != "none":
        pid = brain.parse_terminate_pid(rec_action)
        if pid:
            print(f"  Action : Recommend terminating PID {pid}")
    print("=" * 60)


# ── Interactive Prompt ───────────────────────────────────────────────────────

def interactive_prompt(metrics, top_processes):
    """
    Run an interactive CLI loop:
      - Type a question  -> answered by brain.chat()
      - Type 'kill <PID>' -> terminates the process via monitor
      - Type 'exit'/'quit' -> stops
    """
    print()
    print("NeuroPilot Interactive Mode")
    print('   * Ask anything: "Why is my PC loud?", "What is Discord doing?"')
    print("   * Kill a process: kill <PID>")
    print("   * Type 'exit' or 'quit' to stop.")
    print("-" * 60)

    # Start a Gemini chat session with system context
    brain.chat(metrics, top_processes)


# ── Main Loop ────────────────────────────────────────────────────────────────

def main_loop():
    """Entry point: fetch data, analyze, alert, then enter interactive mode."""

    # Fetch live system data
    metrics = monitor.get_system_metrics()
    top_processes = monitor.get_top_processes()

    # Run AI analysis
    print("[*] Analyzing system state with Gemini...")
    ai_report = brain.analyze_system(metrics, top_processes)

    # Display dashboard
    display_dashboard(metrics, top_processes, ai_report)

    # Enter interactive chat
    interactive_prompt(metrics, top_processes)


if __name__ == "__main__":
    main_loop()
