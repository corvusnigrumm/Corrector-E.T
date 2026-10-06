# -*- coding: utf-8 -*-
"""
Agente 3: Corrector Ortográfico y Tipográfico Estricto
Detecta exclusivamente errores ortográficos graves, dedazos, palabras mal escritas,
palabras pegadas por error tipográfico y tildes omitidas en palabras comunes.
Descarta sugerencias de estilo, omisiones periodísticas válidas de artículos y nombres propios.
"""

import json
import os
import re
import time
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, LEXICO_LOCAL, FEEDBACK_RULES_FILE


class CorrectorAgent:
    def __init__(self, api_key=GROQ_API_KEY, model=GROQ_MODEL):
        self.api_key = api_key
        self.model = model
        self.lexico = self._cargar_lexico()
        self.feedback_rules = self._cargar_feedback()

    def _cargar_lexico(self):
        lexico = set()
        if os.path.exists(LEXICO_LOCAL):
            try:
                with open(LEXICO_LOCAL, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        partes = line.split()
                        if partes:
                            lexico.add(partes[0].lower())
            except Exception:
                pass
        return lexico

    def _cargar_feedback(self):
        if os.path.exists(FEEDBACK_RULES_FILE):
            try:
                with open(FEEDBACK_RULES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"whitelist_palabras": []}

    def recargar_reglas(self):
        """Recarga el diccionario dinámico de excepciones cuando el editor toma decisiones."""
        self.feedback_rules = self._cargar_feedback()

    def _es_palabra_excluida(self, palabra):
        p = palabra.lower().strip()
        whitelist = [w.lower().strip() for w in self.feedback_rules.get("whitelist_palabras", [])]
        return p in whitelist

    def _es_hallazgo_invalido(self, palabra, correccion, texto_original):
        """
        Filtro de seguridad en Python para descartar falsos positivos de estilo,
        cifras numéricas, URLs o inventos del modelo.
        """
        p = palabra.strip()
        c = correccion.strip()

        # 1. No existe en el texto original
        if p.lower() not in texto_original.lower():
            return True

        # 2. Cifras o números (ej. '61.600', '7', '$440')
        if re.search(r"^\$?\d+([.,]\d+)*%?$", p):
            return True

        # 3. URLs o dominios
        if any(ext in p.lower() for ext in [".com", ".co", "http", "www.", ".org"]):
            return True

        # 4. Longitud insignificante o signos de puntuación
        if len(re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ]", "", p)) < 2:
            return True

        # 5. Descartar sugerencias puramente de estilo o inserción de artículos ('un', 'el', 'la', 'de', 'del')
        p_clean = re.sub(r"\s+", " ", p.lower()).strip()
        c_clean = re.sub(r"\s+", " ", c.lower()).strip()
        articulos_prefijo = ["un ", "una ", "el ", "la ", "los ", "las ", "de ", "del ", "al "]
        for art in articulos_prefijo:
            if c_clean == art + p_clean:
                return True

        # 6. Si corrección y palabra son idénticas
        if p_clean == c_clean:
            return True

        return False

    def auditar_campos(self, items_atomicos, tamano_lote=15):
        """
        Recibe una lista de notas atómicas con sus campos limpios.
        Revisa cada campo usando el LLM con instrucciones estrictas anti-alucinación.
        Retorna únicamente hallazgos ortográficos y tipográficos legítimos.
        """
        self.recargar_reglas()
        hallazgos = []

        sub_tareas = []
        for item in items_atomicos:
            for nombre_campo, texto in item["campos"].items():
                if len(texto.strip()) > 5:
                    sub_tareas.append({
                        "id": len(sub_tareas) + 1,
                        "uid": item["uid"],
                        "url": item["url"],
                        "seccion": item["seccion"],
                        "posicion": item["posicion"],
                        "campo": nombre_campo,
                        "texto": texto
                    })

        total = len(sub_tareas)
        if total == 0:
            return []

        client = Groq(api_key=self.api_key)
        total_lotes = (total + tamano_lote - 1) // tamano_lote

        system_prompt = (
            "Eres un corrector ortográfico, gramatical y tipográfico de élite para el periódico El Tiempo (Colombia).\n"
            "Tu objetivo es AUDITAR RIGUROSAMENTE los textos de la portada para detectar errores que dañen la credibilidad periodística.\n\n"
            "ERRORES QUE DEBES DETECTAR Y REPORTAR:\n"
            "1. Erratas y dedazos: Palabras mal escritas, letras cambiadas, omitidas o agregadas (ej. 'gobieno', 'desiciones', 'espectativa', 'conección').\n"
            "2. Tildes faltantes o mal puestas: Palabras agudas, llanas o esdrújulas sin su tilde RAE obligatoria, incluyendo palabras en mayúsculas o títulos (ej. 'Fiscalia' -> 'Fiscalía', 'anuncio' (pretérito) -> 'anunció', 'energia' -> 'energía', 'tambien' -> 'también', 'situacion' -> 'situación', 'bogota' -> 'Bogotá', 'pais' -> 'país', 'dia' -> 'día', 'mas' (adverbio) -> 'más').\n"
            "3. Palabras pegadas accidentalmente por error tipográfico (ej. 'enel' -> 'en el', 'elAeropuerto' -> 'el Aeropuerto', 'dela' -> 'de la').\n"
            "4. Palabras duplicadas por error de tipeo (ej. 'en en', 'de de', 'que que').\n"
            "5. Concordancia rota o sintaxis rota evidente (ej. 'las presidente', 'un reformas').\n\n"
            "REGLAS NEGATIVAS (NO REPORTAR):\n"
            "- NO reportes nombres propios legítimos, apellidos, marcas, empresas, topónimos o siglas oficiales (ej. Petro, Uribe, Lula, DIAN, DANE, CTI, EE. UU., Sincelejo, Ecopetrol, William Vélez, Boyacá, Cali, MinSalud).\n"
            "- NO sugieras agregar artículos ('el', 'la', 'un') en titulares sintéticos de prensa.\n"
            "- NO cambies números o cifras a palabras ni critiques expresiones cuantitativas válidas.\n"
            "- Si el texto está correcto y no contiene errores indiscutibles, no generes hallazgos.\n\n"
            "FORMATO DE RESPUESTA:\n"
            "Responde estrictamente en formato JSON con la siguiente estructura:\n"
            '{"hallazgos": [{"id_texto": <numero_id_del_texto>, "palabra_erronea": "<palabra_exacta_como_aparece>", "correccion": "<forma_correcta>", "tipo_error": "ortografia|tipeo|tilde|sintaxis", "explicacion": "<motivo claro y conciso>"}]}\n'
            'Si todos los textos están impecables, responde exactamente: {"hallazgos": []}'
        )

        for idx_lote, i in enumerate(range(0, total, tamano_lote), start=1):
            lote = sub_tareas[i:i + tamano_lote]
            lineas = [f"[ID: {t['id']}]: \"{t['texto']}\"" for t in lote]

            print(f"  [Agente 3: Corrector] Evaluando lote {idx_lote}/{total_lotes} ({len(lote)} textos)...", end="\r")

            for reintento in range(3):
                try:
                    completion = client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": "Audita minuciosamente estos textos de la portada:\n\n" + "\n".join(lineas)}
                        ],
                        temperature=0.0,
                        max_completion_tokens=2048,
                        response_format={"type": "json_object"},
                        stream=False
                    )
                    raw_content = completion.choices[0].message.content

                    if raw_content:
                        parsed = json.loads(raw_content)
                        items_encontrados = parsed.get("hallazgos", []) if isinstance(parsed, dict) else []

                        mapa_lote = {t["id"]: t for t in lote}
                        for h in items_encontrados:
                            tid = h.get("id_texto") or h.get("id")
                            palabra = h.get("palabra_erronea", "").strip()
                            correccion = h.get("correccion", "").strip()

                            if not palabra or self._es_palabra_excluida(palabra):
                                continue

                            # Intentar buscar la nota por id o por coincidencia textual en el lote
                            meta = mapa_lote.get(tid)
                            palabra_clean = re.sub(r"^[^\wáéíóúñÁÉÍÓÚÑ]+|[^\wáéíóúñÁÉÍÓÚÑ]+$", "", palabra.lower())

                            if not meta or (palabra_clean and palabra_clean not in meta["texto"].lower()):
                                for cand in lote:
                                    if palabra_clean and palabra_clean in cand["texto"].lower():
                                        meta = cand
                                        break

                            if meta:
                                if self._es_hallazgo_invalido(palabra, correccion, meta["texto"]):
                                    continue

                                hallazgos.append({
                                    "uid": meta["uid"],
                                    "url": meta["url"],
                                    "seccion": meta["seccion"],
                                    "posicion": meta["posicion"],
                                    "campo": meta["campo"],
                                    "texto_completo": meta["texto"],
                                    "palabra_erronea": palabra,
                                    "correccion": correccion,
                                    "tipo_error": h.get("tipo_error", "ortografia"),
                                    "explicacion": h.get("explicacion", "")
                                })
                    break
                except Exception as api_err:
                    if reintento < 2:
                        time.sleep(2 * (reintento + 1))
                    else:
                        print(f"\n[Agente 3: Corrector] ✘ Advertencia en lote {idx_lote}: {api_err}")

            time.sleep(0.3)

        return hallazgos
