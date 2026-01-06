"""
Módulo para descargar contenido de Pinterest.
Soporta: imágenes (JPG, PNG, WebP), videos, Pins múltiples (carruseles).
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

# yt-dlp puede servir como respaldo para algunos recursos
import yt_dlp
from ..config import DOWNLOAD_DIR, MAX_FILE_SIZE  

logger = logging.getLogger(__name__)

# ============================================================================
# CLASES DE DATOS
# ============================================================================
@dataclass
class PinterestContentInfo:
    """Información estructurada del contenido de Pinterest."""
    id: str
    content_type: str  
    title: str
    description: str
    uploader: str  
    source_url: Optional[str]  
    pinterest_url: str  
    download_urls: List[str]  
    width: int
    height: int
    duration: Optional[int] = None  
    is_video: bool = False

# ============================================================================
# CLASE PRINCIPAL
# ============================================================================
class PinterestDownloader:
    """
    Descargador de contenido de Pinterest.
    Estrategia:
    1. Intentar obtener metadatos y URLs directas vía la API oficial (si hay token).
    2. Recurrir a web scraping y búsqueda de metadatos Open Graph como respaldo.
    """
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

    # Patrones para identificar URLs de Pinterest
    URL_PATTERNS = {
        'pin': r'https?://(?:www\.)?pinterest\.(?:com|fr|de|co\.uk|ru|etc)/pin/(\d+)',
        'image': r'https?://(?:www\.)?pinterest\.(?:com|fr|de|co\.uk|ru|etc)/[^/]+/[^/]+/',
        # Los videos en Pinterest suelen ser Pins con recursos .mp4
    }

    def __init__(self, api_token: Optional[str] = None):
        """
        Inicializa el descargador.
        :param api_token: Token OAuth de la API de Pinterest (opcional, pero recomendado).
        """
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    # ------------------------------------------------------------------------
    # MÉTODOS DE DETECCIÓN Y EXTRACCIÓN DE INFORMACIÓN
    # ------------------------------------------------------------------------
    @classmethod
    def is_pinterest_url(cls, url: str) -> bool:
        """Verifica si una URL es de Pinterest."""
        return any(re.match(pattern, url) for pattern in cls.URL_PATTERNS.values())

    def extract_pin_id(self, url: str) -> Optional[str]:
        """Extrae el ID del Pin de la URL."""
        match = re.search(self.URL_PATTERNS['pin'], url)
        return match.group(1) if match else None

    def get_content_info(self, url: str) -> PinterestContentInfo:
        """
        Obtiene metadatos del Pin. Combina API y scraping.
        """
        pin_id = self.extract_pin_id(url)
        content_info = None

        # 1. Intento principal: Usar la API oficial de Pinterest (si tenemos token)
        if self.api_token and pin_id:
            content_info = self._get_info_via_api(pin_id)

        # 2. Intento de respaldo: Scraping de la página web
        if not content_info:
            content_info = self._get_info_via_scraping(url)

        # Si todo falla, devolver información básica
        if not content_info:
            content_info = PinterestContentInfo(
                id=pin_id or f"pin_{int(time.time())}",
                content_type='unknown',
                title='Pin de Pinterest',
                description='',
                uploader='',
                source_url=None,
                pinterest_url=url,
                download_urls=[],
                width=0,
                height=0
            )

        return content_info

    def _get_info_via_api(self, pin_id: str) -> Optional[PinterestContentInfo]:
        """Intenta obtener información usando la API oficial v5."""
        if not self.api_token:
            return None

        try:
            url = f"https://api.pinterest.com/v5/pins/{pin_id}"
            headers = {
                'Authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json'
            }
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extraer URLs de medios. La estructura puede variar.
            download_urls = []
            media_type = 'image'

            # Para imágenes
            if 'images' in data and 'orig' in data['images']:
                download_urls.append(data['images']['orig']['url'])
                # También puedes añadir otros tamaños: data['images'].get('736x', {}).get('url')
            # Para videos
            if 'videos' in data and 'video_list' in data['videos']:
                # Buscar la mejor calidad disponible
                video_data = data['videos']['video_list']
                if 'V_720P' in video_data:
                    download_urls.append(video_data['V_720P']['url'])
                elif 'V_HLSV3' in video_data:
                    download_urls.append(video_data['V_HLSV3']['url'])
                media_type = 'video'

            return PinterestContentInfo(
                id=data.get('id', pin_id),
                content_type=media_type,
                title=data.get('title', data.get('alt_text', '')),
                description=data.get('description', data.get('alt_text', '')),
                uploader=data.get('board_owner', {}).get('username', ''),
                source_url=data.get('link', None),
                pinterest_url=data.get('url', f'https://pinterest.com/pin/{pin_id}'),
                download_urls=download_urls,
                width=data.get('images', {}).get('orig', {}).get('width', 0),
                height=data.get('images', {}).get('orig', {}).get('height', 0),
                is_video=(media_type == 'video')
            )

        except Exception as e:
            logger.debug(f"API oficial falló para {pin_id}: {e}")
            return None

    def _get_info_via_scraping(self, url: str) -> Optional[PinterestContentInfo]:
        """
        Método de respaldo: Extrae información analizando el HTML de la página.
        Busca metadatos Open Graph y enlaces a recursos.
        """
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            html = response.text

            # Extraer metadatos Open Graph (muy comunes en Pinterest)
            title = self._extract_og_tag(html, 'og:title')
            description = self._extract_og_tag(html, 'og:description')
            image_url = self._extract_og_tag(html, 'og:image')
            video_url = self._extract_og_tag(html, 'og:video')

            download_urls = []
            media_type = 'image'
            if video_url:
                download_urls.append(video_url)
                media_type = 'video'
            elif image_url:
                download_urls.append(image_url)

            # Intentar encontrar más imágenes (para carruseles) en JSON estructurado
            # Pinterest suele incluir datos en <script id="__PWS_DATA__">
            script_pattern = r'<script id="__PWS_DATA__" type="application/json">(.*?)</script>'
            match = re.search(script_pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    # La estructura de datos es compleja y cambia a menudo.
                    # Necesitarás explorarla para encontrar las URLs de las imágenes/videos.
                    # Por ejemplo, podrías buscar 'images', 'url', 'video_assets', etc.
                except json.JSONDecodeError:
                    pass

            return PinterestContentInfo(
                id=self.extract_pin_id(url) or f"scraped_{int(time.time())}",
                content_type=media_type,
                title=title or 'Pin de Pinterest',
                description=description or '',
                uploader='',  # Difícil de obtener sin API
                source_url=self._extract_og_tag(html, 'og:url'),
                pinterest_url=url,
                download_urls=download_urls,
                width=0,  # Tendrías que extraerlo de otros metadatos o descargar la imagen
                height=0,
                is_video=(media_type == 'video')
            )

        except Exception as e:
            logger.debug(f"Scraping falló para {url}: {e}")
            return None

    def _extract_og_tag(self, html: str, property_name: str) -> Optional[str]:
        """Extrae el contenido de una metaetiqueta Open Graph."""
        pattern = f'<meta property="{property_name}" content="([^"]*)"'
        match = re.search(pattern, html)
        return match.group(1) if match else None

    # ------------------------------------------------------------------------
    # MÉTODO PRINCIPAL DE DESCARGA
    # ------------------------------------------------------------------------
    def download(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Descarga el contenido de un Pin de Pinterest.
        :return: (ruta_al_archivo, información_del_contenido)
        """
        if not self.is_pinterest_url(url):
            raise ValueError("URL de Pinterest no válida.")

        content_info = self.get_content_info(url)

        if not content_info.download_urls:
            raise ValueError("No se pudieron encontrar enlaces de descarga para este Pin.")

        # Descargar el primer recurso disponible (podrías extenderlo para carruseles)
        download_url = content_info.download_urls[0]
        filepath = self._download_resource(download_url, content_info)

        # Verificar tamaño del archivo
        if os.path.getsize(filepath) > MAX_FILE_SIZE:
            os.remove(filepath)
            raise ValueError(f"Archivo demasiado grande (> {MAX_FILE_SIZE} bytes).")

        # Preparar información de resultado
        result_info = {
            'id': content_info.id,
            'title': content_info.title[:100],
            'uploader': content_info.uploader,
            'content_type': content_info.content_type,
            'is_video': content_info.is_video,
            'pinterest_url': content_info.pinterest_url,
            'source_url': content_info.source_url,
            'file_size': os.path.getsize(filepath),
            'file_path': filepath
        }

        logger.info(f"✅ Descargado: {filepath}")
        return filepath, result_info

    def _download_resource(self, url: str, info: PinterestContentInfo) -> str:
        """
        Descarga un recurso (imagen o video) desde una URL directa.
        """
        # Determinar extensión del archivo
        parsed_url = urlparse(url)
        # Extraer extensión del path o de parámetros
        path_ext = os.path.splitext(parsed_url.path)[1]
        if path_ext:
            # Limpiar la extensión (p.ej., .jpg?1234 -> .jpg)
            ext = path_ext.split('?')[0].lower()
        else:
            # Asignar extensión por defecto basada en el tipo
            ext = '.mp4' if info.is_video else '.jpg'

        # Crear nombre de archivo seguro
        safe_title = re.sub(r'[^\w\-_\. ]', '_', info.title[:50])
        filename = f"pinterest_{info.id}_{safe_title}{ext}"
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        # Descargar con requests
        response = self.session.get(url, stream=True, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return filepath

    # ------------------------------------------------------------------------
    # MÉTODOS AUXILIARES
    # ------------------------------------------------------------------------
    def cleanup(self, filepath: str):
        """Elimina un archivo descargado."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.warning(f"No se pudo eliminar {filepath}: {e}")