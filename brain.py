"""
==============================================================================
NeuroPilot — AI Brain & Intelligence Module (brain.py)
==============================================================================
WHAT THIS FILE IS FOR:
The complete AI intelligence layer (combining anomaly detection & assistant).
Uses Google Gemini Flash in the cloud (0% local hardware load) to:
1. Proactively analyze live telemetry and detect anomalies in real-time.
2. Translate complex system states into plain-English explanations.
3. Answer interactive user questions (e.g. "Why is my laptop so slow?")."""



import monitor
import json
import os
import re
import warnings
import logging

# Suppress the AFC (automatic function calling) recommendation notice from google.genai
# The AFC message uses logger.warning(), so we must silence the logger itself
logging.getLogger("google_genai").setLevel(logging.ERROR)
logging.getLogger("google_genai.models").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*Direct use of automatic function calling.*")
warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")

from google import genai

# Also set the internal flag to prevent the AFC message from ever being emitted
try:
    from google.genai.models import Models as _Models
    _Models._logged_afc_warning = True
except Exception:
    pass

try:
    from config import GEMINI_API_KEY, GEMINI_MODEL
except ImportError:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-3.5-flash"

# The API key comes only from config / environment (never hardcode it).
# If it's missing or invalid, client stays None and the rule-based fallback is used.
try:
    client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
except Exception:
    client = None
DEFAULT_MODEL = GEMINI_MODEL or "gemini-3.5-flash"

def format_telemetry_prompt(metrics, top_processes):
    summary = (
        f"CPU Usage: {metrics['cpu_percent']}%\n"
        f"RAM Usage: {metrics['mem_percent']}% "
        f"({metrics['mem_avail']:.1f} MB available of {metrics['mem_total']:.1f} MB)\n"
        f"Disk Usage: {metrics['disk_percent']}%\n"
        f"Battery: {metrics['batt_percent']}% (Plugged in: {metrics['batt_plugin']})"
    )
    top_apps_str = "\n".join(
        f"- {p['name']} (PID: {p['pid']}): {p['vms']:.1f} MB virtual memory"
        for p in top_processes
    )
    return summary + "\n\nTop Processes:\n" + top_apps_str


def analyze_system(metrics, top_processes):
    if client is None:
        return fallback_analysis(metrics, top_processes, error_msg="No Gemini API key configured")

    input_text = format_telemetry_prompt(metrics, top_processes)
    prompt = """You are NeuroPilot, an AI system health doctor.
Analyze the following live PC telemetry and determine if the machine is experiencing an anomaly or severe resource bottleneck.
{telemetry_text}
Respond ONLY with a valid JSON object matching this exact format:
{{
    "is_anomaly": true or false,
    "severity": "normal" or "warning" or "critical",
    "reason": "short 1-sentence plain-English explanation",
    "recommended_action": "terminate <PID>" or "none"
}}
"""
    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt.format(telemetry_text=input_text))
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)  
        return data
    except Exception as e:
        return fallback_analysis(metrics, top_processes, error_msg=str(e))


def fallback_analysis(metrics, top_processes, error_msg=""):
    """Rule-based fallback when Gemini cannot be reached."""
    cpu = metrics.get('cpu_percent', 0)
    ram = metrics.get('mem_percent', 0)
    is_anomaly = cpu > 85 or ram > 85
    severity = "critical" if (cpu > 90 or ram > 90) else ("warning" if is_anomaly else "normal")
    reason = f"High resource usage (CPU: {cpu}%, RAM: {ram}%)." if is_anomaly else "System operating within normal limits."
    if error_msg:
        reason += f" (Offline fallback: {error_msg})"

    # Only suggest a target when RAM is the problem (processes are ranked by memory, not CPU)
    action = "none"
    if ram > 85 and top_processes:
        top_proc = top_processes[0]
        action = f"terminate {top_proc.get('pid')}"

    return {
        "is_anomaly": is_anomaly,
        "severity": severity,
        "reason": reason,
        "recommended_action": action
    }


def parse_terminate_pid(recommended_action, top_processes=None):
    """
    Extracts the integer PID from a recommended action string like 'terminate 1234'.
    Returns None if no PID is found or action is 'none'.
    """
    if not recommended_action:
        return None
    action_str = str(recommended_action).lower().strip()
    if "terminate" not in action_str and "kill" not in action_str:
        return None
    match = re.search(r'\b(\d+)\b', action_str)
    if match:
        return int(match.group(1))
    return None


def chat(metrics, top_processes):
    if client is None:
        print("[!] AI chat is unavailable: no Gemini API key configured. "
              "Add GEMINI_API_KEY to your .env file.")
        return
    try:
        session = client.chats.create(
            model=DEFAULT_MODEL,
            config=genai.types.GenerateContentConfig(
                system_instruction="You are NeuroPilot, an AI system health doctor. Answer the user's questions about their PC.\n\nCurrent telemetry:\n" + format_telemetry_prompt(metrics, top_processes),
                temperature=0.3,
            )
        )
    except Exception as e:
        print(f"Could not start AI chat session: {e}")
        return

    print("Bot initialized! Type 'quit' or 'exit' to stop.")
    print("-" * 50)
    while True:
        try:
            user_input = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nBot: Goodbye!")
            break

        cleaned_input = user_input.strip()
        if cleaned_input.lower() in ['quit', 'exit']:
            print("Bot: Goodbye!")
            break

        if not cleaned_input:
            continue

        # Check for kill / terminate command
        kill_match = re.match(r'^(?:kill|terminate)(?:\s+([a-zA-Z0-9_\-\.]+))?$', cleaned_input, re.IGNORECASE)
        if kill_match:
            target = kill_match.group(1)
            if not target:
                print("[!] Usage: kill <PID> or kill <process_name>")
                continue
            if target.isdigit():
                target_pid = int(target)
                print(f"[*] Attempting to terminate PID {target_pid}...")
                monitor.terminate_process(pid=target_pid)
            else:
                print(f"[*] Attempting to terminate process '{target}'...")
                monitor.terminate_process(name=target)
            continue

        try:
            response = session.send_message(user_input)
            print(f"Bot: {response.text}")
        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == '__main__':
    metrics = monitor.get_system_metrics()
    top_processes = monitor.get_top_processes()

    print("Analyzing system state with Gemini...")
    analysis = analyze_system(metrics, top_processes)
    print(f"Diagnosis: {analysis.get('reason')}")
    print(f"Anomaly: {analysis.get('is_anomaly')} (Severity: {analysis.get('severity')})")
    print(f"Recommended action: {analysis.get('recommended_action')}")

    pid = parse_terminate_pid(analysis.get("recommended_action"), top_processes)
    if pid:
        print(f"Recommendation: terminate PID {pid} (confirm before killing)")

    chat(metrics, top_processes)