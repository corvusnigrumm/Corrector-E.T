# Plan de Implementación y Despliegue en Render (On Render)

Este documento describe la arquitectura, preparación y pasos paso a paso para desplegar el **Corrector Editorial El Tiempo (Sistema Multi-Agente)** en la nube con [Render](https://render.com).

---

## 1. Arquitectura en Render

```
                                  [ Navegador del Editor ]
                                             │
                                             ▼
                               https://corrector-et.onrender.com
                                             │
                   ┌─────────────────────────┴─────────────────────────┐
                   │               Render Web Service                 │
                   │                                                   │
                   │   ┌───────────────────────────────────────────┐   │
                   │   │    Dashboard Web (HTTP API + UI)          │   │
                   │   │    - Host: 0.0.0.0, Port: $PORT           │   │
                   │   │    - Rutas: /, /api/incidencias, etc.     │   │
                   │   └─────────────────────┬─────────────────────┘   │
                   │                         │                         │
                   │   ┌─────────────────────▼─────────────────────┐   │
                   │   │    Orquestador Multi-Agente (Daemon)      │   │
                   │   │    - Crawler -> Extractor -> Corrector    │   │
                   │   │    - Triage -> Notifier                   │   │
                   │   │    - Sondeo recurrente cada 90 seg        │   │
                   │   └─────────────────────┬─────────────────────┘   │
                   │                         │                         │
                   │   ┌─────────────────────▼─────────────────────┐   │
                   │   │    Persistencia (/storage)                │   │
                   │   │    - cache_state.json                     │   │
                   │   │    - feedback_rules.json (whitelist)      │   │
                   │   │    - audit_history.json                   │   │
                   │   └───────────────────────────────────────────┘   │
                   └───────────────────────────────────────────────────┘
```

---

## 2. Archivos Clave Creados en el Proyecto

1. [`requirements.txt`](file:///c:/Users/photo/Downloads/DESCARGAS/DESCARGAS/PROYECTOS/Corrector%20E.T/requirements.txt):
   - `requests>=2.31.0`
   - `beautifulsoup4>=4.12.0`
   - `groq>=0.11.0`
2. [`render.yaml`](file:///c:/Users/photo/Downloads/DESCARGAS/DESCARGAS/PROYECTOS/Corrector%20E.T/render.yaml):
   - Blueprint de infraestructura con variables de entorno y comandos de compilación/arranque.
3. [`Procfile`](file:///c:/Users/photo/Downloads/DESCARGAS/DESCARGAS/PROYECTOS/Corrector%20E.T/Procfile):
   - Definición del proceso principal: `web: python run_monitor.py`.
4. [`config.py`](file:///c:/Users/photo/Downloads/DESCARGAS/DESCARGAS/PROYECTOS/Corrector%20E.T/config.py):
   - Adaptado dinámicamente para leer `PORT` y enlazar en `0.0.0.0` cuando corre en Render.

---

## 3. Pasos para el Despliegue en Render

### Paso 1: Subir el proyecto a GitHub o GitLab
1. Inicializa el repositorio si no lo has hecho:
   ```bash
   git init
   git add .
   git commit -m "feat: preparación para despliegue en Render y ejecutable local"
   ```
2. Crea un repositorio en tu cuenta de GitHub (ej. `corrector-el-tiempo`) y conéctalo:
   ```bash
   git remote add origin https://github.com/TU_USUARIO/corrector-el-tiempo.git
   git branch -M main
   git push -u origin main
   ```

### Paso 2: Crear el Web Service en Render
1. Inicia sesión en [Render Dashboard](https://dashboard.render.com).
2. Haz clic en **New +** y selecciona **Web Service**.
3. Conecta tu repositorio de GitHub `corrector-el-tiempo`.
4. Configura los parámetros básicos:
   - **Name**: `corrector-editorial`
   - **Region**: Oregon (US West) o Frankfurt (EU)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run_monitor.py`
   - **Instance Type**: `Free`

### Paso 3: Configurar Variables de Entorno (Environment Variables)
En la sección **Environment Variables** de Render, añade:

| Variable | Valor | Descripción |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | *(Tu API Key de Groq)* | Clave para el modelo LLM |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Modelo LLM utilizado |
| `CRAWL_INTERVAL_SECONDS` | `90` | Frecuencia de escaneo (segundos) |
| `PYTHON_VERSION` | `3.12.0` | Versión de Python en Render |

> [!NOTE]
> Render inyecta automáticamente la variable `PORT`. Nuestro `config.py` ya está programado para vincularse a `0.0.0.0:$PORT` de forma automática.

### Paso 4: Desplegar y Verificar
1. Presiona **Create Web Service**.
2. Render comenzará la compilación (`pip install`) y ejecutará `python run_monitor.py`.
3. Verás en los logs de Render:
   ```
   ==> Starting service with 'python run_monitor.py'
   ============================================================
     CORRECTOR EDITORIAL AUTOMATIZADO - EL TIEMPO
     Sistema Multi-Agente con IA
   ============================================================
   MESA DE CONTROL EDITORIAL EN VIVO
   Abre en tu navegador: http://0.0.0.0:10000
   ```
4. Render marcará el servicio como **Live** y te proporcionará una URL pública segura con SSL (ej. `https://corrector-editorial.onrender.com`).

---

## 4. Consideración sobre Persistencia (Storage en Render)

- **En el plan Free de Render**: El sistema de archivos es efímero. Cada vez que Render suspenda la instancia por inactividad (después de 15 minutos sin tráfico) o se haga un redeploy, los archivos en `storage/` se restablecerán a los iniciales.
- **Si requieres persistencia total en la nube**:
  1. **Opción A (Render Disk - Plan Starter $7/mes)**: Añadir un *Persistent Disk* en Render montado en `/opt/render/project/src/storage`.
  2. **Opción B (Base de Datos Gratuita)**: Reemplazar los archivos JSON de `storage/` por una base de datos ligera gratuita como **Supabase (PostgreSQL)** o **MongoDB Atlas**, o usar el servicio de PostgreSQL gratuito de Render.
  3. **Opción C (Uso con el script Ping)**: Configurar un monitor de salud gratuito (como UptimeRobot) haciendo ping cada 10 minutos a `https://corrector-editorial.onrender.com/` para mantener la instancia despierta continuamente en el plan Free.
