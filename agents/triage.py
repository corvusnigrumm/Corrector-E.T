# -*- coding: utf-8 -*-
"""
Agente 4: Triage y Priorización
1. Clasifica la severidad (CRÍTICA, MEDIA, BAJA) según el campo y la posición en portada.
2. Descarta falsos positivos y deduplica para no renotificar notas ya alertadas.
3. Entrega una cola priorizada de incidencias reales para el editor.
"""

import hashlib
import json
import os
from datetime import datetime
from config import AUDIT_HISTORY_FILE, FEEDBACK_RULES_FILE


class TriageAgent:
    def __init__(self, history_file=AUDIT_HISTORY_FILE, feedback_file=FEEDBACK_RULES_FILE):
        self.history_file = history_file
        self.feedback_file = feedback_file
        self.alertas_activas = self._cargar_historial()

    def _cargar_historial(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _cargar_whitelist(self):
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(w.lower().strip() for w in data.get("whitelist_palabras", []))
            except Exception:
                return set()
        return set()

    def calcular_severidad(self, item):
        """
        Determina el nivel de severidad según visibilidad e impacto en portada.
        """
        campo = item.get("campo", "").lower()
        posicion = item.get("posicion", "").lower()
        seccion = item.get("seccion", "").lower()

        # 🔴 CRÍTICA: Título SEO, Meta Description o Titulares H1 / H2 / Apertura
        if "seo" in campo or "title" in posicion or "meta" in posicion:
            return "CRÍTICA"
        if "h1" in posicion or "h2" in posicion or "apertura" in seccion:
            return "CRÍTICA"

        # 🟡 MEDIA: Titulares H3 / H4 o Bajadas
        if "h3" in posicion or "h4" in posicion or "titular" in campo or "bajada" in campo:
            return "MEDIA"

        # 🟢 BAJA: Balazos / Viñetas
        return "BAJA"

    def procesar_hallazgos(self, hallazgos_crudos):
        """
        Filtra, clasifica y deduplica la lista de hallazgos.
        Retorna la cola priorizada de incidencias.
        """
        whitelist = self._cargar_whitelist()
        cola_priorizada = []

        # Mapa de huellas ya reportadas en historial pendiente
        huellas_vistas = set()
        for h in self.alertas_activas:
            huellas_vistas.add(h.get("huella"))

        base_id = max([item.get("id", 0) for item in self.alertas_activas], default=0)

        for h in hallazgos_crudos:
            palabra = h.get("palabra_erronea", "").strip()

            # 1. Filtro Whitelist de feedback
            if palabra.lower() in whitelist:
                continue

            # 2. Generar huella única para deduplicación: (url + palabra + campo)
            firma = f"{h.get('url')}|{palabra.lower()}|{h.get('campo')}"
            huella = hashlib.sha256(firma.encode("utf-8")).hexdigest()

            # Si ya fue reportada y está activa, no volver a molestar
            if huella in huellas_vistas:
                continue

            huellas_vistas.add(huella)

            # 3. Asignar severidad
            severidad = self.calcular_severidad(h)

            incidencia = {
                "id": base_id + len(cola_priorizada) + 1,
                "huella": huella,
                "severidad": severidad,
                "estado": "pendiente",  # pendiente | aceptada | falso_positivo
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "url": h.get("url"),
                "seccion": h.get("seccion"),
                "posicion": h.get("posicion"),
                "campo": h.get("campo"),
                "texto_completo": h.get("texto_completo"),
                "palabra_erronea": palabra,
                "correccion": h.get("correccion"),
                "tipo_error": h.get("tipo_error"),
                "explicacion": h.get("explicacion")
            }
            cola_priorizada.append(incidencia)

        # Ordenar: CRÍTICA primero, luego MEDIA, luego BAJA
        orden = {"CRÍTICA": 1, "MEDIA": 2, "BAJA": 3}
        cola_priorizada.sort(key=lambda x: orden.get(x["severidad"], 4))

        # Persistir en historial
        if cola_priorizada:
            self.alertas_activas.extend(cola_priorizada)
            try:
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump(self.alertas_activas, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[Agente 4: Triage] Error persistiendo historial: {e}")

        return cola_priorizada
