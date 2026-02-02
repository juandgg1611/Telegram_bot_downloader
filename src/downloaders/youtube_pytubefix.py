"""
Descargador de YouTube usando pytubefix con PO Token
Basado en: https://github.com/JuanBindez/pytubefix
"""
import os
import re
import logging
import time
import shutil
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

from pytubefix import YouTube
from pytubefix.cli import on_progress

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'downloads')

class YouTubeDownloaderPytubefix:
    """
    Descargador de YouTube usando pytubefix con soporte PO Token
    """
    
    def __init__(self, default_quality: str = '720p'):
        """
        Inicializar descargador con pytubefix
        
        Args:
            default_quality: Calidad por defecto para videos
        """
        self.default_quality = default_quality
        self.cookies_path = 'cookies.txt'
        self.has_cookies = os.path.exists(self.cookies_path)
        
        if self.has_cookies:
            logger.info(f"✅ Usando cookies de YouTube desde: {self.cookies_path}")
        else:
            logger.warning("⚠️ No se encontró archivo cookies.txt")
        
        # Verificar si podemos generar PO Token
        self.po_token_available = self._check_po_token_support()
        
        logger.info(f"YouTubeDownloaderPytubefix inicializado con calidad: {default_quality}")
    
    def _check_po_token_support(self) -> bool:
        """Verificar si tenemos soporte para PO Token"""
        try:
            # Intentar importar el generador de PO Token
            import subprocess
            result = subprocess.run(
                ['which', 'youtube-po-token-generator'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def _generate_po_token(self) -> Optional[Dict[str, str]]:
        """Generar PO Token usando youtube-po-token-generator"""
        try:
            import subprocess
            import json
            
            # Ejecutar generador de PO Token
            result = subprocess.run(
                ['youtube-po-token-generator'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                token_data = json.loads(result.stdout.strip())
                logger.info("✅ PO Token generado exitosamente")
                return token_data
            else:
                logger.error(f"❌ Error generando PO Token: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error en generación PO Token: {e}")
            return None
    
    def is_youtube_url(self, url: str) -> bool:
        """Verificar si es una URL de YouTube"""
        patterns = [
            r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/',
            r'(https?://)?(m\.)?youtube\.com/',
            r'(https?://)?(music\.)?youtube\.com/',
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns)
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extraer ID del video"""
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'(?:youtu\.be/)([0-9A-Za-z_-]{11})',
            r'(?:embed/)([0-9A-Za-z_-]{11})',
            r'(?:shorts/)([0-9A-Za-z_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Obtener información del video"""
        video_id = self.extract_video_id(url)
        
        try:
            # Usar pytubefix para obtener info
            yt = YouTube(url, use_po_token=self.po_token_available)
            
            return {
                'id': video_id or 'unknown',
                'title': yt.title,
                'duration': yt.length,
                'author': yt.author,
                'channel': yt.author,
                'view_count': yt.views,
                'description': yt.description[:500] if yt.description else '',
                'thumbnail_url': yt.thumbnail_url,
                'publish_date': str(yt.publish_date) if yt.publish_date else '',
                'age_restricted': yt.age_restricted,
                'streams_count': len(yt.streams),
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo info: {e}")
            return {
                'id': video_id or 'unknown',
                'title': 'Video de YouTube',
                'duration': 0,
                'author': 'YouTube',
                'channel': 'YouTube',
                'view_count': 0,
                'description': '',
                'thumbnail_url': '',
                'publish_date': '',
                'age_restricted': False,
                'streams_count': 0,
            }
    
    def download_video(self, url: str, quality: str = None) -> Tuple[str, Dict[str, Any]]:
        """Descargar video completo (con audio)"""
        if not self.is_youtube_url(url):
            raise ValueError("URL de YouTube no válida")
        
        quality = quality or self.default_quality
        video_id = self.extract_video_id(url)
        logger.info(f"Descargando video {video_id} en calidad {quality}")
        
        try:
            # Inicializar YouTube con PO Token si está disponible
            yt = YouTube(
                url, 
                use_po_token=self.po_token_available,
                on_progress_callback=on_progress
            )
            
            print(f"📋 Título: {yt.title}")
            print(f"🎬 Canal: {yt.author}")
            print(f"⏱ Duración: {yt.length} segundos")
            
            # Filtrar streams por calidad
            if quality == '360p':
                stream = yt.streams.filter(res="360p", progressive=True).first()
            elif quality == '480p':
                stream = yt.streams.filter(res="480p", progressive=True).first()
            elif quality == '720p':
                stream = yt.streams.filter(res="720p", progressive=True).first()
            else:
                # Mejor calidad disponible
                stream = yt.streams.filter(progressive=True).order_by('resolution').desc().first()
            
            if not stream:
                # Si no hay streams progresivos, usar streams adaptativos
                video_stream = yt.streams.filter(adaptive=True, only_video=True).order_by('resolution').desc().first()
                audio_stream = yt.streams.filter(adaptive=True, only_audio=True).order_by('abr').desc().first()
                
                if video_stream and audio_stream:
                    print("📥 Descargando video y audio por separado...")
                    
                    # Descargar video
                    video_filename = f"youtube_{video_id}_video.{video_stream.subtype}"
                    video_path = os.path.join(DOWNLOAD_DIR, video_filename)
                    print(f"⬇️  Descargando video: {video_stream.resolution}")
                    video_stream.download(output_path=DOWNLOAD_DIR, filename=video_filename)
                    
                    # Descargar audio
                    audio_filename = f"youtube_{video_id}_audio.{audio_stream.subtype}"
                    audio_path = os.path.join(DOWNLOAD_DIR, audio_filename)
                    print(f"🎵 Descargando audio: {audio_stream.abr}")
                    audio_stream.download(output_path=DOWNLOAD_DIR, filename=audio_filename)
                    
                    # Combinar con FFmpeg (si está disponible)
                    final_filename = f"youtube_{video_id}_{quality}_{yt.title[:50]}.mp4"
                    final_path = os.path.join(DOWNLOAD_DIR, final_filename)
                    
                    try:
                        import subprocess
                        cmd = [
                            'ffmpeg', '-i', video_path, '-i', audio_path,
                            '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental',
                            final_path
                        ]
                        subprocess.run(cmd, check=True, capture_output=True)
                        
                        # Limpiar archivos temporales
                        os.remove(video_path)
                        os.remove(audio_path)
                        
                        print(f"✅ Video combinado: {final_path}")
                        filepath = final_path
                        
                    except Exception as e:
                        print(f"⚠️ No se pudo combinar con FFmpeg: {e}")
                        # Usar el video sin audio como fallback
                        filepath = video_path
                else:
                    raise ValueError("No se encontraron streams adecuados")
            else:
                # Stream progresivo (video + audio juntos)
                print(f"⬇️  Descargando stream: {stream.resolution}")
                filepath = stream.download(output_path=DOWNLOAD_DIR, filename_prefix=f"youtube_{video_id}_")
            
            # Verificar que el archivo existe
            if not os.path.exists(filepath):
                raise FileNotFoundError("No se encontró archivo descargado")
            
            # Renombrar para mejor organización
            new_filename = f"youtube_{video_id}_{quality}_{yt.title[:50]}.{stream.subtype if 'stream' in locals() else 'mp4'}"
            new_path = os.path.join(DOWNLOAD_DIR, new_filename)
            
            try:
                shutil.move(filepath, new_path)
                filepath = new_path
            except Exception as e:
                print(f"⚠️ No se pudo renombrar: {e}")
            
            return filepath, {
                'id': video_id,
                'title': yt.title[:100],
                'channel': yt.author,
                'duration': yt.length,
                'filesize': os.path.getsize(filepath),
                'platform': 'youtube',
                'content_type': 'video',
                'quality': quality,
                'format': 'mp4',
                'url': url,
            }
            
        except Exception as e:
            logger.error(f"❌ Error descargando video: {e}")
            raise
    
    def download_audio(self, url: str, format: str = 'm4a') -> Tuple[str, Dict[str, Any]]:
        """Descargar solo audio"""
        if not self.is_youtube_url(url):
            raise ValueError("URL de YouTube no válida")
        
        video_id = self.extract_video_id(url)
        logger.info(f"Descargando audio {video_id} en formato {format}")
        
        try:
            # Inicializar YouTube con PO Token si está disponible
            yt = YouTube(
                url, 
                use_po_token=self.po_token_available,
                on_progress_callback=on_progress
            )
            
            print(f"📋 Título: {yt.title}")
            print(f"🎬 Canal: {yt.author}")
            print(f"⏱ Duración: {yt.length} segundos")
            
            # Encontrar el mejor stream de audio
            if format == 'mp3':
                # Para MP3 necesitamos descargar y convertir
                audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                if not audio_stream:
                    raise ValueError("No se encontró stream de audio")
                
                print(f"🎵 Descargando audio: {audio_stream.abr}")
                filepath = audio_stream.download(
                    output_path=DOWNLOAD_DIR, 
                    filename_prefix=f"youtube_audio_{video_id}_"
                )
                
                # Convertir a MP3 si es necesario
                if not filepath.endswith('.mp3'):
                    try:
                        import subprocess
                        mp3_path = os.path.splitext(filepath)[0] + '.mp3'
                        cmd = [
                            'ffmpeg', '-i', filepath,
                            '-codec:a', 'libmp3lame', '-q:a', '2',
                            mp3_path
                        ]
                        subprocess.run(cmd, check=True, capture_output=True)
                        os.remove(filepath)  # Eliminar original
                        filepath = mp3_path
                    except Exception as e:
                        print(f"⚠️ No se pudo convertir a MP3: {e}")
                        # Renombrar extensión aunque no sea MP3 real
                        new_path = os.path.splitext(filepath)[0] + '.mp3'
                        try:
                            shutil.move(filepath, new_path)
                            filepath = new_path
                        except:
                            pass
            
            elif format == 'm4a':
                # Buscar stream de audio en formato m4a
                audio_stream = yt.streams.filter(
                    only_audio=True, 
                    mime_type="audio/mp4"
                ).order_by('abr').desc().first()
                
                if audio_stream:
                    print(f"🎵 Descargando audio M4A: {audio_stream.abr}")
                    filepath = audio_stream.download(
                        output_path=DOWNLOAD_DIR, 
                        filename_prefix=f"youtube_audio_{video_id}_"
                    )
                else:
                    # Fallback a cualquier stream de audio
                    audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                    if not audio_stream:
                        raise ValueError("No se encontró stream de audio")
                    
                    print(f"🎵 Descargando audio: {audio_stream.abr}")
                    filepath = audio_stream.download(
                        output_path=DOWNLOAD_DIR, 
                        filename_prefix=f"youtube_audio_{video_id}_"
                    )
            
            else:
                # Formato por defecto
                audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                if not audio_stream:
                    raise ValueError("No se encontró stream de audio")
                
                print(f"🎵 Descargando audio: {audio_stream.abr}")
                filepath = audio_stream.download(
                    output_path=DOWNLOAD_DIR, 
                    filename_prefix=f"youtube_audio_{video_id}_"
                )
            
            # Verificar que el archivo existe
            if not os.path.exists(filepath):
                raise FileNotFoundError("No se encontró archivo descargado")
            
            # Renombrar para mejor organización
            new_filename = f"youtube_audio_{video_id}_{yt.title[:50]}.{format}"
            new_path = os.path.join(DOWNLOAD_DIR, new_filename)
            
            try:
                shutil.move(filepath, new_path)
                filepath = new_path
            except Exception as e:
                print(f"⚠️ No se pudo renombrar: {e}")
            
            return filepath, {
                'id': video_id,
                'title': yt.title[:100],
                'channel': yt.author,
                'duration': yt.length,
                'filesize': os.path.getsize(filepath),
                'platform': 'youtube',
                'content_type': 'audio',
                'format': format,
                'url': url,
                'bitrate': audio_stream.abr if 'audio_stream' in locals() else 'unknown',
            }
            
        except Exception as e:
            logger.error(f"❌ Error descargando audio: {e}")
            raise
    
    def get_available_formats(self, url: str) -> Dict[str, Any]:
        """Obtener formatos disponibles"""
        try:
            yt = YouTube(url, use_po_token=self.po_token_available)
            
            video_streams = []
            audio_streams = []
            
            for stream in yt.streams:
                stream_info = {
                    'itag': stream.itag,
                    'mime_type': stream.mime_type,
                    'resolution': stream.resolution,
                    'fps': stream.fps,
                    'video_codec': stream.video_codec,
                    'audio_codec': stream.audio_codec,
                    'type': stream.type,
                    'subtype': stream.subtype,
                    'abr': stream.abr,
                    'is_progressive': stream.is_progressive,
                    'is_adaptive': stream.is_adaptive,
                    'includes_audio_track': stream.includes_audio_track,
                    'includes_video_track': stream.includes_video_track,
                }
                
                if stream.includes_video_track:
                    video_streams.append(stream_info)
                elif stream.includes_audio_track:
                    audio_streams.append(stream_info)
            
            return {
                'video': video_streams,
                'audio': audio_streams,
                'info': {
                    'title': yt.title,
                    'author': yt.author,
                    'duration': yt.length,
                    'views': yt.views,
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo formatos: {e}")
            return {'video': [], 'audio': [], 'info': {}}