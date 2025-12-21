"""
Módulo para descargar contenido de TikTok
Soporta: videos, fotos, slideshows
"""
import os
import re
import logging
import time
import requests
import json
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse, parse_qs, unquote
from dataclasses import dataclass

import yt_dlp
from ..config import TIKTOK_OPTIONS, DOWNLOAD_DIR, MAX_FILE_SIZE

logger = logging.getLogger(__name__)

# ============================================================================
# CLASES DE DATOS
# ============================================================================

@dataclass
class TikTokContentInfo:
    """Información estructurada del contenido de TikTok"""
    id: str
    content_type: str  # 'video', 'photo', 'slideshow'
    title: str
    uploader: str
    duration: int
    view_count: int
    like_count: int
    comment_count: int
    share_count: int
    description: str
    thumbnail_url: str
    download_url: str
    width: int
    height: int
    is_private: bool
    timestamp: int
    music_title: str
    music_author: str

# ============================================================================
# CLASE PRINCIPAL
# ============================================================================

class TikTokDownloader:
    """
    Descargador robusto de contenido de TikTok
    - Soporta videos (todos los formatos)
    - Soporta fotos individuales
    - Soporta slideshows (múltiples fotos)
    - Manejo de errores completo
    - Fallbacks múltiples
    """
    
    # Headers para simular navegador real
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    # API de TikTok (endpoints públicos conocidos)
    API_ENDPOINTS = [
        "https://api16-normal-c-useast1a.tiktokv.com/aweme/v1/feed/",
        "https://api.tiktokv.com/aweme/v1/feed/",
        "https://m.tiktok.com/api/item/detail/",
    ]
    
    # Patrones de URL mejorados
    URL_PATTERNS = {
        'video': [
            r'https?://(?:www\.|vm\.|vt\.|m\.)?tiktok\.com/(?:@[\w\.-]+/video/|t/[\w]+/|[\w]+)(?:\?.*)?',
            r'https?://(?:www\.)?tiktok\.com/(?:v|share)/\d+',
            r'https?://vt\.tiktok\.com/[\w\-]+/',
            r'https?://vm\.tiktok\.com/[\w\-]+/',
        ],
        'photo': [
            r'https?://(?:www\.|m\.)?tiktok\.com/@[\w\.-]+/photo/\d+',
            r'https?://(?:www\.|m\.)?tiktok\.com/photo/\d+',
        ],
        'slideshow': [
            r'https?://(?:www\.|m\.)?tiktok\.com/@[\w\.-]+/slideshow/\d+',
        ]
    }
    
    def __init__(self):
        """Inicializar el descargador con múltiples opciones"""
        self.ydl_opts_video = {
            **TIKTOK_OPTIONS,
            'format': 'best[height<=720][filesize<50M]/best[height<=1080][filesize<50M]/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, 'tiktok_%(id)s_%(title).50s.%(ext)s'),
            'windowsfilenames': True,
            'restrictfilenames': True,
            'nooverwrites': True,
            'continuedl': True,
            'noprogress': True,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'extract_flat': False,
            'quiet': False,
            'verbose': False,
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.timeout = 30
        
    # ============================================================================
    # MÉTODOS DE DETECCIÓN
    # ============================================================================
    
    @classmethod
    def is_tiktok_url(cls, url: str) -> Tuple[bool, str]:
        """
        Verificar si es URL de TikTok y devolver tipo
        
        Returns:
            (es_tiktok, tipo_contenido)
        """
        if not url or 'tiktok.com' not in url.lower():
            return False, 'invalid'
        
        url_clean = url.split('?')[0].strip()
        
        # Verificar fotos primero
        for pattern in cls.URL_PATTERNS['photo']:
            if re.match(pattern, url_clean, re.IGNORECASE):
                return True, 'photo'
        
        # Verificar slideshows
        for pattern in cls.URL_PATTERNS['slideshow']:
            if re.match(pattern, url_clean, re.IGNORECASE):
                return True, 'slideshow'
        
        # Verificar videos (cualquier otra URL de TikTok)
        for pattern in cls.URL_PATTERNS['video']:
            if re.match(pattern, url_clean, re.IGNORECASE):
                return True, 'video'
        
        # Si tiene tiktok.com pero no coincide con patrones específicos
        return True, 'video'  # Asumimos video por defecto
    
    def extract_content_id(self, url: str) -> Optional[str]:
        """
        Extraer ID del contenido de forma robusta
        """
        try:
            # Método 1: Extraer de parámetros de URL
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # Intentar con item_id primero
            if 'item_id' in query_params:
                return str(query_params['item_id'][0])
            
            # Método 2: Extraer de la ruta
            path_parts = parsed.path.strip('/').split('/')
            
            # Para formato: /@user/video/123456789
            if len(path_parts) >= 3 and path_parts[1] in ['video', 'photo', 'slideshow']:
                return path_parts[2]
            
            # Para formato: /video/123456789
            if len(path_parts) >= 2 and path_parts[0] in ['video', 'photo', 'slideshow']:
                return path_parts[1]
            
            # Método 3: Buscar números largos en la URL
            numbers = re.findall(r'\d{10,20}', url)
            if numbers:
                return numbers[0]
            
            # Método 4: Para URLs cortas, usar yt-dlp
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return info.get('id')
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extrayendo ID: {e}")
            return None
    
    # ============================================================================
    # MÉTODOS DE OBTENCIÓN DE INFORMACIÓN
    # ============================================================================
    
    def get_content_info(self, url: str) -> TikTokContentInfo:
        """
        Obtener información completa del contenido usando múltiples métodos
        """
        # Información por defecto (NUNCA estará vacía)
        default_info = TikTokContentInfo(
            id=self.extract_content_id(url) or f"tt_{int(time.time())}",
            content_type='video',
            title='Contenido de TikTok',
            uploader='Usuario de TikTok',
            duration=0,
            view_count=0,
            like_count=0,
            comment_count=0,
            share_count=0,
            description='',
            thumbnail_url='',
            download_url='',
            width=0,
            height=0,
            is_private=False,
            timestamp=int(time.time()),
            music_title='',
            music_author='',
        )
        
        # Determinar tipo de contenido
        is_tiktok, content_type = self.is_tiktok_url(url)
        default_info.content_type = content_type
        
        # Intentar obtener info real usando múltiples métodos
        info = None
        
        # Método 1: Usar yt-dlp (mejor para videos)
        if content_type == 'video':
            info = self._get_info_ytdlp(url)
        
        # Método 2: Usar API pública de TikTok
        if not info:
            info = self._get_info_api(url)
        
        # Método 3: Web scraping básico
        if not info:
            info = self._get_info_scraping(url)
        
        # Combinar información obtenida con la por defecto
        if info:
            for field in info.__dataclass_fields__:
                if hasattr(info, field) and getattr(info, field):
                    setattr(default_info, field, getattr(info, field))
        
        # Post-procesamiento para fotos
        if content_type == 'photo':
            default_info.title = 'Foto de TikTok'
            # Extraer usuario de la URL si es posible
            username_match = re.search(r'@([\w\.-]+)', url)
            if username_match:
                default_info.uploader = username_match.group(1)
        
        logger.info(f"Info obtenida: {default_info.content_type} - {default_info.title[:30]}")
        return default_info
    
    def _get_info_ytdlp(self, url: str) -> Optional[TikTokContentInfo]:
        """Obtener información usando yt-dlp"""
        try:
            with yt_dlp.YoutubeDL({
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                return TikTokContentInfo(
                    id=str(info.get('id', '')),
                    content_type='video' if info.get('duration', 0) > 0 else 'photo',
                    title=info.get('title', ''),
                    uploader=info.get('uploader', ''),
                    duration=int(info.get('duration', 0)),
                    view_count=int(info.get('view_count', 0)),
                    like_count=int(info.get('like_count', 0)),
                    comment_count=int(info.get('comment_count', 0)),
                    share_count=int(info.get('repost_count', 0)),
                    description=info.get('description', ''),
                    thumbnail_url=info.get('thumbnail', ''),
                    download_url=info.get('url', '') if 'formats' not in info else info['formats'][0]['url'] if info.get('formats') else '',
                    width=int(info.get('width', 0)),
                    height=int(info.get('height', 0)),
                    is_private=info.get('availability') == 'private',
                    timestamp=int(info.get('timestamp', time.time())),
                    music_title=info.get('track', ''),
                    music_author=info.get('artist', ''),
                )
                
        except Exception as e:
            logger.debug(f"yt-dlp info falló: {e}")
            return None
    
    def _get_info_api(self, url: str) -> Optional[TikTokContentInfo]:
        """Obtener información usando API pública de TikTok"""
        content_id = self.extract_content_id(url)
        if not content_id:
            return None
        
        for endpoint in self.API_ENDPOINTS:
            try:
                # Construir payload para la API
                payload = {
                    'aweme_id': content_id,
                    'msToken': 'xk03tHBQ7iZR-TmC1-Hjq7OyeIDU01SxZ4qqX18=',
                    'X-Bogus': 'DFSzswVLmDmANRc7SJ/XFlc6c0cS',
                    '_signature': '2.c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7c7',
                }
                
                response = self.session.get(
                    endpoint,
                    params=payload,
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Buscar la estructura de datos de TikTok
                    aweme_info = data.get('aweme_list', [{}])[0] if 'aweme_list' in data else data.get('itemInfo', {}).get('itemStruct', {})
                    
                    if aweme_info:
                        # Extraer información básica
                        author = aweme_info.get('author', {})
                        stats = aweme_info.get('stats', {})
                        video = aweme_info.get('video', {})
                        music = aweme_info.get('music', {})
                        
                        content_type = 'photo' if aweme_info.get('image_post_info') else 'video'
                        
                        return TikTokContentInfo(
                            id=str(aweme_info.get('aweme_id', content_id)),
                            content_type=content_type,
                            title=aweme_info.get('desc', '')[:200],
                            uploader=author.get('unique_id', ''),
                            duration=int(video.get('duration', 0) / 1000),
                            view_count=int(stats.get('play_count', 0)),
                            like_count=int(stats.get('digg_count', 0)),
                            comment_count=int(stats.get('comment_count', 0)),
                            share_count=int(stats.get('share_count', 0)),
                            description=aweme_info.get('desc', ''),
                            thumbnail_url=video.get('cover', {}).get('url_list', [''])[0] if video.get('cover') else '',
                            download_url=video.get('play_addr', {}).get('url_list', [''])[0] if video.get('play_addr') else '',
                            width=int(video.get('width', 0)),
                            height=int(video.get('height', 0)),
                            is_private=aweme_info.get('is_delete', False) or aweme_info.get('private_item', False),
                            timestamp=int(aweme_info.get('create_time', time.time())),
                            music_title=music.get('title', ''),
                            music_author=music.get('author', ''),
                        )
                        
            except Exception as e:
                logger.debug(f"API {endpoint} falló: {e}")
                continue
        
        return None
    
    def _get_info_scraping(self, url: str) -> Optional[TikTokContentInfo]:
        """Obtener información mediante web scraping"""
        try:
            response = self.session.get(url, timeout=15)
            html = response.text
            
            # Buscar datos estructurados en JSON-LD
            import json
            json_patterns = [
                r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
                r'<script[^>]*id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
                r'<script[^>]*id="SIGI_STATE"[^>]*>(.*?)</script>',
                r'window\[\'__INITIAL_PROPS__\'\]\s*=\s*({.*?});',
            ]
            
            for pattern in json_patterns:
                matches = re.search(pattern, html, re.DOTALL)
                if matches:
                    try:
                        data = json.loads(matches.group(1))
                        
                        # Navegar por la estructura común de TikTok
                        item_module = data.get('ItemModule', {})
                        if item_module:
                            for item_id, item_data in item_module.items():
                                return TikTokContentInfo(
                                    id=str(item_id),
                                    content_type='video',
                                    title=item_data.get('desc', ''),
                                    uploader=item_data.get('author', ''),
                                    duration=0,
                                    view_count=int(item_data.get('stats', {}).get('playCount', 0)),
                                    like_count=int(item_data.get('stats', {}).get('diggCount', 0)),
                                    comment_count=int(item_data.get('stats', {}).get('commentCount', 0)),
                                    share_count=int(item_data.get('stats', {}).get('shareCount', 0)),
                                    description=item_data.get('desc', ''),
                                    thumbnail_url=item_data.get('video', {}).get('cover', ''),
                                    download_url='',
                                    width=0,
                                    height=0,
                                    is_private=False,
                                    timestamp=int(time.time()),
                                    music_title='',
                                    music_author='',
                                )
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Scraping falló: {e}")
            return None
    
    # ============================================================================
    # MÉTODOS DE DESCARGA
    # ============================================================================
    
    def download(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Descargar contenido de TikTok
        
        Returns:
            (ruta_archivo, info_dict)
        """
        # Verificar URL
        is_tiktok, content_type = self.is_tiktok_url(url)
        if not is_tiktok:
            raise ValueError("URL de TikTok no válida")
        
        # Obtener información
        content_info = self.get_content_info(url)
        
        logger.info(f"Iniciando descarga: {content_type} - {content_info.id}")
        
        # Descargar según el tipo
        if content_type == 'photo':
            filepath, result_info = self._download_photo(url, content_info)
        else:  # video o slideshow (tratado como video)
            filepath, result_info = self._download_video(url, content_info)
        
        # Verificar tamaño
        if os.path.getsize(filepath) > MAX_FILE_SIZE:
            self.cleanup(filepath)
            raise ValueError(f"Archivo demasiado grande ({os.path.getsize(filepath)} bytes)")
        
        return filepath, result_info
    
    def _download_video(self, url: str, content_info: TikTokContentInfo) -> Tuple[str, Dict[str, Any]]:
        """Descargar video usando yt-dlp con múltiples intentos"""
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"Intento {attempt + 1} de descarga de video")
                
                # Configuración específica para este intento
                ydl_opts = self.ydl_opts_video.copy()
                ydl_opts['outtmpl'] = os.path.join(
                    DOWNLOAD_DIR, 
                    f"tiktok_{content_info.id}_attempt{attempt}.%(ext)s"
                )
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Intentar descargar
                    ydl.download([url])
                    
                    # Buscar el archivo descargado
                    downloaded_files = []
                    for ext in ['.mp4', '.webm', '.mkv', '.mov']:
                        pattern = os.path.join(DOWNLOAD_DIR, f"tiktok_{content_info.id}_attempt{attempt}*{ext}")
                        import glob
                        downloaded_files.extend(glob.glob(pattern))
                    
                    if not downloaded_files:
                        # Buscar el archivo más reciente
                        all_files = [f for f in os.listdir(DOWNLOAD_DIR) 
                                   if f.startswith(f"tiktok_{content_info.id}")]
                        if all_files:
                            downloaded_files = [os.path.join(DOWNLOAD_DIR, 
                                 max(all_files, key=lambda f: os.path.getctime(os.path.join(DOWNLOAD_DIR, f))))]
                    
                    if not downloaded_files:
                        raise FileNotFoundError("No se encontró archivo descargado")
                    
                    filepath = downloaded_files[0]
                    
                    # Renombrar a .mp4 si es necesario
                    if not filepath.endswith('.mp4'):
                        new_path = os.path.splitext(filepath)[0] + '.mp4'
                        os.rename(filepath, new_path)
                        filepath = new_path
                    
                    # Construir información de resultado
                    result_info = {
                        'id': content_info.id,
                        'title': content_info.title[:100],
                        'uploader': content_info.uploader,
                        'duration': content_info.duration,
                        'filesize': os.path.getsize(filepath),
                        'platform': 'tiktok',
                        'content_type': content_info.content_type,
                        'url': url,
                        'width': content_info.width,
                        'height': content_info.height,
                        'view_count': content_info.view_count,
                        'like_count': content_info.like_count,
                    }
                    
                    logger.info(f"✅ Video descargado: {filepath} ({result_info['filesize']} bytes)")
                    return filepath, result_info
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Intento {attempt + 1} falló: {e}")
                time.sleep(2)  # Esperar antes de reintentar
        
        # Si todos los intentos fallaron
        raise Exception(f"No se pudo descargar el video después de {max_attempts} intentos: {last_error}")
    
    def _download_photo(self, url: str, content_info: TikTokContentInfo) -> Tuple[str, Dict[str, Any]]:
        """Descargar foto usando múltiples métodos"""
        # Método 1: Intentar con yt-dlp primero
        try:
            with yt_dlp.YoutubeDL({
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_DIR, f'tiktok_photo_{content_info.id}.%(ext)s'),
                'quiet': True,
            }) as ydl:
                info = ydl.extract_info(url, download=True)
                temp_file = ydl.prepare_filename(info)
                
                if os.path.exists(temp_file):
                    # Convertir a JPG si es necesario
                    if not temp_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        import shutil
                        jpg_file = os.path.splitext(temp_file)[0] + '.jpg'
                        shutil.move(temp_file, jpg_file)
                        temp_file = jpg_file
                    
                    result_info = {
                        'id': content_info.id,
                        'title': content_info.title,
                        'uploader': content_info.uploader,
                        'filesize': os.path.getsize(temp_file),
                        'platform': 'tiktok',
                        'content_type': 'photo',
                        'url': url,
                        'width': content_info.width,
                        'height': content_info.height,
                    }
                    
                    return temp_file, result_info
                    
        except Exception as e:
            logger.debug(f"yt-dlp para foto falló: {e}")
        
        # Método 2: Web scraping para encontrar la imagen
        try:
            response = self.session.get(url, timeout=15)
            html = response.text
            
            # Buscar URLs de imagen en el HTML
            import re
            image_patterns = [
                r'"contentUrl":"([^"]+\.(?:jpg|jpeg|png|webp))"',
                r'property="og:image" content="([^"]+)"',
                r'<meta[^>]*image[^>]*content="([^"]+)"',
                r'src="([^"]+\.(?:jpg|jpeg|png|webp))"[^>]*class="[^"]*photo[^"]*"',
            ]
            
            image_url = None
            for pattern in image_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    image_url = match.group(1)
                    break
            
            if image_url:
                # Descargar la imagen
                if not image_url.startswith('http'):
                    from urllib.parse import urljoin
                    image_url = urljoin(url, image_url)
                
                img_response = self.session.get(image_url, timeout=30)
                img_response.raise_for_status()
                
                # Guardar la imagen
                filename = os.path.join(DOWNLOAD_DIR, f'tiktok_photo_{content_info.id}.jpg')
                with open(filename, 'wb') as f:
                    f.write(img_response.content)
                
                # Optimizar si es muy grande
                self._optimize_image(filename)
                
                result_info = {
                    'id': content_info.id,
                    'title': content_info.title,
                    'uploader': content_info.uploader,
                    'filesize': os.path.getsize(filename),
                    'platform': 'tiktok',
                    'content_type': 'photo',
                    'url': url,
                    'width': 0,
                    'height': 0,
                }
                
                logger.info(f"✅ Foto descargada: {filename} ({result_info['filesize']} bytes)")
                return filename, result_info
                
        except Exception as e:
            logger.debug(f"Scraping para foto falló: {e}")
        
        # Método 3: Usar la thumbnail del video (para fotos que son en realidad videos)
        if content_info.thumbnail_url:
            try:
                img_response = self.session.get(content_info.thumbnail_url, timeout=30)
                img_response.raise_for_status()
                
                filename = os.path.join(DOWNLOAD_DIR, f'tiktok_photo_{content_info.id}_thumb.jpg')
                with open(filename, 'wb') as f:
                    f.write(img_response.content)
                
                result_info = {
                    'id': content_info.id,
                    'title': content_info.title,
                    'uploader': content_info.uploader,
                    'filesize': os.path.getsize(filename),
                    'platform': 'tiktok',
                    'content_type': 'photo',
                    'url': url,
                    'width': 0,
                    'height': 0,
                }
                
                return filename, result_info
                
            except Exception as e:
                logger.debug(f"Thumbnail falló: {e}")
        
        # Si todo falla
        raise Exception("No se pudo descargar la foto con ningún método")
    
    def _optimize_image(self, image_path: str, max_dimension: int = 2000, quality: int = 85):
        """Optimizar imagen si es muy grande"""
        try:
            from PIL import Image
            import os
            
            file_size = os.path.getsize(image_path)
            if file_size < 1024 * 1024:  # Menos de 1MB
                return
            
            with Image.open(image_path) as img:
                # Redimensionar si es muy grande
                if max(img.size) > max_dimension:
                    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                
                # Convertir a RGB si es RGBA
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img, mask=img.getchannel('A'))
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Guardar optimizado
                img.save(image_path, 'JPEG', quality=quality, optimize=True)
                
                logger.debug(f"Imagen optimizada: {file_size} -> {os.path.getsize(image_path)} bytes")
                
        except Exception as e:
            logger.warning(f"No se pudo optimizar imagen: {e}")
    
    # ============================================================================
    # MÉTODOS AUXILIARES
    # ============================================================================
    
    def cleanup(self, filepath: str):
        """Eliminar archivo temporal de forma segura"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                # También eliminar archivos relacionados
                base_name = os.path.splitext(filepath)[0]
                for ext in ['.jpg', '.jpeg', '.png', '.webp', '.part', '.ytdl']:
                    related = f"{base_name}{ext}"
                    if os.path.exists(related):
                        os.remove(related)
                logger.debug(f"Archivos limpiados: {filepath}")
        except Exception as e:
            logger.warning(f"No se pudo limpiar {filepath}: {e}")
    
    def get_file_info(self, filepath: str) -> Dict[str, Any]:
        """Obtener información detallada de un archivo"""
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
        }