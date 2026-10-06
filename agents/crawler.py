# -*- coding: utf-8 -*-
"""
Agente 1: Rastreador de Portada (Crawler)
Descarga y analiza exhaustivamente la portada (Home) de El Tiempo:
- Metadatos SEO del Home (<title> y meta description)
- Artículos editoriales reales (Titulares H1 a H4, Bajadas / Epígrafes)
- Purgado estricto de anuncios, autores, créditos de foto, etiquetas de UI y modales.
"""

import hashlib
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from config import URL_TARGET, CACHE_STATE_FILE

HEADERS_CRAWLER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

# URLs que corresponden a utilidades del portal o publicidad (NO contenido editorial)
URL_EXCLUIDAS = [
    "zona-usuario", "boletines", "club-vivamos", "suscribete", "suscripciones",
    "iniciar-sesion", "registro", "terminos", "politica-de-privacidad", "publicidad",
    "comercial", "patrocinado", "servicios.eltiempo", "juegos", "horoscopo",
    "powerball", "lotto", "brand-studio"
]

# Clases y selectores de elementos de interfaz técnica, popups y ruido
PATRONES_PURGA = [
    "modal", "popup", "newsletter", "boletin", "subscription", "suscribete",
    "c-banner", "banner", "ad-container", "outbrain", "taboola", "c-board-negocio",
    "audio-player", "social-share", "compartir", "tooltip", "c-usuario", "msg-copy",
    "sr-only", "c-detail__media__thumb__icon", "c-articulo__detalle", "c-story__byline",
    "c-story__author", "c-articulo--patrocinado", "c-tag", "c-badge", "kicker", "volanta"
]


