# -*- coding: utf-8 -*-
"""
Configuración central del Sistema Multi-Agente
Soporta ejecución local, empaquetado PyInstaller (.exe) y despliegue en la nube (Render).
"""
import os
import sys

# Asegurar certificados SSL para requests y httpx en Windows y PyInstaller
try:
    import certifi
    ca_bundle = certifi.where()
    if os.path.exists(ca_bundle):
        os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
except Exception:
    pass

# Cargar variables de entorno desde archivo .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

URL_TARGET = "https://www.eltiempo.com/"
CRAWL_INTERVAL_SECONDS = int(os.environ.get("CRAWL_INTERVAL_SECONDS", 90))

# API de Groq
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    print("[Config] ⚠ GROQ_API_KEY no configurada. El agente corrector IA no funcionará hasta configurarla.")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Perfiles de Modelos de IA Disponibles
MODELOS_SOPORTADOS = {
    "qwen/qwen3.8-27b": {
        "id": "qwen/qwen3.8-27b",
        "alias": "qwen",
        "nombre": "Qwen 3.8 (27B)",
        "descripcion": "Alta velocidad y precisión ortográfica en español",
        "temperature": 0.6,
        "top_p": 0.95,
        "max_completion_tokens": 2048,
        "reasoning_effort": "default"
    },
    "openai/gpt-oss-120b": {
        "id": "openai/gpt-oss-120b",
        "alias": "gpt",
        "nombre": "GPT-OSS (120B)",
        "descripcion": "Razonamiento profundo y sintaxis avanzada",
        "temperature": 1.0,
        "top_p": 1.0,
        "max_completion_tokens": 2048,
        "reasoning_effort": "medium"
    }
}

GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")

# Detección de entorno compilado (PyInstaller) vs script normal
if getattr(sys, "frozen", False):
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    # Si se ejecuta dentro de dist/, unificar con la raíz si existe storage padre
    if os.path.basename(exe_dir).lower() == "dist" and os.path.exists(os.path.join(exe_dir, "..", "storage")):
        BASE_DIR = os.path.abspath(os.path.join(exe_dir, ".."))
    else:
        BASE_DIR = exe_dir
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

# Archivos de persistencia (siempre en BASE_DIR para persistir entre reinicios)
STORAGE_DIR = os.environ.get("STORAGE_DIR", os.path.join(BASE_DIR, "storage"))
os.makedirs(STORAGE_DIR, exist_ok=True)

CACHE_STATE_FILE = os.path.join(STORAGE_DIR, "cache_state.json")
FEEDBACK_RULES_FILE = os.path.join(STORAGE_DIR, "feedback_rules.json")
AUDIT_HISTORY_FILE = os.path.join(STORAGE_DIR, "audit_history.json")
HOME_AUDIT_FILE = os.path.join(STORAGE_DIR, "home_audit.json")

# Diccionario léxico (primero buscar en BASE_DIR, luego en BUNDLE_DIR si fue empaquetado)
LEXICO_LOCAL = os.path.join(BASE_DIR, "es_full.txt")
if not os.path.exists(LEXICO_LOCAL):
    LEXICO_LOCAL = os.path.join(BUNDLE_DIR, "es_full.txt")

LEXICO_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/es/es_full.txt"

# Servidor Web Dashboard
# En Render u otros hosts en la nube, se inyecta la variable $PORT y se debe escuchar en 0.0.0.0
IS_CLOUD = bool(os.environ.get("RENDER") or os.environ.get("PORT"))
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0" if IS_CLOUD else "127.0.0.1")
DASHBOARD_PORT = int(os.environ.get("PORT", os.environ.get("DASHBOARD_PORT", 5000)))

