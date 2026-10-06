# -*- coding: utf-8 -*-
"""
Servidor Web Ligero del Dashboard Editorial
Permite al editor ver incidencias en tiempo real y tomar decisiones
(Aceptar, Rechazar / Aprender Whitelist)
"""

import http.server
import socketserver
import json
import os
import sys
import urllib.parse
from config import DASHBOARD_HOST, DASHBOARD_PORT, AUDIT_HISTORY_FILE, FEEDBACK_RULES_FILE, HOME_AUDIT_FILE
from orchestrator import EditorialOrchestrator

# Detección de carpeta web (recursos estáticos HTML/CSS/JS)
if getattr(sys, "frozen", False):
    bundle_web = os.path.join(getattr(sys, "_MEIPASS", ""), "web")
    if os.path.exists(bundle_web):
        WEB_DIR = bundle_web
    else:
        WEB_DIR = os.path.join(os.path.dirname(sys.executable), "web")
else:
    WEB_DIR = os.path.dirname(os.path.abspath(__file__))

orquestador_global = None

def asignar_orquestador(orq):
    global orquestador_global
    orquestador_global = orq


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def _responder_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        global orquestador_global
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/incidencias":
            if os.path.exists(AUDIT_HISTORY_FILE):
                try:
                    with open(AUDIT_HISTORY_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return self._responder_json(data)
                except Exception:
                    pass
            return self._responder_json([])

        elif parsed.path == "/api/home_audit":
            if os.path.exists(HOME_AUDIT_FILE):
                try:
                    with open(HOME_AUDIT_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return self._responder_json(data)
                except Exception:
                    pass
            return self._responder_json({"total_articulos": 0, "articulos": []})

        elif parsed.path == "/api/whitelist":
            if os.path.exists(FEEDBACK_RULES_FILE):
                try:
                    with open(FEEDBACK_RULES_FILE, "r", encoding="utf-8") as f:
                        rules = json.load(f)
                    return self._responder_json({"whitelist": rules.get("whitelist_palabras", [])})
                except Exception:
                    pass
            return self._responder_json({"whitelist": []})

        elif parsed.path == "/api/model":
            from config import MODELOS_SOPORTADOS, GROQ_MODEL
            modelo_actual = GROQ_MODEL
            if orquestador_global and hasattr(orquestador_global, "corrector"):
                modelo_actual = orquestador_global.corrector.model
            return self._responder_json({
                "actual": modelo_actual,
                "modelos": list(MODELOS_SOPORTADOS.values())
            })

        elif parsed.path in ("/ping", "/health"):
            # Endpoint de Keep-Alive para UptimeRobot y verificación de estado
            import threading
            from config import GROQ_MODEL
            modelo_actual = GROQ_MODEL
            if orquestador_global and hasattr(orquestador_global, "corrector"):
                modelo_actual = orquestador_global.corrector.model
            hilos = {t.name: t.is_alive() for t in threading.enumerate()}
            return self._responder_json({
                "status": "ok",
                "service": "Corrector Editorial Corvus Nigrum",
                "uptime": "activo",
                "agentes": "5 agentes IA en línea",
                "modelo_activo": modelo_actual,
                "monitor": hilos.get("monitor", False),
                "target": "https://www.eltiempo.com"
            })

        return super().do_GET()


    def do_POST(self):
        global orquestador_global
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        payload = json.loads(body) if body else {}

        if parsed.path == "/api/resolver":
            inc_id = payload.get("id")
            accion = payload.get("accion")  # "aceptada" o "falso_positivo"
            palabra = payload.get("palabra", "").strip().lower()

            # 1. Actualizar estado en historial
            if os.path.exists(AUDIT_HISTORY_FILE):
                try:
                    with open(AUDIT_HISTORY_FILE, "r", encoding="utf-8") as f:
                        historial = json.load(f)
                    for item in historial:
                        if item.get("id") == inc_id:
                            item["estado"] = accion
                    with open(AUDIT_HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump(historial, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print("Error actualizando historial:", e)

            # 2. Si fue falso positivo, agregar a whitelist (aprendizaje)
            if accion == "falso_positivo" and palabra:
                self._agregar_a_whitelist(palabra)

            return self._responder_json({"ok": True, "accion": accion})

        elif parsed.path == "/api/whitelist/add":
            pal = payload.get("palabra", "").strip().lower()
            if pal:
                self._agregar_a_whitelist(pal)
            return self._responder_json({"ok": True})

        elif parsed.path == "/api/whitelist/remove":
            pal = payload.get("palabra", "").strip().lower()
            if pal and os.path.exists(FEEDBACK_RULES_FILE):
                try:
                    with open(FEEDBACK_RULES_FILE, "r", encoding="utf-8") as f:
                        rules = json.load(f)
                    wlist = rules.get("whitelist_palabras", [])
                    if pal in wlist:
                        wlist.remove(pal)
                    rules["whitelist_palabras"] = wlist
                    with open(FEEDBACK_RULES_FILE, "w", encoding="utf-8") as f:
                        json.dump(rules, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            return self._responder_json({"ok": True})

        elif parsed.path == "/api/trigger":
            # Forzar sondeo manual completo desde el orquestador
            if not orquestador_global:
                orquestador_global = EditorialOrchestrator()
            incidencias = orquestador_global.ejecutar_ciclo(forzar_completo=True)
            return self._responder_json({
                "ok": True,
                "mensaje": f"Sondeo completo finalizado. {len(incidencias)} incidencias detectadas."
            })

        elif parsed.path == "/api/model":
            nuevo_modelo = payload.get("model")
            if nuevo_modelo:
                import config
                config.GROQ_MODEL = nuevo_modelo
                if orquestador_global and hasattr(orquestador_global, "corrector"):
                    orquestador_global.corrector.cambiar_modelo(nuevo_modelo)
                return self._responder_json({"ok": True, "modelo": nuevo_modelo})
            return self._responder_json({"ok": False, "error": "Modelo no especificado"}, 400)

        self.send_error(404, "Ruta no encontrada")

    def _agregar_a_whitelist(self, palabra):
        rules = {"whitelist_palabras": []}
        if os.path.exists(FEEDBACK_RULES_FILE):
            try:
                with open(FEEDBACK_RULES_FILE, "r", encoding="utf-8") as f:
                    rules = json.load(f)
            except Exception as e:
                print("Error leyendo whitelist:", e)
        wlist = rules.get("whitelist_palabras", [])
        if palabra not in wlist:
            wlist.append(palabra)
        rules["whitelist_palabras"] = wlist
        try:
            with open(FEEDBACK_RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Error guardando whitelist:", e)


def iniciar_servidor(port_callback=None):
    handler = DashboardHandler
    socketserver.TCPServer.allow_reuse_address = True

    puerto_elegido = DASHBOARD_PORT
    httpd = None

    for offset in range(15):
        candidato = DASHBOARD_PORT + offset
        try:
            httpd = socketserver.TCPServer((DASHBOARD_HOST, candidato), handler)
            puerto_elegido = candidato
            break
        except OSError:
            continue

    if not httpd:
        print(f"[Error Servidor Web] No se encontró puerto libre a partir del {DASHBOARD_PORT}.")
        return

    host_display = "localhost" if DASHBOARD_HOST in ("0.0.0.0", "127.0.0.1") else DASHBOARD_HOST
    print(f"\n=======================================================")
    print(f"  MESA DE CONTROL EDITORIAL EN VIVO")
    print(f"  Abre en tu navegador: http://{host_display}:{puerto_elegido}")
    print(f"=======================================================\n")

    if callable(port_callback):
        port_callback(puerto_elegido)

    with httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


if __name__ == "__main__":
    iniciar_servidor()
