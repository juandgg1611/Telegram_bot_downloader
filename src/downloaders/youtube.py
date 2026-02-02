"""
Descargador de YouTube sin FFmpeg
Soporta: videos MP4 (calidad seleccionable) y audio MP3/M4A
"""
import os
import re
import logging
import time
import json
import shutil
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass

import yt_dlp
import requests
from ..config import DOWNLOAD_DIR, MAX_FILE_SIZE

logger = logging.getLogger(__name__)

# ============================================================================
# CLASES DE DATOS
# ============================================================================

@dataclass
class YouTubeVideoInfo:
    """Información estructurada del video de YouTube"""
    id: str
    title: str
    duration: int
    uploader: str
    channel: str
    view_count: int
    like_count: int
    description: str
    thumbnail_url: str
    upload_date: str
    categories: List[str]
    tags: List[str]
    age_limit: int
    webpage_url: str
    formats: List[Dict]

# ============================================================================
# CLASE PRINCIPAL
# ============================================================================

class YouTubeDownloader:
    """
    Descargador robusto de YouTube sin FFmpeg
    - Videos MP4 en calidad seleccionable
    - Audio MP3/M4A sin conversión
    - Sin dependencia de FFmpeg
    """
    
    # Opciones de calidad predefinidas
    VIDEO_QUALITIES = {
        '360p': 'best[height<=360][ext=mp4]/best[height<=360]',
        '480p': 'best[height<=480][ext=mp4]/best[height<=480]',
        '720p': 'best[height<=720][ext=mp4]/best[height<=720]',
        'best': 'best[ext=mp4]/best',
    }
    
    AUDIO_FORMATS = {
        'mp3': 'bestaudio[ext=m4a]/bestaudio',  # Usamos m4a nativo, no MP3
        'm4a': 'bestaudio[ext=m4a]/bestaudio',
        'best': 'bestaudio',
    }
    
    def __init__(self, default_quality: str = '720p'):
        """
        Inicializar descargador
        
        Args:
            default_quality: Calidad por defecto para videos (360p, 480p, 720p, best)
        """
        self.default_quality = default_quality if default_quality in self.VIDEO_QUALITIES else '720p'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'es-ES,es;q=0.9',
        })
        
        # Configuración base para yt-dlp (SIN FFMPEG)
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'no_color': True,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'extract_flat': False,
            'concurrent_fragment_downloads': 3,
            'http_chunk_size': 10485760,  # 10MB
            'continuedl': True,
            'noprogress': False,
            'outtmpl': os.path.join(DOWNLOAD_DIR, 'youtube_%(id)s_%(title).50s.%(ext)s'),
            'restrictfilenames': True,
            'windowsfilenames': True,
            'nooverwrites': True,
        }
        
        # ========== AGREGAR SOPORTE PARA COOKIES ==========
        # Verificar si existe archivo de cookies
        cookies_path = 'cookies.txt'
        if os.path.exists(cookies_path):
            self.base_opts['cookiefile'] = cookies_path
            logger.info(f"✅ Usando cookies de YouTube desde: {cookies_path}")
        else:
            logger.info("ℹ️  No se encontró archivo cookies.txt para YouTube")
        # ========== FIN AGREGAR COOKIES ==========
        
        logger.info(f"YouTubeDownloader inicializado con calidad: {self.default_quality}")
    
    # ============================================================================
    # MÉTODOS DE DETECCIÓN
    # ============================================================================
    
    @classmethod
    def is_youtube_url(cls, url: str) -> bool:
        """Verificar si es una URL de YouTube válida"""
        if not url:
            return False
        
        url_lower = url.lower().strip()
        
        # Patrones de YouTube
        patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w\-_]+',
            r'https?://youtu\.be/[\w\-_]+',
            r'https?://(?:www\.)?youtube\.com/shorts/[\w\-_]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w\-_]+',
            r'https?://(?:www\.)?youtube\.com/v/[\w\-_]+',
            r'https?://(?:www\.)?youtube\.com/live/[\w\-_]+',
            r'https?://music\.youtube\.com/watch\?v=[\w\-_]+',
        ]
        
        return any(re.match(pattern, url_lower) for pattern in patterns)
    
    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """Extraer ID del video de YouTube"""
        try:
            # Para youtu.be/ID
            if 'youtu.be' in url:
                parsed = urlparse(url)
                return parsed.path.strip('/')
            
            # Para shorts
            if '/shorts/' in url:
                match = re.search(r'/shorts/([\w\-_]+)', url)
                return match.group(1) if match else None
            
            # Para watch?v=ID
            parsed = urlparse(url)
            if parsed.path == '/watch':
                query_params = parse_qs(parsed.query)
                return query_params.get('v', [None])[0]
            
            # Para /embed/ID o /v/ID
            match = re.search(r'/(?:embed|v)/([\w\-_]+)', url)
            return match.group(1) if match else None
            
        except Exception as e:
            logger.debug(f"Error extrayendo ID: {e}")
            return None
    
    # ============================================================================
    # MÉTODOS DE INFORMACIÓN
    # ============================================================================
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        Obtener información del video (método de compatibilidad)
        Returns dict para compatibilidad con código viejo
        """
        try:
            info = self._get_video_info_structured(url)
            
            return {
                'id': info.id,
                'title': info.title,
                'duration': info.duration,
                'uploader': info.uploader,
                'channel': info.channel,
                'view_count': info.view_count,
                'like_count': info.like_count,
                'description': info.description[:500] if info.description else '',
                'thumbnail': info.thumbnail_url,
                'upload_date': info.upload_date,
                'formats_count': len(info.formats),
                'age_limit': info.age_limit,
                'webpage_url': info.webpage_url,
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo info: {e}")
            # Info por defecto para no romper el flujo
            return {
                'id': self.extract_video_id(url) or 'unknown',
                'title': 'Video de YouTube',
                'duration': 0,
                'uploader': 'YouTube',
                'channel': 'YouTube',
                'view_count': 0,
                'like_count': 0,
                'description': '',
                'thumbnail': '',
                'upload_date': '',
                'formats_count': 0,
                'age_limit': 0,
                'webpage_url': url,
            }
    
    def _get_video_info_structured(self, url: str) -> YouTubeVideoInfo:
        """Obtener información estructurada del video"""
        # ========== CONFIGURACIÓN CON COOKIES ==========
        info_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        # FORZAR uso de cookies si el archivo existe
        cookies_path = 'cookies.txt'
        if os.path.exists(cookies_path):
            info_opts['cookiefile'] = cookies_path
            print(f"🔐 Usando cookies para obtener info del video")
            
            # También agregar headers de navegador
            info_opts['http_headers'] = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.youtube.com/',
            }
        
        try:
            with yt_dlp.YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError("No se pudo obtener información del video")
                
                return YouTubeVideoInfo(
                    id=info.get('id', ''),
                    title=info.get('title', 'Sin título'),
                    duration=info.get('duration', 0),
                    uploader=info.get('uploader', 'Desconocido'),
                    channel=info.get('channel', info.get('uploader', 'Desconocido')),
                    view_count=info.get('view_count', 0),
                    like_count=info.get('like_count', 0),
                    description=info.get('description', ''),
                    thumbnail_url=info.get('thumbnail', ''),
                    upload_date=info.get('upload_date', ''),
                    categories=info.get('categories', []),
                    tags=info.get('tags', []),
                    age_limit=info.get('age_limit', 0),
                    webpage_url=info.get('webpage_url', url),
                    formats=info.get('formats', []),
                )
                
        except Exception as e:
            logger.error(f"Error en _get_video_info_structured: {e}")
            raise
    
    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """Obtener lista de formatos disponibles"""
        # ========== CONFIGURACIÓN CON COOKIES ==========
        formats_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        # FORZAR uso de cookies si el archivo existe
        if os.path.exists('cookies.txt'):
            formats_opts['cookiefile'] = 'cookies.txt'
            formats_opts['http_headers'] = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        
        try:
            with yt_dlp.YoutubeDL(formats_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                formats = []
                for fmt in info.get('formats', []):
                    if fmt.get('vcodec') != 'none' or fmt.get('acodec') != 'none':
                        formats.append({
                            'format_id': fmt.get('format_id', ''),
                            'ext': fmt.get('ext', ''),
                            'resolution': fmt.get('resolution', ''),
                            'height': fmt.get('height', 0),
                            'width': fmt.get('width', 0),
                            'fps': fmt.get('fps', 0),
                            'vcodec': fmt.get('vcodec', ''),
                            'acodec': fmt.get('acodec', ''),
                            'filesize': fmt.get('filesize', 0),
                            'format_note': fmt.get('format_note', ''),
                        })
                
                return formats
                
        except Exception as e:
            logger.error(f"Error obteniendo formatos: {e}")
            return []
        
    def download_with_forced_cookies(self, url: str, format: str = 'm4a') -> Tuple[str, Dict[str, Any]]:
        """Descargar audio FORZANDO uso de cookies"""
        if not self.is_youtube_url(url):
            raise ValueError("URL de YouTube no válida")
        
        video_id = self.extract_video_id(url)
        print(f"🎵 Descargando {video_id} con cookies forzadas...")
        
        # Configuración AGRESIVA con cookies
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'youtube_cookies_{video_id}_%(title).50s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 5,
            
            # ========== COOKIES FORZADAS ==========
            'cookiefile': 'cookies.txt',
            
            # Headers completos de navegador
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.youtube.com/',
            },
            
            # Configuración para evitar detección
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['js', 'configs'],
                }
            },
            
            # Comportamiento más humano
            'sleep_interval': 1,
            'max_sleep_interval': 3,
            'ignoreerrors': False,
            'no_check_certificate': False,
            'prefer_insecure': False,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Primero obtener info CON cookies
                print("🔍 Obteniendo información del video...")
                info = ydl.extract_info(url, download=False)
                
                print(f"📋 Título: {info.get('title', 'Desconocido')}")
                print(f"⏱ Duración: {info.get('duration', 0)}s")
                
                # Luego descargar
                print("⬇️ Descargando audio...")
                ydl.download([url])
                
                # Buscar archivo descargado
                pattern = os.path.join(DOWNLOAD_DIR, f"*{video_id}*")
                import glob
                files = glob.glob(pattern)
                
                if not files:
                    raise FileNotFoundError("No se encontró archivo descargado")
                
                filepath = files[0]
                
                # Asegurar extensión .m4a
                if not filepath.endswith('.m4a'):
                    new_path = os.path.splitext(filepath)[0] + '.m4a'
                    if os.path.exists(filepath):
                        shutil.move(filepath, new_path)
                        filepath = new_path
                
                return filepath, {
                    'id': video_id,
                    'title': info.get('title', 'Audio')[:100],
                    'channel': info.get('uploader', 'YouTube'),
                    'duration': info.get('duration', 0),
                    'filesize': os.path.getsize(filepath),
                    'platform': 'youtube',
                    'content_type': 'audio',
                    'format': 'm4a',
                    'url': url,
                }
                
        except Exception as e:
            print(f"❌ Error con cookies forzadas: {e}")
            raise
    # ============================================================================
    # MÉTODOS DE DESCARGA (SIN FFMPEG)
    # ============================================================================
    
    def download_video(self, url: str, quality: str = None) -> Tuple[str, Dict[str, Any]]:
        """
        Descargar video de YouTube en formato MP4
        
        Args:
            url: URL del video
            quality: 360p, 480p, 720p, best (si es None, usa default_quality)
        
        Returns:
            (ruta_archivo, información)
        """
        if not self.is_youtube_url(url):
            raise ValueError("URL de YouTube no válida")
        
        quality = quality or self.default_quality
        if quality not in self.VIDEO_QUALITIES:
            quality = '720p'
        
        video_id = self.extract_video_id(url)
        logger.info(f"Descargando video {video_id} en {quality}")
        
        # Obtener información primero
        video_info = self._get_video_info_structured(url)
        
        # Configuración para descarga de VIDEO (formato combinado)
        ydl_opts = {
            **self.base_opts,
            'format': self.VIDEO_QUALITIES[quality],
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'youtube_{video_id}_{quality}_%(title).50s.%(ext)s'),
            'merge_output_format': 'mp4',  # Forzar MP4 como contenedor
            'prefer_free_formats': True,
            'keepvideo': False,
        }
        
        # Eliminar cualquier opción relacionada con FFmpeg
        if 'postprocessors' in ydl_opts:
            del ydl_opts['postprocessors']
        
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                logger.info(f"Intento {attempt + 1} para video {video_id}")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Descargar
                    ydl.download([url])
                    
                    # Buscar el archivo descargado
                    downloaded_files = self._find_downloaded_file(video_id, ['.mp4', '.webm', '.mkv'])
                    
                    if not downloaded_files:
                        # Buscar por patrón más amplio
                        pattern = os.path.join(DOWNLOAD_DIR, f"youtube_{video_id}*")
                        import glob
                        downloaded_files = glob.glob(pattern)
                    
                    if not downloaded_files:
                        raise FileNotFoundError("No se encontró archivo descargado")
                    
                    filepath = downloaded_files[0]
                    
                    # Renombrar a .mp4 si es necesario
                    if not filepath.lower().endswith('.mp4'):
                        new_path = os.path.splitext(filepath)[0] + '.mp4'
                        try:
                            shutil.move(filepath, new_path)
                            filepath = new_path
                        except Exception as e:
                            logger.warning(f"No se pudo renombrar a MP4: {e}")
                    
                    # Verificar que el archivo existe y tiene tamaño
                    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                        raise ValueError("Archivo descargado vacío o no existe")
                    
                    # Construir información de resultado
                    result_info = {
                        'id': video_id,
                        'title': video_info.title[:100],
                        'channel': video_info.channel,
                        'duration': video_info.duration,
                        'filesize': os.path.getsize(filepath),
                        'platform': 'youtube',
                        'content_type': 'video',
                        'quality': quality,
                        'format': 'mp4',
                        'url': url,
                        'width': 0,
                        'height': 0,
                    }
                    
                    # Intentar obtener resolución real
                    try:
                        import subprocess
                        cmd = [
                            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-show_entries', 'stream=width,height',
                            '-of', 'csv=p=0', filepath
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            dimensions = result.stdout.strip().split(',')
                            if len(dimensions) == 2:
                                result_info['width'] = int(dimensions[0])
                                result_info['height'] = int(dimensions[1])
                    except:
                        pass  # No problem si no tenemos ffprobe
                    
                    logger.info(f"✅ Video descargado: {filepath} ({result_info['filesize']} bytes)")
                    return filepath, result_info
                    
            except yt_dlp.utils.DownloadError as e:
                logger.error(f"Error yt-dlp video (intento {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    raise Exception(f"No se pudo descargar el video: {e}")
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error inesperado video (intento {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    raise Exception(f"Error descargando video: {str(e)}")
                time.sleep(2)
        
        raise Exception(f"No se pudo descargar el video después de {max_attempts} intentos")
    
    def download_audio(self, url: str, format: str = 'm4a') -> Tuple[str, Dict[str, Any]]:
        """
        Descargar solo audio de YouTube (SIN CONVERSIÓN A MP3)
        
        Args:
            url: URL del video
            format: m4a (recomendado), best
        
        Returns:
            (ruta_archivo, información)
        """
        if not self.is_youtube_url(url):
            raise ValueError("URL de YouTube no válida")
        
        if format not in self.AUDIO_FORMATS:
            format = 'm4a'
        
        video_id = self.extract_video_id(url)
        logger.info(f"Descargando audio {video_id} en formato {format}")
        
        # Obtener información primero
        video_info = self._get_video_info_structured(url)
        
        # Configuración para descarga de AUDIO (sin conversión)
        ydl_opts = {
            **self.base_opts,
            'format': self.AUDIO_FORMATS[format],
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'youtube_audio_{video_id}_%(title).50s.%(ext)s'),
            # NO USAR postprocessors (evita FFmpeg)
            'writethumbnail': False,  # Necesita FFmpeg
            'embedthumbnail': False,  # Necesita FFmpeg
            'addmetadata': False,     # Necesita FFmpeg
            'prefer_free_formats': True,
        }
        
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                logger.info(f"Intento {attempt + 1} para audio {video_id}")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Descargar
                    ydl.download([url])
                    
                    # Buscar el archivo descargado
                    downloaded_files = self._find_downloaded_file(
                        video_id, 
                        ['.m4a', '.webm', '.opus', '.mp3', '.aac']
                    )
                    
                    if not downloaded_files:
                        # Buscar archivo de audio más reciente
                        pattern = os.path.join(DOWNLOAD_DIR, f"youtube_audio_{video_id}*")
                        import glob
                        downloaded_files = glob.glob(pattern)
                    
                    if not downloaded_files:
                        raise FileNotFoundError("No se encontró archivo de audio descargado")
                    
                    filepath = downloaded_files[0]
                    file_ext = os.path.splitext(filepath)[1].lower()
                    
                    # Si es .webm o .opus y queremos m4a, intentar descargar específicamente m4a
                    if format == 'm4a' and file_ext in ['.webm', '.opus']:
                        logger.info(f"Formato {file_ext} no óptimo, intentando obtener m4a...")
                        # Intentar con formato específico para m4a
                        ydl_opts_m4a = {
                            **ydl_opts,
                            'format': 'bestaudio[ext=m4a]',
                        }
                        
                        with yt_dlp.YoutubeDL(ydl_opts_m4a) as ydl_m4a:
                            # Limpiar archivo anterior
                            try:
                                os.remove(filepath)
                            except:
                                pass
                            
                            # Intentar descargar m4a específicamente
                            ydl_m4a.download([url])
                            downloaded_files = self._find_downloaded_file(video_id, ['.m4a'])
                            if downloaded_files:
                                filepath = downloaded_files[0]
                                file_ext = '.m4a'
                    
                    # Verificar archivo
                    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                        raise ValueError("Archivo de audio vacío o no existe")
                    
                    # Renombrar extensión según formato solicitado
                    desired_ext = f".{format}"
                    if not filepath.endswith(desired_ext):
                        new_path = os.path.splitext(filepath)[0] + desired_ext
                        try:
                            shutil.move(filepath, new_path)
                            filepath = new_path
                        except Exception as e:
                            logger.warning(f"No se pudo renombrar a {desired_ext}: {e}")
                    
                    # Construir información de resultado
                    result_info = {
                        'id': video_id,
                        'title': video_info.title[:100],
                        'channel': video_info.channel,
                        'duration': video_info.duration,
                        'filesize': os.path.getsize(filepath),
                        'platform': 'youtube',
                        'content_type': 'audio',
                        'format': format,
                        'url': url,
                        'actual_format': file_ext[1:] if file_ext else format,
                    }
                    
                    # Añadir metadatos básicos sin FFmpeg
                    self._add_basic_metadata(filepath, video_info, format)
                    
                    logger.info(f"✅ Audio descargado: {filepath} ({result_info['filesize']} bytes)")
                    return filepath, result_info
                    
            except yt_dlp.utils.DownloadError as e:
                logger.error(f"Error yt-dlp audio (intento {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    raise Exception(f"No se pudo descargar el audio: {e}")
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error inesperado audio (intento {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    raise Exception(f"Error descargando audio: {str(e)}")
                time.sleep(2)
        
        raise Exception(f"No se pudo descargar el audio después de {max_attempts} intentos")
    
    def download(self, url: str, download_type: str = 'video', quality: str = None, 
                 audio_format: str = 'm4a') -> Tuple[str, Dict[str, Any]]:
        """
        Método principal de descarga (para compatibilidad)
        
        Args:
            url: URL del video
            download_type: 'video' o 'audio'
            quality: Solo para video: 360p, 480p, 720p, best
            audio_format: Solo para audio: m4a, best
        
        Returns:
            (ruta_archivo, información)
        """
        if download_type.lower() == 'video':
            return self.download_video(url, quality)
        else:
            return self.download_audio(url, audio_format)
    
    # ============================================================================
    # MÉTODOS AUXILIARES
    # ============================================================================
    
    def _find_downloaded_file(self, video_id: str, extensions: List[str]) -> List[str]:
        """Buscar archivo descargado por ID y extensiones"""
        found_files = []
        
        for ext in extensions:
            pattern = os.path.join(DOWNLOAD_DIR, f"*{video_id}*{ext}")
            import glob
            files = glob.glob(pattern)
            found_files.extend(files)
        
        # Ordenar por fecha de modificación (más reciente primero)
        found_files.sort(key=os.path.getmtime, reverse=True)
        
        return found_files
    
    def _add_basic_metadata(self, filepath: str, video_info: YouTubeVideoInfo, format: str):
        """Añadir metadatos básicos sin FFmpeg"""
        try:
            # Para archivos m4a, podemos usar mutagen para metadatos básicos
            if format == 'm4a' and filepath.endswith('.m4a'):
                try:
                    from mutagen.mp4 import MP4, MP4Cover
                    
                    audio = MP4(filepath)
                    
                    # Añadir metadatos básicos
                    audio['\xa9nam'] = [video_info.title[:100]]  # Title
                    audio['\xa9ART'] = [video_info.channel[:100]]  # Artist
                    audio['\xa9alb'] = ['YouTube Download']  # Album
                    audio['\xa9day'] = [video_info.upload_date] if video_info.upload_date else []
                    audio['\xa9cmt'] = [video_info.description[:200]] if video_info.description else []
                    audio['\xa9gen'] = [', '.join(video_info.categories)] if video_info.categories else []
                    
                    # Guardar
                    audio.save()
                    logger.debug(f"Metadatos añadidos a {filepath}")
                    
                except ImportError:
                    logger.debug("Mutagen no disponible para metadatos")
                except Exception as e:
                    logger.debug(f"No se pudieron añadir metadatos: {e}")
                    
        except Exception as e:
            logger.debug(f"Error en metadatos: {e}")
    
    def cleanup(self, filepath: str):
        """Eliminar archivo temporal"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                
                # También eliminar archivos relacionados
                base_name = os.path.splitext(filepath)[0]
                for ext in ['.jpg', '.jpeg', '.png', '.webp', '.part', '.ytdl', '.temp']:
                    related = f"{base_name}{ext}"
                    if os.path.exists(related):
                        try:
                            os.remove(related)
                        except:
                            pass
                            
                logger.debug(f"Archivo limpiado: {filepath}")
                
        except Exception as e:
            logger.warning(f"No se pudo limpiar {filepath}: {e}")
    
    def get_file_info(self, filepath: str) -> Dict[str, Any]:
        """Obtener información del archivo"""
        if not os.path.exists(filepath):
            return {}
        
        import datetime
        stat = os.stat(filepath)
        
        return {
            'path': filepath,
            'size': stat.st_size,
            'created': datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'extension': os.path.splitext(filepath)[1].lower(),
            'filename': os.path.basename(filepath),
        }
    
    def get_download_options(self, url: str) -> Dict[str, Any]:
        """Obtener opciones de descarga disponibles"""
        try:
            formats = self.get_available_formats(url)
            video_info = self._get_video_info_structured(url)
            
            # Agrupar formatos por tipo
            video_formats = []
            audio_formats = []
            
            for fmt in formats:
                if fmt['vcodec'] != 'none':
                    video_formats.append(fmt)
                elif fmt['acodec'] != 'none':
                    audio_formats.append(fmt)
            
            return {
                'video': {
                    'count': len(video_formats),
                    'qualities': sorted(set(fmt['height'] for fmt in video_formats if fmt['height'])),
                    'formats': video_formats[:10],  # Primeros 10
                },
                'audio': {
                    'count': len(audio_formats),
                    'formats': sorted(set(fmt['ext'] for fmt in audio_formats)),
                    'audio_formats': audio_formats[:5],  # Primeros 5
                },
                'info': {
                    'duration': video_info.duration,
                    'title': video_info.title,
                    'channel': video_info.channel,
                }
            }
        
            
        except Exception as e:
            logger.error(f"Error obteniendo opciones: {e}")
            return {'video': {'count': 0}, 'audio': {'count': 0}}

    # ============================================================================
    # MÉTODOS PARA PO TOKEN/VISITOR DATA
    # ============================================================================
    
    def _extract_visitor_data(self) -> Optional[str]:
        """Extraer VISITOR_INFO1_LIVE de cookies.txt"""
        cookies_path = 'cookies.txt'
        if not os.path.exists(cookies_path):
            return None
        
        try:
            with open(cookies_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and 'VISITOR_INFO1_LIVE' in line:
                        parts = line.split('\t')
                        if len(parts) >= 7:
                            return parts[6]  # El valor de la cookie
            return None
        except Exception as e:
            logger.error(f"Error extrayendo visitor data: {e}")
            return None
    
    def download_audio_with_visitor_data(self, url: str, format: str = 'm4a') -> Tuple[str, Dict[str, Any]]:
        """
        Descargar usando Visitor Data en lugar de cookies completas
        Según: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies
        """
        if not self.is_youtube_url(url):
            raise ValueError("URL de YouTube no válida")
        
        video_id = self.extract_video_id(url)
        logger.info(f"Descargando audio {video_id} con Visitor Data")
        
        # Extraer visitor data
        visitor_data = self._extract_visitor_data()
        
        if not visitor_data:
            raise ValueError("No se pudo extraer VISITOR_INFO1_LIVE de cookies.txt")
        
        print(f"🔐 Usando Visitor Data: {visitor_data[:20]}...")
        
        # Configuración especial para Visitor Data
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'no_color': True,
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
            'skip_unavailable_fragments': True,
            'extract_flat': False,
            'concurrent_fragment_downloads': 1,
            'http_chunk_size': 10485760,
            'continuedl': True,
            'noprogress': True,
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'youtube_visitor_{video_id}_%(title).50s.%(ext)s'),
            'restrictfilenames': True,
            'windowsfilenames': True,
            'nooverwrites': True,
            
            # Formato de audio
            'format': 'bestaudio[ext=m4a]/bestaudio',
            
            # ========== CONFIGURACIÓN PARA VISITOR DATA ==========
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb', 'android'],
                    'player_skip': ['webpage', 'configs'],
                    'visitor_data': visitor_data,
                }
            },
            
            # Headers optimizados
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'X-YouTube-Client-Name': '2',
                'X-YouTube-Client-Version': '2.20250101.00.00',
                'Origin': 'https://www.youtube.com',
                'Referer': 'https://m.youtube.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
            },
            
            # Comportamiento conservador
            'sleep_interval': 3,
            'max_sleep_interval': 6,
            'retry_sleep': 5,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extraer información primero
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError("No se pudo obtener información del video")
                
                print(f"📋 Título: {info.get('title', 'Desconocido')}")
                print(f"⏱ Duración: {info.get('duration', 0)}s")
                
                # Descargar
                ydl.download([url])
                
                # Buscar archivo
                pattern = os.path.join(DOWNLOAD_DIR, f"*{video_id}*")
                import glob
                files = glob.glob(pattern)
                
                if not files:
                    raise FileNotFoundError("No se encontró archivo descargado")
                
                filepath = files[0]
                
                # Asegurar extensión .m4a
                if not filepath.endswith('.m4a'):
                    base_name = os.path.splitext(filepath)[0]
                    m4a_file = base_name + '.m4a'
                    if os.path.exists(filepath):
                        shutil.move(filepath, m4a_file)
                        filepath = m4a_file
                
                logger.info(f"✅ Audio descargado con Visitor Data: {filepath}")
                
                return filepath, {
                    'id': video_id,
                    'title': info.get('title', 'Audio')[:100],
                    'channel': info.get('uploader', 'YouTube'),
                    'duration': info.get('duration', 0),
                    'filesize': os.path.getsize(filepath),
                    'platform': 'youtube',
                    'content_type': 'audio',
                    'format': format,
                    'method': 'visitor_data',
                }
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logger.error(f"Error con Visitor Data: {error_msg}")
            
            # Si falla, probar método alternativo
            if "Sign in to confirm you're not a bot" in error_msg:
                raise Exception("Visitor Data no funcionó. Necesitas PO Token real.")
            else:
                raise Exception(f"Error descargando con Visitor Data: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            raise
    
    def download_audio_with_retry(self, url: str, format: str = 'm4a', max_retries: int = 3) -> Tuple[str, Dict[str, Any]]:
        """
        Sistema de reintentos inteligente
        1. Primero intenta con Visitor Data
        2. Si falla, intenta con cookies normales
        3. Si falla, intenta método básico
        """
        video_id = self.extract_video_id(url)
        print(f"🔄 Sistema de reintentos para: {video_id}")
        
        methods = [
            ("Visitor Data", self.download_audio_with_visitor_data),
            ("Cookies forzadas", self.download_with_forced_cookies),
            ("Método normal", self.download_audio),
        ]
        
        last_error = None
        
        for method_name, method_func in methods:
            try:
                print(f"🔄 Intentando con: {method_name}")
                return method_func(url, format)
            except Exception as e:
                error_msg = str(e)
                print(f"❌ {method_name} falló: {error_msg[:100]}")
                last_error = e
                
                # Esperar antes de intentar siguiente método
                time.sleep(2)
                continue
        
        # Si todos los métodos fallaron
        raise Exception(f"Todos los métodos fallaron para {video_id}. Último error: {last_error}")