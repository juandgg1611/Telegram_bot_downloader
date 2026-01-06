import os
from pathlib import Path

# ============================================================================
# CONFIGURACIÓN BÁSICA
# ============================================================================

# Token del bot de Telegram (OBTENER DE @BotFather)
TELEGRAM_TOKEN = "8315169253:AAEHkDCqPayRQJxM6_isxBVf-7L4PFnrzkE"

# Límite de tamaño en bytes (1000MB)
MAX_FILE_SIZE = 1000 * 1024 * 1024

# Tiempo máximo de descarga en segundos
DOWNLOAD_TIMEOUT = 300

# ============================================================================
# RUTAS
# ============================================================================

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent.parent

# Directorio para descargas temporales
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Directorio para logs
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ============================================================================
# CONFIGURACIÓN yt-dlp
# ============================================================================

# Opciones para TikTok
TIKTOK_OPTIONS = {
    'format': 'best[height<=720][filesize<50M]',  # Máximo 720p y 50MB
    'outtmpl': str(DOWNLOAD_DIR / 'tiktok_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'socket_timeout': 30,
    'retries': 3,
    'fragment_retries': 3,
    'skip_unavailable_fragments': True,
}

# Opciones para YouTube (audio)
YOUTUBE_AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': str(DOWNLOAD_DIR / 'youtube_%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'writethumbnail': True,
    'embedthumbnail': True,
    'addmetadata': True,
    'socket_timeout': 30,
    'retries': 3,
}

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'simple': {
            'format': '%(levelname)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': str(LOG_DIR / 'bot.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ============================================================================
# MENSAJES DEL BOT
# ============================================================================

MESSAGES = {
    'welcome': """
🎬 **Bot Descargador de TikTok, YouTube e Instagram Reels diseñado por Juan Oberto**

📥 **Soportado:**
• TikTok videos (públicos)
• YouTube a MP3 (públicos)
• Reels (videos cortos)
• Posts (fotos y videos)
• Stories públicas
• IGTV videos
• Pinterest posts (imágenes, videos, carruseles)

✨ **Características:**
- No requiere login
- Límite: 1000MB por archivo
- Totalmente gratuito
- Rápido y confiable

🔗 **Envía cualquier link de TikTok o YouTube**

⚙️ **Comandos:**
/start - Iniciar bot
/help - Mostrar ayuda
/stats - Ver estadísticas
""",

    'help': """
ℹ️ **Guía de uso:**

📌 **Para TikTok:**
Envía: `https://vm.tiktok.com/XXXXXX/`
O: `https://www.tiktok.com/@usuario/video/123456789`

📌 **Para YouTube (audio MP3):**
Envía: `https://youtu.be/XXXXXXXXXXX`
O: `https://www.youtube.com/watch?v=XXXXXXXXXXX`

⚠️ **Limitaciones:**
• Máximo 1000MB por archivo
• Solo contenido público
• Videos cortos funcionan mejor
• Instagram puede bloquear descargas frecuentes
• Máximo 1000MB por archivo
🔧 **Si tienes problemas:**
1. Verifica que el link sea correcto
2. Asegúrate que el video sea público
3. Intenta con otro video
4. Contacta al desarrollador si persiste
""",

    'processing': "⏳ Descargando y procesando...",
    'too_large': "❌ El archivo es muy grande (>1000MB). Intenta con un video más corto.",
    'error': "❌ Error: {error}",
    'success_tiktok': "✅ TikTok descargado correctamente!",
    'success_youtube': "✅ Audio de YouTube descargado correctamente!",
    'invalid_url': "❌ URL no válida. Envía un link de TikTok o YouTube.",
    'unknown_error': "❌ Error desconocido. Por favor intenta de nuevo.",
}