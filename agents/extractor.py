# -*- coding: utf-8 -*-
"""
Agente 2: Extractor de Contenido Editorial
Descompone cada noticia de portada y metadatos SEO en campos atómicos limpios:
- Titular periodístico
- Bajada / Epígrafe editorial
- Balazos / Viñetas
- Metadatos SEO del Home (<title>, meta description)
Las URLs se conservan únicamente como enlace de referencia y NUNCA se auditan ortográficamente.
"""

import re


class ExtractorAgent:
    def __init__(self):
        pass

    def procesar_lote(self, bloques):
        """
        Transforma los bloques del crawler en estructuras atómicas de campos limpios.
        """
        resultado = []
        for b in bloques:
            campos = {}

            tipo = b.get("tipo", "articulo")
            titular = b.get("titular", "").strip()

            if tipo == "seo":
                pos = b.get("posicion", "").lower()
                nombre_campo = "seo_meta_description" if "meta" in pos else "seo_title"
                if titular and len(titular) >= 8:
                    campos[nombre_campo] = re.sub(r"\s+", " ", titular)
            else:
                if titular and len(titular) >= 15:
                    campos["titular"] = re.sub(r"\s+", " ", titular)

                bajada = b.get("bajada", "").strip()
                if bajada and len(bajada) >= 20:
                    campos["bajada"] = re.sub(r"\s+", " ", bajada)

                vinetas = b.get("vinetas", [])
                for idx, vin in enumerate(vinetas):
                    v_clean = re.sub(r"\s+", " ", vin.strip())
                    if len(v_clean) >= 20:
                        campos[f"balazo_{idx+1}"] = v_clean

            if campos:
                resultado.append({
                    "uid": b.get("uid", ""),
                    "url": b.get("url", ""),
                    "seccion": b.get("seccion", "Portada General"),
                    "posicion": b.get("posicion", "TITULAR"),
                    "campos": campos
                })

        return resultado