class CrawlerAgent:
    def __init__(self, cache_file=CACHE_STATE_FILE):
        self.cache_file = cache_file
        self.cache = self._cargar_cache()

    def _cargar_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _guardar_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando cache de rastreador: {e}")

    def sondeo_y_diff(self, url=URL_TARGET, forzar_completo=False):
        """
        Descarga la portada completa, limpia popups y elementos de UI,
        y extrae metadatos SEO y notas editoriales reales.
        """
        try:
            resp = requests.get(url, headers=HEADERS_CRAWLER, timeout=25)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Agente 1: Rastreador] ✘ Error descargando home: {e}")
            return [], 0, False

        html = resp.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        bloques_totales = []

        # 1. Metadatos SEO del Home (<title> y meta description)
        if soup.title and soup.title.get_text().strip():
            title_text = re.sub(r"\s+", " ", soup.title.get_text()).strip()
            if len(title_text) > 10:
                t_hash = hashlib.sha256(title_text.encode("utf-8")).hexdigest()
                bloques_totales.append({
                    "uid": "seo_home_title",
                    "tipo": "seo",
                    "seccion": "SEO Home",
                    "posicion": "TITLE",
                    "titular": title_text,
                    "bajada": "",
                    "vinetas": [],
                    "url": url,
                    "hash": t_hash
                })

        for meta in soup.find_all("meta"):
            attr = (meta.get("name") or meta.get("property") or "").lower()
            content = meta.get("content", "").strip()
            if not content:
                continue
            if attr in ("description", "og:description"):
                desc_text = re.sub(r"\s+", " ", content).strip()
                if len(desc_text) > 20:
                    d_hash = hashlib.sha256(desc_text.encode("utf-8")).hexdigest()
                    bloques_totales.append({
                        "uid": f"seo_home_{attr.replace(':', '_')}",
                        "tipo": "seo",
                        "seccion": "SEO Home",
                        "posicion": "META DESCRIPTION",
                        "titular": desc_text,
                        "bajada": "",
                        "vinetas": [],
                        "url": url,
                        "hash": d_hash
                    })
                    break

        # 2. Purgar scripts, estilos, iframes, navegadores, headers, footers y elementos de UI
        for tag in soup(["script", "style", "noscript", "svg", "iframe", "header", "footer", "nav"]):
            tag.decompose()

        for trash in soup.find_all(class_=lambda c: c and any(p in str(c).lower() for p in PATRONES_PURGA)):
            trash.decompose()

        # 3. RASTREO PROFUNDO: Extraer Artículos y Secciones Editoriales de toda la Portada
        vistos_titulares = set()

        def inferir_seccion(url_item):
            if not url_item:
                return "Portada General"
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url_item)
                if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
                    return "Video / Multimedia"
                partes = [p for p in parsed.path.split("/") if p]
                if partes:
                    slug = partes[0].lower().replace("-", " ")
                    return slug.capitalize()
            except Exception:
                pass
            return "Portada General"

        # Fase 3A: Buscar contenedores de artículos (<article> y divs/sections con clases editoriales)
        contenedores = soup.find_all(lambda tag: tag.name in ["article", "div", "section", "li"] and (
            tag.name == "article" or
            (tag.get("class") and any(k in " ".join(tag.get("class")).lower() for k in [
                "c-articulo", "c-story", "c-card", "c-nota", "article-card", "c-destacado", "c-news-item"
            ]))
        ))

        for idx, art in enumerate(contenedores):
            art_text = art.get_text().lower()
            if any(p in art_text for p in [
                "contenido publicitario", "patrocinado por", "redacción comercial",
                "brand studio", "publirreportaje", "powerball", "lotto"
            ]):
                continue

            # Buscar encabezado o título
            h_tag = art.find(["h1", "h2", "h3", "h4", "h5"])
            if not h_tag:
                h_tag = art.find(class_=lambda c: c and any(k in str(c).lower() for k in ["titulo", "title", "heading"]))
            if not h_tag:
                continue

            # Limpiar etiquetas o kickers residuales
            for sub_kicker in h_tag.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["kicker", "badge", "tag", "volanta"])):
                sub_kicker.decompose()

            titular = re.sub(r"\s+", " ", h_tag.get_text()).strip()
            titular = re.sub(r"^(En vivo|Exclusivo|Análisis|Opinión|Video|Fotogalería|Podcast|Especial|Atención)\s*:\s*", "", titular, flags=re.I).strip()

            clave_tit = titular.lower()
            if len(titular) < 15 or clave_tit in vistos_titulares:
                continue

            if any(b in clave_tit for b in ["copiada", "portapapeles", "suscríbete", "inicia sesión", "reproducir video"]):
                continue

            # Extraer URL canónica de la noticia
            a_tag = h_tag.find("a", href=True) or art.find("a", href=True)
            url_nota = ""
            descartar = False
            if a_tag and a_tag.get("href"):
                href = a_tag["href"].strip()
                if any(exc in href.lower() for exc in URL_EXCLUIDAS):
                    descartar = True
                else:
                    url_nota = href if href.startswith("http") else "https://www.eltiempo.com" + href

            if descartar:
                continue

            vistos_titulares.add(clave_tit)
            seccion = inferir_seccion(url_nota)

            if len(bloques_totales) < 8 and seccion in ["Portada General", "Politica", "Justicia", "Mundo", "Economia"]:
                seccion = f"Apertura ({seccion})"

            # Extraer bajada / epígrafe
            bajada = ""
            p_bajada = art.find(class_=lambda c: c and any(k in str(c).lower() for k in [
                "c-articulo__resumen", "epigrafe", "bajada", "c-story__lead", "c-story__summary", "lead", "summary"
            ]))
            if p_bajada:
                b_txt = re.sub(r"\s+", " ", p_bajada.get_text()).strip()
                if len(b_txt) >= 20 and b_txt.lower() != clave_tit and not any(ign in b_txt.lower() for ign in ["foto:", "crédito:", "por:", "redacción", "afp", "efe", "reuters"]):
                    bajada = b_txt

            # Extraer viñetas / balazos
            vinetas = []
            for li in art.find_all("li"):
                li_txt = re.sub(r"\s+", " ", li.get_text()).strip()
                if len(li_txt) >= 25 and li_txt.lower() != clave_tit and (not bajada or li_txt.lower() != bajada.lower()):
                    if not any(m in li_txt.lower() for m in ["compartir", "guardar", "comentar", "seguir"]):
                        vinetas.append(li_txt)

            raw_full = f"{titular}|{bajada}|{'|'.join(vinetas)}"
            b_hash = hashlib.sha256(raw_full.encode("utf-8")).hexdigest()

            bloques_totales.append({
                "uid": url_nota or f"nota_{idx}",
                "tipo": "articulo",
                "seccion": seccion,
                "posicion": h_tag.name.upper() if hasattr(h_tag, "name") else "TITULAR",
                "titular": titular,
                "bajada": bajada,
                "vinetas": vinetas,
                "url": url_nota or f"https://www.eltiempo.com/#nota_{idx}",
                "hash": b_hash
            })

        # Fase 3B: Escaneo complementario de todos los H1..H5 y enlaces editoriales no capturados
        for h in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
            t = re.sub(r"\s+", " ", h.get_text()).strip()
            t = re.sub(r"^(En vivo|Exclusivo|Análisis|Opinión|Video|Fotogalería|Podcast|Especial|Atención)\s*:\s*", "", t, flags=re.I).strip()
            clave = t.lower()
            if len(t) < 15 or clave in vistos_titulares:
                continue
            if any(b in clave for b in ["copiada", "portapapeles", "suscríbete", "inicia sesión"]):
                continue

            a = h.find("a", href=True) or h.find_parent("a", href=True)
            url_nota = ""
            if a and a.get("href"):
                href = a["href"].strip()
                if any(exc in href.lower() for exc in URL_EXCLUIDAS):
                    continue
                url_nota = href if href.startswith("http") else "https://www.eltiempo.com" + href

            vistos_titulares.add(clave)
            seccion = inferir_seccion(url_nota)

            bloques_totales.append({
                "uid": url_nota or f"extra_{len(bloques_totales)}",
                "tipo": "articulo",
                "seccion": seccion,
                "posicion": h.name.upper(),
                "titular": t,
                "bajada": "",
                "vinetas": [],
                "url": url_nota or f"https://www.eltiempo.com/#extra_{len(bloques_totales)}",
                "hash": hashlib.sha256(t.encode("utf-8")).hexdigest()
            })

        # Fase 3C: Enlaces editoriales profundos de noticias (-id) que no fueron envueltos en encabezados
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if re.search(r"-\d{5,8}$", href):
                t = re.sub(r"\s+", " ", a.get_text()).strip()
                t = re.sub(r"^(En vivo|Exclusivo|Análisis|Opinión|Video|Fotogalería|Podcast|Especial|Atención)\s*:\s*", "", t, flags=re.I).strip()
                clave = t.lower()
                if len(t) >= 18 and clave not in vistos_titulares:
                    if not any(ign in clave for ign in ["suscríbete", "inicia sesión", "compartir", "portapapeles"]):
                        vistos_titulares.add(clave)
                        url_nota = href if href.startswith("http") else "https://www.eltiempo.com" + href
                        seccion = inferir_seccion(url_nota)
                        bloques_totales.append({
                            "uid": url_nota,
                            "tipo": "articulo",
                            "seccion": seccion,
                            "posicion": "ENLACE EDITORIAL",
                            "titular": t,
                            "bajada": "",
                            "vinetas": [],
                            "url": url_nota,
                            "hash": hashlib.sha256(t.encode("utf-8")).hexdigest()
                        })

        # Evaluar cambios contra cache
        nuevo_cache = {b["uid"]: b["hash"] for b in bloques_totales}
        bloques_modificados = []

        if forzar_completo or not self.cache:
            bloques_modificados = list(bloques_totales)
        else:
            for b in bloques_totales:
                uid = b["uid"]
                if uid not in self.cache or self.cache[uid] != b["hash"]:
                    bloques_modificados.append(b)

        hubo_cambios = len(bloques_modificados) > 0
        if hubo_cambios:
            self.cache = nuevo_cache
            self._guardar_cache()

        return bloques_modificados, bloques_totales, hubo_cambios
