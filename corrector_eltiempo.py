# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║        CORRECTOR ORTOGRÁFICO Y AUDITOR SEO - EL TIEMPO               ║
║        Filtra publicidad y audita titulares editoriales con IA       ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import io
import os
import json
import time
import argparse
import re
from datetime import datetime

# UTF-8 en consola de Windows
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

import requests
from bs4 import BeautifulSoup
from groq import Groq

import os

URL_DEFAULT = "https://www.eltiempo.com/"
GROQ_API_KEY_DEFAULT = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3-8b")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

# Palabras clave en clases, IDs y atributos que indican contenido comercial o publicitario
PATRONES_PUBLICIDAD = [
    "patrocinado", "publi", "comercial", "anuncio", "advertisement",
    "sponsor", "ad-", "banner", "native-ad", "promocionado",
    "outbrain", "taboola", "c-articulo--patrocinado", "c-board-negocio",
    "contenido publicitario", "redacción comercial", "brand studio",
    "powerball", "lotto", "juegos", "horoscopo", "club-vivamos", "suscribete"
]

PATRONES_PURGA = [
    "modal", "popup", "newsletter", "boletin", "subscription", "suscribete",
    "c-banner", "banner", "ad-container", "outbrain", "taboola", "c-board-negocio",
    "audio-player", "social-share", "compartir", "tooltip", "c-usuario", "msg-copy",
    "sr-only", "c-detail__media__thumb__icon", "c-articulo__detalle", "c-story__byline",
    "c-story__author", "c-articulo--patrocinado", "c-tag", "c-badge", "kicker", "volanta"
]


class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    GRAY    = "\033[90m"
    WHITE   = "\033[97m"


def extraer_titulares_y_seo(url):
    """Extrae exclusivamente los titulares editoriales y metadatos SEO del Home."""
    print(f"\n{Color.CYAN}⟳ Descargando contenido de: {url}{Color.RESET}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
    except Exception as e:
        print(f"{Color.RED}✘ Error de conexión: {e}{Color.RESET}")
        return []

    html = resp.content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    elementos = []
    vistos = set()

    def registrar(categoria, texto, selector=""):
        texto = re.sub(r"\s+", " ", texto.strip())
        if texto and texto not in vistos and len(texto) >= 10:
            vistos.add(texto)
            elementos.append({
                "id": len(elementos) + 1,
                "categoria": categoria,
                "texto": texto,
                "selector": selector,
            })

    # 1. Metadatos SEO (Head)
    tag_title = soup.find("title")
    if tag_title and tag_title.get_text().strip():
        registrar("SEO: <title>", tag_title.get_text(), "<title>")

    for meta in soup.find_all("meta"):
        attr = (meta.get("name") or meta.get("property") or "").lower()
        contenido = meta.get("content", "").strip()
        if not contenido:
            continue
        if attr in ("description", "og:description"):
            if len(contenido) > 20:
                registrar("SEO: Meta Description", contenido, f'meta[{attr}]')
                break

    # 2. Purgar scripts, estilos y ruido
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "header", "footer", "nav"]):
        tag.decompose()

    for trash in soup.find_all(class_=lambda c: c and any(p in str(c).lower() for p in PATRONES_PURGA)):
        trash.decompose()

    # 3. Titulares y Bajadas
    articulos = soup.find_all("article")
    for art in articulos:
        txt_art = art.get_text().lower()
        if any(p in txt_art for p in ["contenido publicitario", "patrocinado por", "redacción comercial", "brand studio"]):
            continue

        h_tag = art.find(["h1", "h2", "h3", "h4"])
        if not h_tag:
            continue

        for sub_kicker in h_tag.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["kicker", "badge", "tag", "volanta"])):
            sub_kicker.decompose()

        titular = re.sub(r"\s+", " ", h_tag.get_text()).strip()
        titular = re.sub(r"^(En vivo|Exclusivo|Análisis|Opinión|Video|Fotogalería|Podcast|Especial|Atención)\s*:\s*", "", titular, flags=re.I).strip()

        if len(titular) >= 15:
            registrar(f"Titular {h_tag.name.upper()}", titular, h_tag.name)

        # Bajada explícita
        bajada_tag = art.find(class_=lambda c: c and any(k in str(c).lower() for k in ["c-articulo__resumen", "epigrafe", "bajada", "c-story__lead", "c-story__summary"]))
        if bajada_tag:
            b_txt = re.sub(r"\s+", " ", bajada_tag.get_text()).strip()
            if len(b_txt) > 20 and b_txt != titular and not any(ign in b_txt.lower() for ign in ["foto:", "crédito:", "por:", "redacción", "afp", "efe"]):
                registrar("Bajada / Epígrafe", b_txt, "resumen")

    print(f"{Color.GREEN}✔ Extracción exitosa: {len(elementos)} textos editoriales limpios.{Color.RESET}")
    return elementos


