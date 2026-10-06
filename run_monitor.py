# -*- coding: utf-8 -*-
"""
Script Principal de Ejecución:
Lanza el servidor Dashboard Web en segundo plano y el monitor continuo de los 5 agentes.
Diseñado para ejecución local (.exe / script) y despliegue cloud (Render).
"""

import io
import os
import sys

# Consola Windows UTF-8 segura
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        elif hasattr(sys.stdout, "buffer") and sys.stdout.buffer is not None:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        elif hasattr(sys.stderr, "buffer") and sys.stderr.buffer is not None:
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

import threading
import time
import webbrowser
from orchestrator import EditorialOrchestrator
from web.server import iniciar_servidor, asignar_orquestador
from config import CRAWL_INTERVAL_SECONDS, DASHBOARD_HOST, DASHBOARD_PORT, IS_CLOUD

# Puerto activo que se actualizará si el 5000 está en uso
_puerto_activo = DASHBOARD_PORT

def _notificar_puerto(puerto):
    global _puerto_activo
    _puerto_activo = puerto

def abrir_navegador():
    time.sleep(1.8)
    host = "localhost" if DASHBOARD_HOST in ("0.0.0.0", "127.0.0.1") else DASHBOARD_HOST
    url = f"http://{host}:{_puerto_activo}"
    try:
        webbrowser.open_new_tab(url)
    except Exception:
        pass

def main():
    print("=" * 60)
    print("  CORRECTOR EDITORIAL AUTOMATIZADO - EL TIEMPO")
    print("  Sistema Multi-Agente con Inteligencia Artificial")
    print("=" * 60)

    # 1. Hilo para el servidor Dashboard Web
    t_web = threading.Thread(target=iniciar_servidor, args=(_notificar_puerto,), daemon=True)
    t_web.start()
    time.sleep(0.8)

    # Abrir navegador automáticamente si se ejecuta en local / escritorio
    if not IS_CLOUD:
        threading.Thread(target=abrir_navegador, daemon=True).start()

    # 2. Orquestador en el hilo principal
    orquestador = EditorialOrchestrator()
    asignar_orquestador(orquestador)

    # Primera pasada inmediata: Auditoría completa de todo el Home
    try:
        orquestador.ejecutar_ciclo(forzar_completo=True)
    except Exception as e:
        print(f"[Aviso] Primera pasada tuvo una excepción controlada: {e}")

    # Bucle periódico de monitoreo
    orquestador.iniciar_monitoreo_continuo(intervalo=CRAWL_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Detenido] Aplicación cerrada por el usuario.")
        sys.exit(0)
    except Exception as e:
        import traceback
        print("\n" + "=" * 60)
        print("  [ERROR FATAL INESPERADO]")
        print("=" * 60)
        traceback.print_exc()
        print("\nPresione Enter para salir...")
        try:
            input()
        except Exception:
            pass
        sys.exit(1)
