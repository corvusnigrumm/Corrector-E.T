# -*- coding: utf-8 -*-
"""
Agente Orquestador y Pipeline Central
Coordina el flujo completo de los 5 agentes editoriales:
  Rastreador ➔ Extractor ➔ Corrector ➔ Triage ➔ Notificador ➔ Retroalimentación
Audita exhaustivamente el home completo de El Tiempo y persiste el censo editorial.
"""

import sys
import io
import json
import os
import time
from datetime import datetime

# Consola Windows UTF-8
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

from agents.crawler import CrawlerAgent
from agents.extractor import ExtractorAgent
from agents.corrector import CorrectorAgent
from agents.triage import TriageAgent
from agents.notifier import NotifierAgent
from config import URL_TARGET, CRAWL_INTERVAL_SECONDS, HOME_AUDIT_FILE


class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    MAGENTA = "\033[95m"
    GRAY    = "\033[90m"


class EditorialOrchestrator:
    def __init__(self, url=URL_TARGET):
        self.url = url
        print(f"{Color.BOLD}{Color.CYAN}⟳ Inicializando Equipo de 5 Agentes Editoriales...{Color.RESET}")
        self.crawler = CrawlerAgent()
        self.extractor = ExtractorAgent()
        self.corrector = CorrectorAgent()
        self.triage = TriageAgent()
        self.notifier = NotifierAgent()
        print(f"{Color.GREEN}✔ Todos los agentes listos y comunicados.{Color.RESET}\n")

    def ejecutar_ciclo(self, forzar_completo=False):
        """Ejecuta una pasada completa del pipeline sobre el Home de El Tiempo."""
        inicio = time.time()
        ahora = datetime.now().strftime("%H:%M:%S")
        modo_txt = "AUDITORÍA COMPLETA DEL HOME" if forzar_completo else "sondeo continuo"
        print(f"{Color.BOLD}{Color.MAGENTA}[{ahora}] [Pipeline] Iniciando {modo_txt}...{Color.RESET}")

        # 1. Agente Rastreador: Extracción completa del Home
        bloques_modificados, bloques_totales, hubo_cambios = self.crawler.sondeo_y_diff(
            self.url, forzar_completo=forzar_completo
        )

        if not hubo_cambios and not forzar_completo:
            dur = time.time() - inicio
            print(f"{Color.GRAY}  [Agente 1: Rastreador] Sin cambios desde la última pasada ({len(bloques_totales)} notas iguales). Pipeline suspendido ({dur:.2f}s).{Color.RESET}\n")
            return []

        print(f"{Color.CYAN}  [Agente 1: Rastreador] Detectadas {len(bloques_totales)} notas periodísticas en la portada.{Color.RESET}")
        if not forzar_completo and len(bloques_modificados) < len(bloques_totales):
            print(f"{Color.YELLOW}  [Agente 1: Rastreador] {len(bloques_modificados)} notas nuevas o editadas requieren revisión.{Color.RESET}")

        # Guardar inventario inmediato para visualización instantánea en el dashboard
        self._guardar_censo_home(bloques_totales, [], estado_default="en_revision")

        # 2. Agente Extractor: Estructuración atómica de campos
        items_atomicos = self.extractor.procesar_lote(bloques_modificados)
        print(f"{Color.CYAN}  [Agente 2: Extractor] {len(items_atomicos)} notas descompuestas en campos limpios (titular, bajada, balazos).{Color.RESET}")

        # 3. Agente Corrector: Detección con IA (Groq LLM)
        print(f"{Color.CYAN}  [Agente 3: Corrector] Evaluando ortografía y estilo con IA...{Color.RESET}")
        hallazgos_crudos = self.corrector.auditar_campos(items_atomicos)
        print(f"\n{Color.CYAN}  [Agente 3: Corrector] {len(hallazgos_crudos)} posibles faltas identificadas.{Color.RESET}")

        # 4. Agente de Triage: Priorización, deduplicación y severidad
        incidencias = self.triage.procesar_hallazgos(hallazgos_crudos)
        print(f"{Color.CYAN}  [Agente 4: Triage] {len(incidencias)} incidencias priorizadas tras filtrar duplicados y whitelist.{Color.RESET}")

        # 5. Generar Censo Completo de la Portada para el Dashboard
        self._guardar_censo_home(bloques_totales, incidencias, estado_default="aprobada")

        # 6. Agente de Notificación: Alertar al editor
        if incidencias:
            self.notifier.alertar(incidencias)
        else:
            print(f"{Color.GREEN}  ✔ Portada impecable: No hay faltas ortográficas que requieran intervención.{Color.RESET}\n")

        dur = time.time() - inicio
        print(f"{Color.GRAY}  Ciclo completado en {dur:.2f} seg. ({len(bloques_totales)} artículos cubiertos){Color.RESET}\n")
        return incidencias

    def _guardar_censo_home(self, bloques_totales, incidencias_ciclo, estado_default="aprobada"):
        """Guarda el inventario completo de notas del Home auditadas con su estado real."""
        # Unir incidencias del ciclo actual con todas las alertas pendientes del historial
        todas_activas = [inc for inc in self.triage.alertas_activas if inc.get("estado") == "pendiente"]
        pool_incidencias = []
        huellas_vistas = set()

        for inc in (list(incidencias_ciclo or []) + todas_activas):
            h = inc.get("huella")
            if h and h not in huellas_vistas:
                huellas_vistas.add(h)
                pool_incidencias.append(inc)
            elif not h and inc not in pool_incidencias:
                pool_incidencias.append(inc)

        censo = []
        ahora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for b in bloques_totales:
            url_b = (b.get("url") or "").strip().lower()
            uid_b = (b.get("uid") or "").strip().lower()
            tit_b = (b.get("titular") or "").strip().lower()
            baj_b = (b.get("bajada") or "").strip().lower()

            incs_nota = []
            for inc in pool_incidencias:
                url_i = (inc.get("url") or "").strip().lower()
                uid_i = (inc.get("uid") or "").strip().lower()
                texto_i = (inc.get("texto_completo") or "").strip().lower()

                match = False
                if url_b and url_i and (url_b == url_i or url_b in url_i or url_i in url_b):
                    match = True
                elif uid_b and uid_i and uid_b == uid_i:
                    match = True
                elif texto_i and (texto_i in tit_b or texto_i in baj_b or tit_b in texto_i):
                    match = True

                if match and inc not in incs_nota:
                    incs_nota.append(inc)

            estado = "con_incidencia" if incs_nota else estado_default

            censo.append({
                "uid": b.get("uid"),
                "seccion": b.get("seccion", "Portada General"),
                "posicion": b.get("posicion", "TITULAR"),
                "titular": b.get("titular"),
                "bajada": b.get("bajada"),
                "vinetas": b.get("vinetas", []),
                "url": b.get("url", ""),
                "estado": estado,
                "incidencias": incs_nota,
                "timestamp": ahora_iso
            })

        try:
            with open(HOME_AUDIT_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "total_articulos": len(censo),
                    "fecha_auditoria": ahora_iso,
                    "aprobados": sum(1 for c in censo if c["estado"] == "aprobada"),
                    "con_incidencias": sum(1 for c in censo if c["estado"] == "con_incidencia"),
                    "articulos": censo
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Orquestador] Error guardando censo de home: {e}")

    def iniciar_monitoreo_continuo(self, intervalo=CRAWL_INTERVAL_SECONDS):
        """Bucle periódico de monitoreo."""
        print(f"{Color.BOLD}{Color.GREEN}🚀 Monitor continuo activo. Intervalo: {intervalo} segundos. Presiona Ctrl+C para detener.{Color.RESET}\n")
        try:
            while True:
                self.ejecutar_ciclo(forzar_completo=False)
                time.sleep(intervalo)
        except KeyboardInterrupt:
            print(f"\n{Color.YELLOW}🛑 Monitoreo detenido por el usuario.{Color.RESET}")


if __name__ == "__main__":
    orquestador = EditorialOrchestrator()
    orquestador.ejecutar_ciclo(forzar_completo=True)