def es_hallazgo_invalido(palabra, correccion, texto_original):
    p = palabra.strip()
    c = correccion.strip()

    if p.lower() not in texto_original.lower():
        return True
    if re.search(r"^\$?\d+([.,]\d+)*%?$", p):
        return True
    if any(ext in p.lower() for ext in [".com", ".co", "http", "www.", ".org"]):
        return True
    if len(re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ]", "", p)) < 2:
        return True

    p_clean = re.sub(r"\s+", " ", p.lower()).strip()
    c_clean = re.sub(r"\s+", " ", c.lower()).strip()
    for art in ["un ", "una ", "el ", "la ", "los ", "las ", "de ", "del ", "al "]:
        if c_clean == art + p_clean:
            return True

    if p_clean == c_clean:
        return True

    return False


def auditar_con_ia(elementos, api_key, tamano_lote=15):
    """Audita los fragmentos editoriales con IA usando reglas estrictas anti-falsos positivos."""
    print(f"\n{Color.MAGENTA}⚡ Analizando ortografía editorial con IA ({GROQ_MODEL})...{Color.RESET}")
    resultados_ia = []
    total = len(elementos)
    client = Groq(api_key=api_key)

    total_lotes = (total + tamano_lote - 1) // tamano_lote

    system_prompt = (
        "Eres un corrector ortográfico y tipográfico estricto para el periódico El Tiempo (Colombia).\n"
        "Tu ÚNICA misión es detectar ERRORES GRAVES DE ORTOGRAFÍA, DEDAZOS Y PALABRAS MAL ESCRITAS.\n\n"
        "CRITERIOS DE ERROR GRAVE (SÓLO REPORTAR ESTOS):\n"
        "1. Palabras mal escritas, erratas o dedazos evidentes (ej. 'gobieno' -> 'gobierno', 'desiciones' -> 'decisiones').\n"
        "2. Palabras pegadas accidentalmente (ej. 'elAeropuerto' -> 'el Aeropuerto', 'enel' -> 'en el').\n"
        "3. Palabras duplicadas por error tipográfico (ej. 'en en', 'de de').\n"
        "4. Tildes faltantes en palabras comunes del español donde sea un error ortográfico indiscutible según la RAE.\n\n"
        "REGLAS NEGATIVAS ESTRICTAS (TOTALMENTE PROHIBIDO REPORTAR):\n"
        "- NO reportes nombres propios, apellidos, marcas, empresas, topónimos, instituciones o siglas (ej. Petro, Lula da Silva, Bolsonaro, De La Espriella, Baloto, Holiday Inn, Eln, DIAN, DANE, CTI, EE. UU., Sincelejo, Ecopetrol).\n"
        "- NO sugieras añadir artículos ('un', 'el', 'la', 'de') en titulares. El estilo periodístico sintético es válido.\n"
        "- NO cambies números/cifras a palabras (ej. '7 países', '61.600 millones' es correcto).\n"
        "- NO sugieras cambios de redacción o estilo a menos que la frase sea totalmente ininteligible.\n"
        "- Si el texto está correcto, NO generes ningún hallazgo.\n\n"
        "Formato JSON de respuesta:\n"
        '{"hallazgos": [{"id": <numero_id>, "palabra_erronea": "<palabra_exacta>", "correccion": "<correccion>", "tipo_error": "ortografia|tipeo|tilde|redaccion_grave", "explicacion": "<motivo>"}]}\n'
        'Si no hay errores graves indiscutibles, responde exactamente: {"hallazgos": []}'
    )

    for i in range(0, total, tamano_lote):
        lote = elementos[i:i + tamano_lote]
        num_lote = (i // tamano_lote) + 1
        print(f"  {Color.CYAN}⟳ Evaluando lote editorial {num_lote}/{total_lotes} ({len(lote)} textos)...{Color.RESET}", end="\r", flush=True)

        lineas_usuario = [f"[{item['id']}]: \"{item['texto']}\"" for item in lote]

        for reintento in range(3):
            try:
                completion = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "Revisa estos textos de portada:\n\n" + "\n".join(lineas_usuario)}
                    ],
                    temperature=0.0,
                    max_completion_tokens=2048,
                    response_format={"type": "json_object"}
                )
                raw_content = completion.choices[0].message.content
                if raw_content:
                    parsed = json.loads(raw_content)
                    mapa_lote = {item["id"]: item for item in lote}

                    for h in parsed.get("hallazgos", []):
                        tid = h.get("id")
                        palabra = h.get("palabra_erronea", "").strip()
                        correccion = h.get("correccion", "").strip()

                        if not palabra:
                            continue

                        titular = mapa_lote.get(tid)
                        if not titular or palabra.lower() not in titular["texto"].lower():
                            for cand in lote:
                                if palabra.lower() in cand["texto"].lower():
                                    titular = cand
                                    break

                        if titular:
                            if es_hallazgo_invalido(palabra, correccion, titular["texto"]):
                                continue

                            resultados_ia.append({
                                "id": titular["id"],
                                "categoria": titular["categoria"],
                                "selector": titular["selector"],
                                "texto": titular["texto"],
                                "palabra_erronea": palabra,
                                "correccion": correccion,
                                "motivo": h.get("explicacion", ""),
                            })
                break
            except Exception as e:
                if reintento < 2:
                    time.sleep(2 * (reintento + 1))
                else:
                    print(f"\n{Color.YELLOW}Advertencia en lote {num_lote}: {e}{Color.RESET}")

        time.sleep(0.3)

    print(f"\n{Color.GREEN}✔ Auditoría completada sobre los {total} textos editoriales.{Color.RESET}\n")
    return resultados_ia


