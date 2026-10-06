# -*- coding: utf-8 -*-
"""
Agente 5: Notificación y Despacho
1. Genera alertas de consola visuales con colores ANSI clasificados por severidad.
2. Registra las incidencias en la base de datos de historial para alimentar el Dashboard Web.
3. Envía webhooks si están configurados.
"""

import json
import os
from datetime import datetime
from config import AUDIT_HISTORY_FILE


class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    GREEN   = "\033[92m"
    CYAN    = "\033[96m"
    GRAY    = "\033[90m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"


class NotifierAgent:
    def __init__(self, history_file=AUDIT_HISTORY_FILE):
        self.history_file = history_file

    def _guardar_en_historial(self, nuevas_incidencias):
        """Persiste las nuevas incidencias para el dashboard web."""
        historial = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    historial = json.load(f)
            except Exception:
                historial = []

        # Agregar timestamp real
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for inc in nuevas_incidencias:
            inc["timestamp"] = ahora
            historial.insert(0, inc)

        # Limitar historial a últimas 300 alertas
        historial = historial[:300]

        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(historial, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Agente 5: Notificador] ✘ Error guardando historial: {e}")

    def alertar(self, incidencias):
        """Muestra alertas formateadas en consola y actualiza la base de datos."""
        if not incidencias:
            return

        self._guardar_en_historial(incidencias)

        print(f"\n{Color.BOLD}{Color.RED}{'🚨 '*3} COLA DE INCIDENCIAS PARA EL EDITOR ({len(incidencias)}) {'🚨 '*3}{Color.RESET}\n")

        for inc in incidencias:
            sev = inc["severidad"]
            color_sev = Color.RED if sev == "CRÍTICA" else Color.YELLOW if sev == "MEDIA" else Color.GREEN
            tag_sev = f"[{sev}]"

            print(f"  {Color.BOLD}{color_sev}{tag_sev} {inc['seccion']} | {inc['campo'].upper()} ({inc['posicion']}){Color.RESET}")
            print(f"  {Color.GRAY}URL: {inc['url']}{Color.RESET}")
            print(f"  {Color.WHITE}\"{inc['texto_completo']}\"{Color.RESET}")
            print(f"  {Color.RED}✖ Error: {Color.BOLD}{inc['palabra_erronea']}{Color.RESET} ➔ Sugerencia: {Color.GREEN}{Color.BOLD}{inc['correccion']}{Color.RESET}")
            if inc.get("explicacion"):
                print(f"  {Color.GRAY}ℹ Motivo: {inc['explicacion']}{Color.RESET}")
            print(f"  {Color.GRAY}{'-'*68}{Color.RESET}\n")
