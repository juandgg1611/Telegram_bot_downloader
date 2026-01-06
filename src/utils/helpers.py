"""
Utilidades para el bot
"""
import re
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def extract_url_from_text(text: str) -> Optional[str]:
    """
    Extraer URL de un texto
    """
    # Patrón para URLs
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w@:%.\+~#=]*)*(?:\?[-\w@:%\+.~#?&//=]*)?'
    
    matches = re.findall(url_pattern, text)
    if matches:
        return matches[0]
    return None

def validate_url(url: str) -> Tuple[bool, str]:
    """
    Validar URL y detectar plataforma
    
    Returns:
        (es_válida, plataforma)
    """
    if not url or not isinstance(url, str):
        return False, "invalid"
    
    # Limpiar la URL
    url = url.strip()
    
    # Asegurar que empiece con http:// o https://
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        # Verificar dominio primero (más rápido que importar las clases)
        domain = url.lower()
        
        # TikTok
        if any(tiktok_domain in domain for tiktok_domain in ['tiktok.com', 'tiktok.com']):
            from ..downloaders.tiktok import TikTokDownloader
            if TikTokDownloader.is_tiktok_url(url)[0]:
                return True, "tiktok"
        
        # YouTube
        if any(yt_domain in domain for yt_domain in ['youtube.com', 'youtu.be']):
            from ..downloaders.youtube import YouTubeDownloader
            if YouTubeDownloader.is_youtube_url(url):
                return True, "youtube"
        
        # Instagram
        if any(ig_domain in domain for ig_domain in ['instagram.com', 'instagr.am']):
            from ..downloaders.instagram import InstagramDownloader
            is_instagram, _ = InstagramDownloader.is_instagram_url(url)
            if is_instagram:
                return True, "instagram"
        
        # Pinterest
        if any(pin_domain in domain for pin_domain in ['pinterest.com', 'pin.it', 'pinterest.co.uk', 
                                                      'pinterest.fr', 'pinterest.de', 'pinterest.ru']):
            from ..downloaders.pinterest import PinterestDownloader
            is_pinterest, _ = PinterestDownloader.is_pinterest_url(url)
            if is_pinterest:
                return True, "pinterest"
        
        return False, "unsupported"
        
    except ImportError as e:
        logger.error(f"Error importando módulos: {e}")
        # Fallback: verificar por patrones simples
        if 'tiktok.com' in url.lower():
            return True, "tiktok"
        elif 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
            return True, "youtube"
        elif 'instagram.com' in url.lower() or 'instagr.am' in url.lower():
            return True, "instagram"
        elif any(pin_domain in url.lower() for pin_domain in ['pinterest.com', 'pin.it', 'pinterest.co.uk', 
                                                              'pinterest.fr', 'pinterest.de', 'pinterest.ru']):
            return True, "pinterest"
        return False, "error"
    except Exception as e:
        logger.error(f"Error validando URL {url}: {e}")
        return False, "error"

def format_file_size(size_bytes: int) -> str:
    """Formatear tamaño de archivo en formato legible"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def format_duration(seconds: float) -> str:
    """
    Formatear duración en formato MM:SS o HH:MM:SS
    Maneja floats, ints, y valores None/0
    """
    try:
        # Convertir a int (redondear hacia abajo)
        if seconds is None or seconds <= 0:
            return "00:00"
        
        seconds_int = int(seconds)
        
        if seconds_int < 3600:
            minutes = seconds_int // 60
            secs = seconds_int % 60
            return f"{minutes:01d}:{secs:02d}"  # Cambiado a 01d para minutos
        else:
            hours = seconds_int // 3600
            minutes = (seconds_int % 3600) // 60
            secs = seconds_int % 60
            return f"{hours}:{minutes:02d}:{secs:02d}"
            
    except (ValueError, TypeError) as e:
        logger.debug(f"Error formateando duración {seconds}: {e}")
        return "00:00"

def format_duration_human(seconds: float) -> str:
    """
    Formatear duración en formato humano (1 min 30 seg)
    """
    try:
        if seconds is None or seconds <= 0:
            return "0 seg"
        
        seconds_int = int(seconds)
        
        if seconds_int < 60:
            return f"{seconds_int} seg"
        elif seconds_int < 3600:
            minutes = seconds_int // 60
            secs = seconds_int % 60
            if secs > 0:
                return f"{minutes} min {secs} seg"
            else:
                return f"{minutes} min"
        else:
            hours = seconds_int // 3600
            minutes = (seconds_int % 3600) // 60
            if minutes > 0:
                return f"{hours} h {minutes} min"
            else:
                return f"{hours} h"
                
    except (ValueError, TypeError) as e:
        logger.debug(f"Error formateando duración humana {seconds}: {e}")
        return "0 seg"

def sanitize_filename(filename: str) -> str:
    """Sanitizar nombre de archivo"""
    # Remover caracteres inválidos
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limitar longitud
    if len(filename) > 200:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:195] + (f'.{ext}' if ext else '')
    
    return filename