"""
==============================================================================
NeuroPilot — Configuration Settings (config.py)
==============================================================================
Central place to define project settings, alert limits, and API keys.
"""
import os
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()

# ── Gemini API Settings ──

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.5-flash"

# ── Monitoring & Alert Thresholds ──
REFRESH_INTERVAL_SECONDS = 2.0
CPU_WARNING_THRESHOLD = 80.0       # Alert when CPU % exceeds this
RAM_WARNING_THRESHOLD = 80.0       # Alert when RAM % exceeds this
TOP_PROCESSES_LIMIT = 5            # Number of resource-heavy apps to display

# ── Anomaly Detection Model ──
MODEL_CONTAMINATION_RATE = 0.05    # Expected outlier rate (~5%)
DATA_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "system_history.json")
MODEL_FILE = os.path.join(os.path.dirname(__file__), "data", "anomaly_model.pkl")
