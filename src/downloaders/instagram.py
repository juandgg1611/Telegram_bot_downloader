"""
Descargador de Instagram robusto
Soporta: Reels, Posts, Videos, Fotos, Stories públicas
"""
import os
import re
import json
import logging
import time
import random
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse, parse_qs, unquote
from dataclasses import dataclass

import requests
import yt_dlp
from ..config import DOWNLOAD_DIR, MAX_FILE_SIZE

logger = logging.getLogger(__name__)

# ============================================================================
# CLASES DE DATOS
# ============================================================================

@dataclass
class InstagramContentInfo:
    """Información estructurada del contenido de Instagram"""
    id: str
    content_type: str  # 'reel', 'post', 'story', 'video', 'photo'
    title: str
    username: str
    full_name: str
    description: str
    like_count: int
    comment_count: int
    view_count: int
    timestamp: int
    duration: int
    thumbnail_url: str
    download_urls: List[str]  # Múltiples URLs para respaldo
    is_video: bool
    width: int
    height: int
    media_count: int  # Para posts con múltiples elementos
    music_title: str
    music_author: str

# ============================================================================
# CLASE PRINCIPAL
# ============================================================================

class InstagramDownloader:
    """
    Descargador robusto de Instagram
    Usa múltiples métodos para evitar bloqueos
    """
    
    # Headers realistas para evitar detección
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
    
    # Servicios de terceros para descarga (sin login)
    THIRD_PARTY_SERVICES = [
        {
            'name': 'SaveFrom',
            'url': 'https://savefrom.net/api/convert',
            'method': 'POST',
            'data_key': 'url',
        },
        {
            'name': 'InstagramOnline',
            'url': 'https://www.instagramonlinedownloader.com/wp-json/aio-dl/video-data/',
            'method': 'POST',
            'data_key': 'url',
        },
        {
            'name': 'InstaDownloader',
            'url': 'https://api.instadownloader.co/api/download',
            'method': 'POST',
            'data_key': 'url',
        },
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.timeout = 30
        
        # Configuración de yt-dlp para Instagram
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
            'skip_unavailable_fragments': True,
            'outtmpl': os.path.join(DOWNLOAD_DIR, 'instagram_%(id)s.%(ext)s'),
            'restrictfilenames': True,
            'windowsfilenames': True,
            'nooverwrites': True,
            'concurrent_fragment_downloads': 2,
            'http_chunk_size': 10485760,
            'continuedl': True,
            'noprogress': True,
        }
        
        logger.info("InstagramDownloader inicializado")
    
    # ============================================================================
    # MÉTODOS DE DETECCIÓN
    # ============================================================================
    
    @classmethod
    def is_instagram_url(cls, url: str) -> Tuple[bool, str]:
        """
        Verificar si es URL de Instagram y devolver tipo
        
        Returns:
            (es_instagram, tipo_contenido)
        """
        if not url or 'instagram.com' not in url.lower() and 'instagr.am' not in url.lower():
            return False, 'invalid'
        
        url_lower = url.lower()
        
        # Detectar tipo por patrón de URL
        if '/reel/' in url_lower:
            return True, 'reel'
        elif '/p/' in url_lower:
            return True, 'post'
        elif '/stories/' in url_lower:
            return True, 'story'
        elif '/tv/' in url_lower:
            return True, 'igtv'
        elif '/video/' in url_lower:
            return True, 'video'
        else:
            # URL genérica de Instagram
            return True, 'unknown'
    
    @classmethod
    def extract_media_id(cls, url: str) -> Optional[str]:
        """Extraer ID del contenido de Instagram"""
        try:
            # Para /reel/ABC123/, /p/ABC123/, etc.
            patterns = [
                r'/(?:reel|p|tv|video)/([A-Za-z0-9_-]+)',
                r'instagram\.com/(?:reels?/)?([A-Za-z0-9_-]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            # Intentar extraer de parámetros
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            if 'id' in query_params:
                return query_params['id'][0]
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extrayendo ID: {e}")
            return None
    
    # ============================================================================
    # MÉTODOS DE OBTENCIÓN DE INFORMACIÓN
    # ============================================================================
    
    def get_content_info(self, url: str) -> InstagramContentInfo:
        """
        Obtener información del contenido usando múltiples métodos
        
        Returns:
            InstagramContentInfo (nunca vacío)
        """
        # Información por defecto
        default_info = InstagramContentInfo(
            id=self.extract_media_id(url) or f"ig_{int(time.time())}",
            content_type='unknown',
            title='Contenido de Instagram',
            username='instagram_user',
            full_name='Usuario de Instagram',
            description='',
            like_count=0,
            comment_count=0,
            view_count=0,
            timestamp=int(time.time()),
            duration=0,
            thumbnail_url='',
            download_urls=[],
            is_video=False,
            width=0,
            height=0,
            media_count=1,
            music_title='',
            music_author='',
        )
        
        # Determinar tipo de contenido
        is_instagram, content_type = self.is_instagram_url(url)
        default_info.content_type = content_type
        
        # Intentar obtener info real usando múltiples métodos
        info = None
        
        # Método 1: GraphQL público (más confiable)
        info = self._get_info_graphql(url, default_info)
        
        # Método 2: oEmbed API (oficial de Instagram)
        if not info or not info.download_urls:
            info = self._get_info_oembed(url, default_info)
        
        # Método 3: Web scraping del HTML
        if not info or not info.download_urls:
            info = self._get_info_html(url, default_info)
        
        # Método 4: Usar yt-dlp como último recurso
        if not info or not info.download_urls:
            info = self._get_info_ytdlp(url, default_info)
        
        # Si después de todo no tenemos info, usar la por defecto
        if not info:
            info = default_info
        
        logger.info(f"Info obtenida: {info.content_type} - {info.username}")
        return info
    
    def _get_info_graphql(self, url: str, default_info: InstagramContentInfo) -> Optional[InstagramContentInfo]:
        """Obtener información usando GraphQL público de Instagram"""
        try:
            # Primero obtener la página HTML
            response = self.session.get(url, timeout=15)
            html = response.text
            
            # Buscar datos GraphQL en el HTML
            graphql_patterns = [
                r'window\.__additionalDataLoaded\s*\(\s*[^,]+\s*,\s*({.*?})\s*\)',
                r'window\._sharedData\s*=\s*({.*?});',
                r'"graphql"\s*:\s*({.*?})\s*,',
                r'"video_url"\s*:\s*"([^"]+)"',
                r'"display_url"\s*:\s*"([^"]+)"',
            ]
            
            for pattern in graphql_patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                for match in matches:
                    try:
                        if isinstance(match, str) and match.startswith('{'):
                            data = json.loads(match)
                            
                            # Navegar por la estructura GraphQL
                            media_data = self._extract_from_graphql(data)
                            
                            if media_data and media_data.get('urls'):
                                return InstagramContentInfo(
                                    id=media_data.get('id', default_info.id),
                                    content_type=media_data.get('type', default_info.content_type),
                                    title=media_data.get('title', 'Instagram'),
                                    username=media_data.get('username', default_info.username),
                                    full_name=media_data.get('full_name', default_info.full_name),
                                    description=media_data.get('description', ''),
                                    like_count=media_data.get('like_count', 0),
                                    comment_count=media_data.get('comment_count', 0),
                                    view_count=media_data.get('view_count', 0),
                                    timestamp=media_data.get('timestamp', int(time.time())),
                                    duration=media_data.get('duration', 0),
                                    thumbnail_url=media_data.get('thumbnail', ''),
                                    download_urls=media_data.get('urls', []),
                                    is_video=media_data.get('is_video', False),
                                    width=media_data.get('width', 0),
                                    height=media_data.get('height', 0),
                                    media_count=media_data.get('media_count', 1),
                                    music_title=media_data.get('music_title', ''),
                                    music_author=media_data.get('music_author', ''),
                                )
                        
                        # Si el match es una URL directa
                        elif isinstance(match, str) and match.startswith('http'):
                            return InstagramContentInfo(
                                **{**default_info.__dict__, 'download_urls': [match]}
                            )
                            
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"GraphQL falló: {e}")
            return None
    
    def _extract_from_graphql(self, data: Dict) -> Optional[Dict]:
        """Extraer información de la estructura GraphQL"""
        try:
            # Diferentes estructuras GraphQL de Instagram
            structures = [
                ['graphql', 'shortcode_media'],
                ['entry_data', 'PostPage', 0, 'graphql', 'shortcode_media'],
                ['entry_data', 'PostPage', 0, 'graphql', 'shortcode_media', 'edge_sidecar_to_children', 'edges'],
                ['items', 0],
                ['media'],
            ]
            
            for structure in structures:
                current = data
                valid = True
                
                for key in structure:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    elif isinstance(current, list) and isinstance(key, int) and key < len(current):
                        current = current[key]
                    else:
                        valid = False
                        break
                
                if valid and current:
                    return self._parse_media_data(current)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extrayendo GraphQL: {e}")
            return None
    
    def _parse_media_data(self, media_data: Any) -> Dict:
        """Parsear datos de media de Instagram"""
        result = {
            'id': '',
            'type': 'unknown',
            'title': '',
            'username': '',
            'full_name': '',
            'description': '',
            'like_count': 0,
            'comment_count': 0,
            'view_count': 0,
            'timestamp': int(time.time()),
            'duration': 0,
            'thumbnail': '',
            'urls': [],
            'is_video': False,
            'width': 0,
            'height': 0,
            'media_count': 1,
            'music_title': '',
            'music_author': '',
        }
        
        try:
            # ID
            result['id'] = media_data.get('id') or media_data.get('shortcode') or ''
            
            # Tipo y datos básicos
            if 'is_video' in media_data:
                result['is_video'] = media_data['is_video']
                result['type'] = 'video' if media_data['is_video'] else 'photo'
            
            # Usuario
            if 'owner' in media_data:
                owner = media_data['owner']
                result['username'] = owner.get('username', '')
                result['full_name'] = owner.get('full_name', '')
            
            # Descripción
            if 'edge_media_to_caption' in media_data:
                edges = media_data['edge_media_to_caption'].get('edges', [])
                if edges:
                    result['description'] = edges[0].get('node', {}).get('text', '')
            
            # Estadísticas
            if 'edge_media_preview_like' in media_data:
                result['like_count'] = media_data['edge_media_preview_like'].get('count', 0)
            
            if 'edge_media_to_comment' in media_data:
                result['comment_count'] = media_data['edge_media_to_comment'].get('count', 0)
            
            if 'video_view_count' in media_data:
                result['view_count'] = media_data['video_view_count']
            
            # URLs de media
            if result['is_video']:
                if 'video_url' in media_data:
                    result['urls'].append(media_data['video_url'])
                if 'video_versions' in media_data:
                    for version in media_data['video_versions']:
                        result['urls'].append(version.get('url', ''))
            else:
                if 'display_url' in media_data:
                    result['urls'].append(media_data['display_url'])
                if 'display_resources' in media_data:
                    for resource in media_data['display_resources']:
                        result['urls'].append(resource.get('src', ''))
            
            # Thumbnail
            if 'thumbnail_src' in media_data:
                result['thumbnail'] = media_data['thumbnail_src']
            elif 'display_url' in media_data:
                result['thumbnail'] = media_data['display_url']
            
            # Dimensiones
            if 'dimensions' in media_data:
                result['width'] = media_data['dimensions'].get('width', 0)
                result['height'] = media_data['dimensions'].get('height', 0)
            
            # Música (para Reels)
            if 'clips_music_attribution_info' in media_data:
                music = media_data['clips_music_attribution_info']
                result['music_title'] = music.get('song_name', '')
                result['music_author'] = music.get('artist_name', '')
            
        except Exception as e:
            logger.debug(f"Error parseando media: {e}")
        
        return result
    
    def _get_info_oembed(self, url: str, default_info: InstagramContentInfo) -> Optional[InstagramContentInfo]:
        """Obtener información usando oEmbed API oficial"""
        try:
            oembed_url = f"https://graph.facebook.com/v18.0/instagram_oembed"
            params = {
                'url': url,
                'access_token': 'EAAGNOkqZB8PcBO2q7cDZA9YrxbPbyZCVIqvyzr41G4P3s3ZBlWENJBjVZC4z9U8qZAsTQx9NZC2VQmFZAcPeYC6jD9oPChrZB4Hv6ZCYlK2TpoQZBlKfdHajj3ZAiS5K5lGZC2CvgNWmZA4qSd8tGSJqoXoZBq0NAlpFdPZA3nps03c4MLvQZDZD',  # Token público limitado
                'fields': 'title,author_name,thumbnail_url,width,height'
            }
            
            response = self.session.get(oembed_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                return InstagramContentInfo(
                    id=default_info.id,
                    content_type=default_info.content_type,
                    title=data.get('title', default_info.title),
                    username=data.get('author_name', '').replace('@', ''),
                    full_name=data.get('author_name', default_info.full_name),
                    description='',
                    like_count=0,
                    comment_count=0,
                    view_count=0,
                    timestamp=int(time.time()),
                    duration=0,
                    thumbnail_url=data.get('thumbnail_url', ''),
                    download_urls=[data.get('thumbnail_url', '')],
                    is_video=True,  # oEmbed generalmente devuelve thumbnails
                    width=data.get('width', 0),
                    height=data.get('height', 0),
                    media_count=1,
                    music_title='',
                    music_author='',
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"oEmbed falló: {e}")
            return None
    
    def _get_info_html(self, url: str, default_info: InstagramContentInfo) -> Optional[InstagramContentInfo]:
        """Obtener información mediante web scraping básico"""
        try:
            response = self.session.get(url, timeout=15)
            html = response.text
            
            # Buscar metadatos en HTML
            meta_patterns = {
                'title': r'<title[^>]*>(.*?)</title>',
                'description': r'"description"\s*content="([^"]+)"',
                'video_url': r'"video_url"\s*content="([^"]+)"',
                'image_url': r'"og:image"\s*content="([^"]+)"',
                'username': r'"username"\s*content="([^"]+)"',
            }
            
            extracted = {}
            for key, pattern in meta_patterns.items():
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    extracted[key] = match.group(1)
            
            # Si encontramos URLs
            urls = []
            if 'video_url' in extracted:
                urls.append(extracted['video_url'])
            if 'image_url' in extracted:
                urls.append(extracted['image_url'])
            
            if urls:
                return InstagramContentInfo(
                    id=default_info.id,
                    content_type=default_info.content_type,
                    title=extracted.get('title', '').replace('• Instagram', '').strip(),
                    username=extracted.get('username', default_info.username),
                    full_name=extracted.get('username', default_info.full_name),
                    description=extracted.get('description', '')[:200],
                    like_count=0,
                    comment_count=0,
                    view_count=0,
                    timestamp=int(time.time()),
                    duration=0,
                    thumbnail_url=extracted.get('image_url', ''),
                    download_urls=urls,
                    is_video='video_url' in extracted,
                    width=0,
                    height=0,
                    media_count=1,
                    music_title='',
                    music_author='',
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"HTML scraping falló: {e}")
            return None
    
    def _get_info_ytdlp(self, url: str, default_info: InstagramContentInfo) -> Optional[InstagramContentInfo]:
        """Obtener información usando yt-dlp"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                urls = []
                if info.get('url'):
                    urls.append(info['url'])
                
                # Para formatos disponibles
                for fmt in info.get('formats', []):
                    if fmt.get('url'):
                        urls.append(fmt['url'])
                
                return InstagramContentInfo(
                    id=info.get('id', default_info.id),
                    content_type=info.get('extractor_key', 'unknown').lower(),
                    title=info.get('title', default_info.title),
                    username=info.get('uploader', default_info.username),
                    full_name=info.get('uploader', default_info.full_name),
                    description=info.get('description', ''),
                    like_count=info.get('like_count', 0),
                    comment_count=info.get('comment_count', 0),
                    view_count=info.get('view_count', 0),
                    timestamp=info.get('timestamp', int(time.time())),
                    duration=info.get('duration', 0),
                    thumbnail_url=info.get('thumbnail', ''),
                    download_urls=urls,
                    is_video=info.get('duration', 0) > 0,
                    width=info.get('width', 0),
                    height=info.get('height', 0),
                    media_count=1,
                    music_title=info.get('track', ''),
                    music_author=info.get('artist', ''),
                )
                
        except Exception as e:
            logger.debug(f"yt-dlp info falló: {e}")
            return None
    
    # ============================================================================
    # MÉTODOS DE DESCARGA
    # ============================================================================
    
    def download(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Descargar contenido de Instagram
        
        Returns:
            (ruta_archivo, información)
        """
        # Verificar URL
        is_instagram, content_type = self.is_instagram_url(url)
        if not is_instagram:
            raise ValueError("URL de Instagram no válida")
        
        # Obtener información
        content_info = self.get_content_info(url)
        
        logger.info(f"Descargando Instagram {content_type}: {content_info.id}")
        
        # Intentar múltiples métodos de descarga
        filepath, result_info = None, None
        
        # Método 1: Descarga directa desde URLs obtenidas
        if content_info.download_urls:
            for i, download_url in enumerate(content_info.download_urls):
                if download_url:
                    try:
                        logger.info(f"Intento {i+1}: Descarga directa")
                        filepath, result_info = self._download_direct(download_url, content_info)
                        if filepath:
                            break
                    except Exception as e:
                        logger.debug(f"Descarga directa {i+1} falló: {e}")
        
        # Método 2: Usar yt-dlp
        if not filepath:
            try:
                logger.info("Intento: yt-dlp")
                filepath, result_info = self._download_ytdlp(url, content_info)
            except Exception as e:
                logger.debug(f"yt-dlp falló: {e}")
        
        # Método 3: Usar servicios de terceros
        if not filepath:
            for service in self.THIRD_PARTY_SERVICES:
                try:
                    logger.info(f"Intento: {service['name']}")
                    filepath, result_info = self._download_via_service(url, content_info, service)
                    if filepath:
                        break
                except Exception as e:
                    logger.debug(f"Servicio {service['name']} falló: {e}")
        
        # Si todo falló
        if not filepath:
            raise Exception("No se pudo descargar el contenido con ningún método. Instagram puede estar bloqueando las descargas.")
        
        # Verificar tamaño
        if os.path.getsize(filepath) > MAX_FILE_SIZE:
            self.cleanup(filepath)
            raise ValueError(f"Archivo demasiado grande ({os.path.getsize(filepath)} bytes)")
        
        return filepath, result_info
    
    def _download_direct(self, download_url: str, content_info: InstagramContentInfo) -> Tuple[str, Dict[str, Any]]:
        """Descarga directa desde URL"""
        try:
            # Determinar extensión
            parsed = urlparse(download_url)
            path = parsed.path.lower()
            
            if content_info.is_video:
                ext = '.mp4'
                if '.mp4' in path:
                    ext = '.mp4'
                elif '.mov' in path:
                    ext = '.mov'
            else:
                ext = '.jpg'
                if '.jpg' in path or '.jpeg' in path:
                    ext = '.jpg'
                elif '.png' in path:
                    ext = '.png'
                elif '.webp' in path:
                    ext = '.webp'
            
            # Nombre de archivo
            filename = os.path.join(
                DOWNLOAD_DIR, 
                f"instagram_{content_info.content_type}_{content_info.id}{ext}"
            )
            
            # Descargar
            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verificar que se descargó
            if not os.path.exists(filename) or os.path.getsize(filename) == 0:
                raise ValueError("Archivo descargado vacío")
            
            # Información de resultado
            result_info = {
                'id': content_info.id,
                'title': content_info.title[:100],
                'username': content_info.username,
                'full_name': content_info.full_name,
                'filesize': os.path.getsize(filename),
                'platform': 'instagram',
                'content_type': content_info.content_type,
                'media_type': 'video' if content_info.is_video else 'photo',
                'url': download_url,
                'duration': content_info.duration,
                'like_count': content_info.like_count,
                'comment_count': content_info.comment_count,
                'view_count': content_info.view_count,
            }
            
            logger.info(f"✅ Descarga directa exitosa: {filename} ({result_info['filesize']} bytes)")
            return filename, result_info
            
        except Exception as e:
            logger.error(f"Error en descarga directa: {e}")
            raise
    
    def _download_ytdlp(self, url: str, content_info: InstagramContentInfo) -> Tuple[str, Dict[str, Any]]:
        """Descargar usando yt-dlp"""
        try:
            # Configurar opciones específicas para Instagram
            ydl_opts = {
                **self.ydl_opts,
                'format': 'best[height<=720]/best',
                'outtmpl': os.path.join(
                    DOWNLOAD_DIR, 
                    f"instagram_{content_info.content_type}_{content_info.id}.%(ext)s"
                ),
                'referer': 'https://www.instagram.com/',
                'http_headers': self.HEADERS,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Descargar
                ydl.download([url])
                
                # Buscar archivo descargado
                pattern = os.path.join(DOWNLOAD_DIR, f"instagram_{content_info.content_type}_{content_info.id}*")
                import glob
                downloaded_files = glob.glob(pattern)
                
                if not downloaded_files:
                    # Buscar cualquier archivo de Instagram reciente
                    all_files = [f for f in os.listdir(DOWNLOAD_DIR) if 'instagram' in f.lower()]
                    if all_files:
                        downloaded_files = [os.path.join(DOWNLOAD_DIR, 
                                         max(all_files, key=lambda f: os.path.getctime(os.path.join(DOWNLOAD_DIR, f))))]
                
                if not downloaded_files:
                    raise FileNotFoundError("No se encontró archivo descargado")
                
                filepath = downloaded_files[0]
                
                # Normalizar extensión
                if content_info.is_video and not filepath.endswith('.mp4'):
                    new_path = os.path.splitext(filepath)[0] + '.mp4'
                    os.rename(filepath, new_path)
                    filepath = new_path
                
                # Información de resultado
                result_info = {
                    'id': content_info.id,
                    'title': content_info.title[:100],
                    'username': content_info.username,
                    'full_name': content_info.full_name,
                    'filesize': os.path.getsize(filepath),
                    'platform': 'instagram',
                    'content_type': content_info.content_type,
                    'media_type': 'video' if content_info.is_video else 'photo',
                    'url': url,
                    'duration': content_info.duration,
                    'like_count': content_info.like_count,
                    'comment_count': content_info.comment_count,
                    'view_count': content_info.view_count,
                }
                
                logger.info(f"✅ yt-dlp exitoso: {filepath} ({result_info['filesize']} bytes)")
                return filepath, result_info
                
        except Exception as e:
            logger.error(f"Error en yt-dlp: {e}")
            raise
    
    def _download_via_service(self, url: str, content_info: InstagramContentInfo, 
                            service: Dict) -> Tuple[str, Dict[str, Any]]:
        """Descargar usando servicio de terceros"""
        try:
            if service['method'] == 'POST':
                response = self.session.post(
                    service['url'],
                    data={service['data_key']: url},
                    timeout=30
                )
            else:
                response = self.session.get(
                    service['url'],
                    params={service['data_key']: url},
                    timeout=30
                )
            
            if response.status_code != 200:
                raise ValueError(f"Servicio respondió con código {response.status_code}")
            
            data = response.json()
            
            # Buscar URL de descarga en la respuesta
            download_url = None
            possible_keys = ['url', 'download_url', 'video_url', 'media_url', 'link']
            
            for key in possible_keys:
                if key in data:
                    download_url = data[key]
                    break
            
            if not download_url:
                # Buscar en estructuras anidadas
                for value in data.values():
                    if isinstance(value, str) and value.startswith('http'):
                        download_url = value
                        break
            
            if not download_url:
                raise ValueError("No se encontró URL de descarga en la respuesta")
            
            # Descargar desde la URL obtenida
            return self._download_direct(download_url, content_info)
            
        except Exception as e:
            logger.error(f"Error con servicio {service['name']}: {e}")
            raise
    
    # ============================================================================
    # MÉTODOS AUXILIARES
    # ============================================================================
    
    def cleanup(self, filepath: str):
        """Eliminar archivo temporal"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                
                # Eliminar archivos relacionados
                base_name = os.path.splitext(filepath)[0]
                for ext in ['.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.part', '.ytdl']:
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