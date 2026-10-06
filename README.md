# 🦅 Corrector Editorial — Corvus Nigrum

Sistema multiagente de corrección ortográfica y editorial en tiempo real para **eltiempo.com**. Audita la portada completa cada 90 segundos usando IA (Groq LLM) y presenta los errores en un dashboard web editorial.

---

## 🚀 Despliegue en Render

### Paso 1 — Subir el repositorio a GitHub

```bash
git init
git add .
git commit -m "feat: Corrector Editorial Corvus Nigrum"
git remote add origin https://github.com/TU_USUARIO/corrector-editorial.git
git push -u origin main
```

> ⚠️ Asegúrate de que `.gitignore` excluya `es_full.txt` y la carpeta `storage/`.

### Paso 2 — Crear servicio en Render

1. Ve a [render.com](https://render.com) → **New Web Service**
2. Conecta tu repositorio de GitHub
3. Render detecta el `render.yaml` automáticamente
4. En la pestaña **Environment**, agrega:

| Variable | Valor |
|----------|-------|
| `GROQ_API_KEY` | Tu clave de Groq (consíguela en [console.groq.com](https://console.groq.com)) |

5. Haz clic en **Deploy**

### Paso 3 — Configurar Keep-Alive con UptimeRobot (gratis)

Para que el servicio nunca duerma en el plan gratuito:

1. Regístrate en [uptimerobot.com](https://uptimerobot.com) (gratuito)
2. **New Monitor** → HTTP(s)
3. URL: `https://TU-APP.onrender.com/ping`
4. Intervalo: **5 minutos**
5. Guardar

Esto hace que UptimeRobot pingee el endpoint `/ping` cada 5 minutos, manteniendo el servicio activo 24/7 sin costo adicional.

---

## 💻 Ejecución Local

### Requisitos
- Python 3.11+
- Clave API de Groq (gratis en [console.groq.com](https://console.groq.com))

### Instalación

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar la API key (Windows PowerShell)
$env:GROQ_API_KEY = "gsk_TU_CLAVE_AQUI"

# 3. Ejecutar
python run_monitor.py
```

El dashboard abre automáticamente en `http://localhost:5000`

### Con el EXE (Windows)
Simplemente ejecuta `CorrectorEditorial.exe`. La API key debe estar configurada como variable de entorno del sistema.

---

## 🤖 Agentes del Sistema

| # | Agente | Función |
|---|--------|---------|
| 1 | **Rastreador** | Descarga y parsea la portada completa de eltiempo.com |
| 2 | **Extractor** | Descompone cada noticia en campos atómicos (titular, bajada, viñetas, SEO) |
| 3 | **Corrector IA** | Envía los textos a Groq LLM para detección de errores ortográficos |
| 4 | **Triage** | Clasifica por severidad (Crítica/Media/Baja) y deduplica |
| 5 | **Notificador** | Persiste incidencias y las expone al dashboard web |

---

## 🔑 Variables de Entorno

| Variable | Requerida | Descripción | Default |
|----------|-----------|-------------|---------|
| `GROQ_API_KEY` | ✅ Sí | Clave API de Groq | — |
| `GROQ_MODEL` | No | Modelo de IA a usar | `qwen/qwen3-8b` |
| `CRAWL_INTERVAL_SECONDS` | No | Frecuencia de sondeo | `90` |
| `STORAGE_DIR` | No | Directorio de persistencia | `./storage` |
| `PORT` | No (Render lo inyecta) | Puerto del servidor web | `5000` |

---

## 📡 Endpoints API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Dashboard editorial |
| GET | `/ping` | Keep-alive (UptimeRobot) |
| GET | `/health` | Estado del sistema |
| GET | `/api/incidencias` | Cola de errores detectados |
| GET | `/api/home_audit` | Censo completo de la portada |
| GET | `/api/whitelist` | Diccionario editorial |
| POST | `/api/resolver` | Aceptar o descartar una incidencia |
| POST | `/api/trigger` | Forzar auditoría inmediata |
| POST | `/api/whitelist/add` | Agregar palabra al diccionario |
| POST | `/api/whitelist/remove` | Quitar palabra del diccionario |
