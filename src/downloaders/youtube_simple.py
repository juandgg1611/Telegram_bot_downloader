"""
Descargador SIMPLE de YouTube usando pytubefix
"""
import os
import re
import logging
import subprocess
import json
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'downloads')

class YouTubeSimpleDownloader:
    """
    Descargador SIMPLE de YouTube usando pytubefix con PO Token
    """
    
    def __init__(self, default_quality: str = '720p'):
        self.default_quality = default_quality
        
        # Intentar importar pytubefix
        try:
            from pytubefix import YouTube
            self.YouTube = YouTube
            self.pytubefix_available = True
            logger.info("✅ pytubefix disponible - usando con PO Token")
        except ImportError:
            logger.warning("⚠️ pytubefix no disponible - usando fallback")
            self.pytubefix_available = False
        
        # Verificar generador de PO Token
        self.po_token_available = self._check_po_token_generator()
        logger.info(f"YouTubeSimpleDownloader inicializado. PO Token: {self.po_token_available}")
    
    def _check_po_token_generator(self) -> bool:
        """Verificar si youtube-po-token-generator está disponible"""
        try:
            result = subprocess.run(
                ['which', 'youtube-po-token-generator'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _get_po_token(self) -> Optional[Dict[str, str]]:
        """Obtener PO Token si el generador está disponible"""
        if not self.po_token_available:
            return None
        
        try:
            result = subprocess.run(
                ['youtube-po-token-generator'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                token_data = json.loads(result.stdout.strip())
                logger.info("✅ PO Token generado")
                return token_data
        except Exception as e:
            logger.warning(f"⚠️  No se pudo generar PO Token: {e}")
        
        return None
    
    def is_youtube_url(self, url: str) -> bool:
        """Verificar si es URL de YouTube"""
        patterns = [
            r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/',
            r'(https?://)?(m\.)?youtube\.com/',
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns)
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extraer ID del video"""
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'(?:youtu\.be/)([0-9A-Za-z_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Obtener información básica del video"""
        video_id = self.extract_video_id(url)
        
        if not self.pytubefix_available:
            return {
                'id': video_id or 'unknown',
                'title': 'Video de YouTube',
                'duration': 0,
                'channel': 'YouTube',
                'thumbnail': '',
            }
        
        try:
            # Obtener PO Token si está disponible
            po_token = self._get_po_token()
            
            # Crear objeto YouTube con/sin PO Token
            if po_token and self.po_token_available:
                yt = self.YouTube(url, use_po_token=True)
            else:
                yt = self.YouTube(url)
            
            return {
                'id': video_id,
                'title': yt.title,
                'duration': yt.length,
                'channel': yt.author,
                'thumbnail': yt.thumbnail_url,
                'views': yt.views,
            }
        except Exception as e:
            logger.error(f"Error obteniendo info: {e}")
            return {
                'id': video_id or 'unknown',
                'title': 'Video de YouTube',
                'duration': 0,
                'channel': 'YouTube',
                'thumbnail': '',
                'views': 0,
            }
    
    def download_audio(self, url: str, format: str = 'm4a') -> Tuple[str, Dict[str, Any]]:
        """
        Descargar audio de YouTube usando pytubefix
        """
        if not self.is_youtube_url(url):
            raise ValueError("URL de YouTube no válida")
        
        video_id = self.extract_video_id(url)
        if not video_id:
            raise ValueError("No se pudo extraer ID del video")
        
        if not self.pytubefix_available:
            raise ImportError("pytubefix no está instalado")
        
        print(f"\n🎵 Descargando audio: {video_id}")
        
        try:
            # Obtener PO Token si está disponible
            po_token = self._get_po_token()
            
            # Crear objeto YouTube con/sin PO Token
            if po_token and self.po_token_available:
                print("🔐 Usando PO Token para autenticación")
                yt = self.YouTube(url, use_po_token=True)
            else:
                print("⚠️  Usando pytubefix sin PO Token")
                yt = self.YouTube(url)
            
            print(f"📋 Título: {yt.title}")
            print(f"🎬 Canal: {yt.author}")
            print(f"⏱ Duración: {yt.length}s")
            
            # Buscar mejor stream de audio
            if format == 'm4a':
                # Preferir audio M4A (AAC)
                audio_stream = yt.streams.filter(
                    only_audio=True,
                    mime_type="audio/mp4"
                ).order_by('abr').desc().first()
            else:
                # Cualquier audio
                audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            
            if not audio_stream:
                raise ValueError("No se encontró stream de audio")
            
            print(f"🎵 Calidad de audio: {audio_stream.abr}")
            print(f"📦 Codec: {audio_stream.codecs[0] if audio_stream.codecs else 'Desconocido'}")
            
            # Descargar
            filename = f"youtube_{video_id}_{yt.title[:50]}.{format}"
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            
            print(f"⬇️  Descargando...")
            audio_stream.download(output_path=DOWNLOAD_DIR, filename=filename)
            
            print(f"✅ Descarga completada: {os.path.basename(filepath)}")
            
            return filepath, {
                'id': video_id,
                'title': yt.title[:100],
                'channel': yt.author,
                'duration': yt.length,
                'filesize': os.path.getsize(filepath),
                'platform': 'youtube',
                'content_type': 'audio',
                'format': format,
                'method': 'pytubefix_with_po_token' if po_token else 'pytubefix',
                'bitrate': audio_stream.abr,
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error descargando: {error_msg}")
            raise Exception(f"No se pudo descargar el audio: {error_msg}")