def mostrar_reporte(hallazgos, url, total_analizados, duracion):
    sep = "═" * 72
    print(f"{Color.BOLD}{Color.MAGENTA}{sep}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  INFORME DE ORTOGRAFÍA EN TITULARES Y SEO: EL TIEMPO{Color.RESET}")
    print(f"{Color.GRAY}  Objetivo  : {url}")
    print(f"  Motor IA  : Groq Cloud ({GROQ_MODEL})")
    print(f"  Fecha     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Muestreo  : {total_analizados} textos analizados en {duracion:.2f} seg{Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}{sep}{Color.RESET}\n")

    if not hallazgos:
        print(f"  {Color.GREEN}{Color.BOLD}✔ ¡Redacción impecable! No se detectaron errores ortográficos graves en la portada.{Color.RESET}\n")
        print(f"{Color.BOLD}{Color.MAGENTA}{sep}{Color.RESET}\n")
        return

    print(f"  {Color.RED}{Color.BOLD}Se encontraron {len(hallazgos)} observación(es) en los textos:{Color.RESET}\n")

    for idx, h in enumerate(hallazgos, 1):
        color_cat = Color.RED if "SEO" in h["categoria"] or "H1" in h["categoria"] else Color.YELLOW
        print(f"  {Color.BOLD}{color_cat}[{idx:02d}] {h['categoria']}{Color.RESET} {Color.GRAY}({h['selector']}){Color.RESET}")
        print(f"      \"{h['texto']}\"")
        print(f"      {Color.RED}✖ Error detectado:{Color.RESET} {Color.BOLD}{h['palabra_erronea']}{Color.RESET} -> Sugerencia IA: {Color.GREEN}{h['correccion']}{Color.RESET}")
        if h.get("motivo"):
            print(f"      {Color.GRAY}ℹ Motivo: {h['motivo']}{Color.RESET}")
        print(f"  {Color.GRAY}{'-'*70}{Color.RESET}")

    print(f"\n{Color.BOLD}{Color.MAGENTA}{sep}{Color.RESET}\n")


def exportar_json(hallazgos, url, total_analizados, duracion):
    nombre_archivo = f"reporte_ortografia_editorial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    datos = {
        "url": url,
        "motor": f"Groq IA ({GROQ_MODEL})",
        "tipo_analisis": "Titulares editoriales y SEO (Publicidad excluida)",
        "fecha": datetime.now().isoformat(),
        "duracion_segundos": round(duracion, 2),
        "total_titulares_analizados": total_analizados,
        "total_errores_detectados": len(hallazgos),
        "hallazgos": hallazgos,
    }
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"{Color.GREEN}✔ Archivo exportado: {nombre_archivo}{Color.RESET}\n")
    return nombre_archivo


def main():
    parser = argparse.ArgumentParser(description="Auditor ortográfico de titulares editoriales para El Tiempo")
    parser.add_argument("--url", default=URL_DEFAULT, help="URL de la página a auditar")
    parser.add_argument("--api-key", default=os.environ.get("GROQ_API_KEY", GROQ_API_KEY_DEFAULT), help="API Key de Groq")
    parser.add_argument("--export", action="store_true", help="Exportar automáticamente a JSON")
    args = parser.parse_args()

    inicio = time.time()
    elementos = extraer_titulares_y_seo(args.url)

    if not elementos:
        sys.exit(1)

    hallazgos = auditar_con_ia(elementos, args.api_key)
    duracion = time.time() - inicio

    mostrar_reporte(hallazgos, args.url, len(elementos), duracion)

    if args.export or hallazgos:
        exportar_json(hallazgos, args.url, len(elementos), duracion)


if __name__ == "__main__":
    main()
