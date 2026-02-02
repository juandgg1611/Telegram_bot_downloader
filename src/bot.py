"""
Bot principal para descargar contenido de TikTok y YouTube
Con botones inline para selección de formato
"""
import os
import logging
import logging.config
import asyncio
from typing import Optional, Dict, Any, Set
from datetime import datetime
from .downloaders.instagram import InstagramDownloader, InstagramContentInfo
from telegram import Update, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from .downloaders.pinterest import PinterestDownloader, PinterestContentInfo

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    CallbackContext,
)

from .config import TELEGRAM_TOKEN, MAX_FILE_SIZE, MESSAGES, LOG_CONFIG
from .downloaders.tiktok import TikTokDownloader, TikTokContentInfo
from .downloaders.youtube import YouTubeDownloader
from .utils.helpers import validate_url, format_file_size, extract_url_from_text, format_duration

# Configurar logging
logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger(__name__)

class TikTokYouTubeBot:
    """Bot principal para descargar TikTok y YouTube, Instagram y Pinterest"""
    
    def __init__(self):
        self.tiktok_downloader = TikTokDownloader()
        self.youtube_downloader = YouTubeDownloader()
        self.instagram_downloader = InstagramDownloader()
        self.pinterest_downloader = PinterestDownloader()
        self.stats = {
            'start_time': datetime.now(),
            'downloads': {
                'tiktok': {'success': 0, 'failed': 0, 'total_size': 0},
                'youtube_video': {'success': 0, 'failed': 0, 'total_size': 0},
                'youtube_audio': {'success': 0, 'failed': 0, 'total_size': 0},
                'instagram': {'success': 0, 'failed': 0, 'total_size': 0},
                'pinterest': {'success': 0, 'failed': 0, 'total_size': 0},
            },
            'users': set(),
        }
        
        self.pending_downloads: Dict[str, Dict[str, Any]] = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar comando /start"""
        user = update.effective_user
        self.stats['users'].add(user.id)
        
        logger.info(f"Usuario {user.id} ({user.username}) inició el bot")
        
        welcome_text = """
🎬 **Bot Descargador de TikTok y YouTube**

📥 **Soportado:**
• TikTok videos/fotos (automático)
• YouTube videos MP4 (720p)
• YouTube audio M4A (sin conversión)
• Instagram reels/fotos (automático)
• Pinterest imágenes/videos (automático)

✨ **Cómo usar:**
1. Envía un link de TikTok, YouTube, Instagram o Pinterest
2. Para YouTube: Selecciona formato con los botones
3. ¡Listo! El bot te enviará el contenido

⚙️ **Comandos:**
/start - Iniciar bot
/help - Mostrar ayuda
/stats - Ver estadísticas

⚠️ **Nota:** Solo contenido público, máximo 50MB
"""
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar comando /help"""
        help_text = """
📖 **Guía de uso:**

🔗 **Para TikTok:**
Envía: `https://vm.tiktok.com/XXXXXX/`
O: `https://www.tiktok.com/@usuario/video/123456789`

El bot detectará automáticamente si es video o foto.

🔗 **Para YouTube:**
Envía: `https://youtu.be/XXXXXXXXXXX`
O: `https://www.youtube.com/watch?v=XXXXXXXXXXX`

Aparecerán botones para elegir:
• 🎥 **Video MP4** - Video completo en 720p
• 🎵 **Audio M4A** - Solo audio (mejor calidad)

⚠️ **Limitaciones:**
• Máximo 1000MB por archivo
• Solo contenido público
• Uso educativo/responsable

❓ **Problemas comunes:**
• TikTok: Algunos videos pueden fallar por restricciones
• YouTube: Videos muy largos pueden superar el límite
"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar comando /stats"""
        uptime = datetime.now() - self.stats['start_time']
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        stats_text = f"""
📊 **Estadísticas del Bot**

⏰ **Tiempo activo:** {days}d {hours}h {minutes}m
👥 **Usuarios únicos:** {len(self.stats['users'])}

📥 **TikTok:**
   • ✅ Exitosos: {self.stats['downloads']['tiktok']['success']}
   • ❌ Fallidos: {self.stats['downloads']['tiktok']['failed']}
   • 💾 Total descargado: {format_file_size(self.stats['downloads']['tiktok']['total_size'])}

🎥 **YouTube (Video):**
   • ✅ Exitosos: {self.stats['downloads']['youtube_video']['success']}
   • ❌ Fallidos: {self.stats['downloads']['youtube_video']['failed']}
   • 💾 Total descargado: {format_file_size(self.stats['downloads']['youtube_video']['total_size'])}

🎵 **YouTube (Audio):**
   • ✅ Exitosos: {self.stats['downloads']['youtube_audio']['success']}
   • ❌ Fallidos: {self.stats['downloads']['youtube_audio']['failed']}
   • 💾 Total descargado: {format_file_size(self.stats['downloads']['youtube_audio']['total_size'])}
   
📖 **Instagram:**  
   • ✅ Exitosos: {self.stats['downloads']['instagram']['success']}
   • ❌ Fallidos: {self.stats['downloads']['instagram']['failed']}
   • 💾 Total descargado: {format_file_size(self.stats['downloads']['instagram']['total_size'])}
   
📌 **Pinterest:**  
   • ✅ Exitosos: {self.stats['downloads']['pinterest']['success']}
   • ❌ Fallidos: {self.stats['downloads']['pinterest']['failed']}
   • 💾 Total descargado: {format_file_size(self.stats['downloads']['pinterest']['total_size'])}

🔧 **Estado:** 🟢 Operativo
"""
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar mensajes con URLs"""
        user = update.effective_user
        text = update.message.text.strip()
        
        logger.info(f"Mensaje de {user.id} ({user.username}): {text[:50]}...")
        
        # Extraer URL del mensaje
        url = extract_url_from_text(text)
        if not url:
            await update.message.reply_text("Por favor envía un enlace de TikTok o YouTube.")
            return
        
        # Validar URL
        is_valid, platform = validate_url(url)
        
        if not is_valid:
            if platform == "unsupported":
                await update.message.reply_text(
                    "❌ Plataforma no soportada. Solo acepto:\n"
                    "• TikTok (tiktok.com)\n"
                    "• YouTube (youtube.com, youtu.be)\n"
                    "• Instagram (instagram.com, instagr.am)\n"
                    "• Pinterest (pinterest.com, pin.it)"
                )
            else:
                await update.message.reply_text(MESSAGES['invalid_url'])
            return
        
        # Manejar según plataforma
        if platform == "tiktok":
            await self._handle_tiktok_url(url, update, context)
        elif platform == "youtube":
            await self._handle_youtube_url(url, update, context)
        elif platform == "instagram":  
            await self._handle_instagram_url(url, update, context)
        elif platform == "pinterest":  
            await self._handle_pinterest_url(url, update, context)
            
    async def _handle_instagram_url(self, url: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar URL de Instagram (descarga directa)"""
        # Enviar mensaje de procesamiento
        status_msg = await update.message.reply_text("⏳ Procesando Instagram...")
        
        try:
            result = await self._process_instagram(url, update, status_msg)
            
            if result:
                self.stats['downloads']['instagram']['success'] += 1
            else:
                self.stats['downloads']['instagram']['failed'] += 1
                
        except Exception as e:
            logger.error(f"Error procesando Instagram: {e}")
            await status_msg.edit_text(f"❌ Error Instagram: {str(e)[:200]}")
            self.stats['downloads']['instagram']['failed'] += 1

    async def _process_instagram(self, url: str, update: Update, status_msg) -> bool:
        """Procesar descarga de Instagram"""
        try:
            # Obtener información primero
            content_info = self.instagram_downloader.get_content_info(url)
            
            # Mostrar preview
            emoji_map = {
                'reel': '🎬',
                'post': '📸', 
                'story': '📱',
                'video': '🎥',
                'photo': '🖼️',
                'igtv': '📺',
                'unknown': '📷'
            }
            
            emoji = emoji_map.get(content_info.content_type, '📷')
            content_type_text = content_info.content_type.capitalize()
            
            preview_text = f"""
    {emoji} **Instagram {content_type_text}**

    👤 **Usuario:** @{content_info.username}
    """
            
            if content_info.description:
                preview_text += f"📝 **Descripción:** {content_info.description[:100]}...\n"
            
            if content_info.like_count > 0:
                preview_text += f"❤️ **Likes:** {content_info.like_count:,}\n"
            
            if content_info.comment_count > 0:
                preview_text += f"💬 **Comentarios:** {content_info.comment_count:,}\n"
            
            if content_info.view_count > 0:
                preview_text += f"👁 **Vistas:** {content_info.view_count:,}\n"
            
            # CORRECCIÓN: Usar la nueva función segura
            if content_info.duration and content_info.duration > 0:
                duration_text = format_duration(content_info.duration)
                if duration_text != "00:00":
                    preview_text += f"⏱ **Duración:** {duration_text}\n"
            
            await status_msg.edit_text(f"{preview_text}\n\n⏳ Descargando...")
            
            # Descargar contenido
            filepath, result_info = await asyncio.to_thread(
                self.instagram_downloader.download, url
            )
            
            # Verificar tamaño
            if result_info['filesize'] > MAX_FILE_SIZE:
                self.instagram_downloader.cleanup(filepath)
                await status_msg.edit_text(MESSAGES['too_large'])
                return False
            
            # Construir caption
            caption = f"{emoji} Instagram {content_type_text}\n"
            caption += f"👤 @{result_info['username']}"
            
            if result_info.get('full_name'):
                caption += f" ({result_info['full_name']})"
            
            if content_info.description:
                caption += f"\n📝 {content_info.description[:100]}"
            
            if result_info.get('like_count', 0) > 0:
                caption += f"\n❤️ {result_info['like_count']:,}"
            
            # CORRECCIÓN: Verificar duración antes de formatear
            if result_info.get('duration', 0) > 0:
                duration_text = format_duration(result_info['duration'])
                if duration_text != "00:00":
                    caption += f"\n⏱ {duration_text}"
            
            # Enviar según el tipo de contenido
            if result_info['media_type'] == 'video':
                with open(filepath, 'rb') as video_file:
                    await update.message.reply_video(
                        video=InputFile(video_file, filename=f"instagram_{result_info['id']}.mp4"),
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=60,
                        write_timeout=60,
                    )
            else:
                with open(filepath, 'rb') as photo_file:
                    await update.message.reply_photo(
                        photo=InputFile(photo_file, filename=f"instagram_{result_info['id']}.jpg"),
                        caption=caption,
                        read_timeout=60,
                        write_timeout=60,
                    )
            
            # Actualizar estadísticas
            self.stats['downloads']['instagram']['total_size'] += result_info['filesize']
            
            # Limpiar
            self.instagram_downloader.cleanup(filepath)
            await status_msg.delete()
            
            logger.info(f"Instagram {content_info.content_type} {result_info['id']} enviado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error procesando Instagram: {e}", exc_info=True)
            error_msg = f"❌ Error Instagram: {str(e)[:200]}"
            
            # Mensajes específicos
            error_lower = str(e).lower()
            if "privado" in error_lower or "private" in error_lower:
                error_msg = "❌ Este contenido es privado y no se puede descargar."
            elif "bloque" in error_lower or "block" in error_lower:
                error_msg = "❌ Instagram está bloqueando las descargas. Espera unos minutos."
            elif "login" in error_lower or "iniciar sesión" in error_lower:
                error_msg = "❌ Este contenido requiere inicio de sesión."
            elif "formato" in error_lower and "duración" in error_lower:
                error_msg = "❌ Error procesando la información del video."
            
            await status_msg.edit_text(error_msg)
            return False
    async def _handle_tiktok_url(self, url: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar URL de TikTok (descarga directa)"""
        # Enviar mensaje de procesamiento
        status_msg = await update.message.reply_text("⏳ Procesando TikTok...")
        
        try:
            result = await self._process_tiktok(url, update, status_msg)
            
            if result:
                self.stats['downloads']['tiktok']['success'] += 1
            else:
                self.stats['downloads']['tiktok']['failed'] += 1
                
        except Exception as e:
            logger.error(f"Error procesando TikTok: {e}")
            await status_msg.edit_text(f"❌ Error TikTok: {str(e)[:200]}")
            self.stats['downloads']['tiktok']['failed'] += 1
    
    async def _handle_youtube_url(self, url: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar URL de YouTube (mostrar botones)"""
        try:
            # Obtener información del video
            info = self.youtube_downloader.get_video_info(url)
            
            # Formatear información para mostrar
            duration_text = format_duration(info['duration']) if info['duration'] > 0 else "Desconocida"
            
            # Crear botones inline
            keyboard = [
                [
                    InlineKeyboardButton("🎥 Video MP4 (720p)", callback_data=f"youtube_video:{url}"),
                    InlineKeyboardButton("🎵 Audio M4A", callback_data=f"youtube_audio:{url}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Mensaje con botones
            message_text = f"""
🎬 **{info['title'][:80]}...**

👤 **Canal:** {info['channel']}
⏱ **Duración:** {duration_text}
👁 **Vistas:** {info['view_count']:,}

📥 **Selecciona el formato:**
"""
            
            await update.message.reply_text(
                message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo info de YouTube: {e}")
            await update.message.reply_text(f"❌ Error obteniendo información: {str(e)[:200]}")
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar clics en botones inline"""
        query = update.callback_query
        await query.answer()  # Responder al callback para quitar el "loading"
        
        user = update.effective_user
        data = query.data
        
        logger.info(f"Callback de {user.id}: {data}")
        
        try:
            # Procesar según el tipo de callback
            if data.startswith("youtube_video:"):
                url = data.split(":", 1)[1]
                await self._process_youtube_video(url, query, context)
                
            elif data.startswith("youtube_audio:"):
                url = data.split(":", 1)[1]
                await self._process_youtube_audio(url, query, context)
                
            else:
                await query.edit_message_text("❌ Opción no reconocida")
                
        except Exception as e:
            logger.error(f"Error en callback: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)[:200]}")
    
    async def _process_youtube_video(self, url: str, query, context: ContextTypes.DEFAULT_TYPE):
        """Procesar descarga de video de YouTube"""
        try:
            # Actualizar mensaje
            await query.edit_message_text("⏳ Descargando video en 720p...")
            
            # Obtener información para el caption
            info = self.youtube_downloader.get_video_info(url)
            
            # Descargar video
            filepath, media_info = await asyncio.to_thread(
                self.youtube_downloader.download_video, url, '720p'
            )
            
            # Verificar tamaño máximo configurado (ej: 3GB)
            if media_info['filesize'] > MAX_FILE_SIZE:
                self.youtube_downloader.cleanup(filepath)
                await query.edit_message_text(MESSAGES['too_large'])
                return
            
            # Construir caption
            caption = f"🎥 YouTube Video\n📝 {media_info['title'][:100]}\n👤 {media_info['channel']}"
            if media_info.get('duration', 0) > 0:
                caption += f"\n⏱ {format_duration(media_info['duration'])}"
            
            # DECIDIR MÉTODO DE ENVÍO SEGÚN TAMAÑO
            filesize_mb = media_info['filesize'] / (1024 * 1024)
            
            # Telegram limits:
            # - send_video: máximo 50MB para streaming
            # - send_document: máximo 2GB (teórico), mejor mantener < 1.5GB
            
            if media_info['filesize'] <= 45 * 1024 * 1024:  # ≤ 45MB (dejar margen)
                # Método 1: Enviar como video con streaming
                await query.edit_message_text("⏳ Enviando video (streaming)...")
                with open(filepath, 'rb') as media_file:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=InputFile(media_file, filename=f"youtube_{media_info['id']}.mp4"),
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=120,  # Aumentar timeout para videos grandes
                        write_timeout=120,
                        connect_timeout=120,
                    )
                
            elif media_info['filesize'] <= 1.5 * 1024 * 1024 * 1024:  # ≤ 1.5GB
                # Método 2: Enviar como documento (hasta 2GB teóricos)
                warning_msg = f"⚠️ Video grande ({filesize_mb:.1f}MB). Enviando como documento..."
                await query.edit_message_text(warning_msg)
                
                with open(filepath, 'rb') as media_file:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=InputFile(media_file, filename=f"youtube_{media_info['id']}.mp4"),
                        caption=caption,
                        read_timeout=300,  # Timeout largo para archivos grandes
                        write_timeout=300,
                        connect_timeout=300,
                    )
                
            else:  # > 1.5GB
                # Método 3: Dividir o comprimir (opcional)
                self.youtube_downloader.cleanup(filepath)
                await query.edit_message_text(
                    f"❌ Video demasiado grande ({filesize_mb:.1f}MB).\n\n"
                    f"📊 Límites de Telegram:\n"
                    f"• Video con streaming: ≤ 50MB\n"
                    f"• Como documento: ≤ 1.5GB recomendado\n\n"
                    f"💡 Sugerencias:\n"
                    f"1. Descarga calidad más baja\n"
                    f"2. Usa /help para ver opciones"
                )
                return
            
            # Actualizar estadísticas
            self.stats['downloads']['youtube_video']['total_size'] += media_info['filesize']
            self.stats['downloads']['youtube_video']['success'] += 1
            
            # Limpiar archivo
            self.youtube_downloader.cleanup(filepath)
            
            # Eliminar mensaje de botones
            await query.delete_message()
            
            logger.info(f"YouTube video {media_info['id']} enviado exitosamente ({filesize_mb:.1f}MB)")
            
        except Exception as e:
            logger.error(f"Error procesando video YouTube: {e}", exc_info=True)
            error_msg = f"❌ Error descargando video: {str(e)[:200]}"
            
            # Mensajes específicos
            error_str = str(e).lower()
            if "request entity too large" in error_str or "413" in error_str:
                error_msg = f"❌ Video demasiado grande para Telegram.\n\n💡 Intenta:\n1. Calidad más baja\n2. Video más corto"
            elif "private video" in error_str:
                error_msg = "❌ Este video es privado y no se puede descargar."
            elif "not available" in error_str:
                error_msg = "❌ Este video no está disponible en tu país o fue eliminado."
            elif "sign in" in error_str:
                error_msg = "❌ Este video requiere inicio de sesión (edad restringida)."
            elif "timeout" in error_str:
                error_msg = "❌ Tiempo de espera agotado. El video es muy grande o la conexión es lenta."
            
            await query.edit_message_text(error_msg)
            
    async def _process_youtube_audio(self, url: str, query, context: ContextTypes.DEFAULT_TYPE):
        """Procesar descarga de audio de YouTube"""
        try:
            # Actualizar mensaje
            await query.edit_message_text("⏳ Descargando audio...")
            
            # Obtener información para el caption
            info = self.youtube_downloader.get_video_info(url)
            
            # Descargar audio
            filepath, media_info = await asyncio.to_thread(
                self.youtube_downloader.download_audio_with_retry, url, 'm4a'
            )
            
            # Verificar tamaño
            if media_info['filesize'] > MAX_FILE_SIZE:
                self.youtube_downloader.cleanup(filepath)
                await query.edit_message_text(MESSAGES['too_large'])
                return
            
            # Construir caption
            caption = f"🎵 YouTube Audio\n📝 {media_info['title'][:100]}\n👤 {media_info['channel']}"
            if media_info.get('duration', 0) > 0:
                caption += f"\n⏱ {format_duration(media_info['duration'])}"
            
            # Telegram audio limit: 50MB
            if media_info['filesize'] <= 50 * 1024 * 1024:
                # Enviar como audio
                with open(filepath, 'rb') as media_file:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=InputFile(media_file, filename=f"youtube_{media_info['id']}.m4a"),
                        caption=caption,
                        title=media_info['title'][:64],
                        performer=media_info['channel'][:64],
                        read_timeout=120,
                        write_timeout=120,
                    )
            else:
                # Si es muy grande, enviar como documento
                await query.edit_message_text(f"⚠️ Audio grande ({media_info['filesize']/1024/1024:.1f}MB). Enviando como documento...")
                
                with open(filepath, 'rb') as media_file:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=InputFile(media_file, filename=f"youtube_{media_info['id']}.m4a"),
                        caption=caption,
                        read_timeout=120,
                        write_timeout=120,
                    )
            
            # Actualizar estadísticas
            self.stats['downloads']['youtube_audio']['total_size'] += media_info['filesize']
            self.stats['downloads']['youtube_audio']['success'] += 1
            
            # Limpiar archivo
            self.youtube_downloader.cleanup(filepath)
            
            # Eliminar mensaje de botones
            await query.delete_message()
            
            logger.info(f"YouTube audio {media_info['id']} enviado exitosamente")
            
        except Exception as e:
            logger.error(f"Error procesando audio YouTube: {e}", exc_info=True)
            error_msg = f"❌ Error descargando audio: {str(e)[:200]}"
            
            # Mensajes específicos
            if "request entity too large" in str(e).lower():
                error_msg = "❌ Audio demasiado grande (>50MB). Intenta con un video más corto."
            elif "FFmpeg" in str(e):
                error_msg = "❌ Error: No se pudo procesar el audio. El formato puede no ser compatible."
            
            await query.edit_message_text(error_msg)
    
    async def _process_tiktok(self, url: str, update: Update, status_msg) -> bool:
        """Procesar descarga de TikTok"""
        try:
            # Obtener información primero
            content_info = self.tiktok_downloader.get_content_info(url)
            
            # Mostrar preview
            emoji = "📸" if content_info.content_type == 'photo' else "🎥"
            content_type_text = "Foto" if content_info.content_type == 'photo' else "Video"
            
            preview_text = f"""
{emoji} **TikTok {content_type_text}**
        
📝 **Título:** {content_info.title[:100]}
👤 **Usuario:** @{content_info.uploader}
"""
            
            if content_info.content_type == 'video' and content_info.duration > 0:
                preview_text += f"⏱ **Duración:** {format_duration(content_info.duration)}\n"
            
            if content_info.view_count > 0:
                preview_text += f"👁 **Vistas:** {content_info.view_count:,}\n"
            
            await status_msg.edit_text(f"{preview_text}\n\n⏳ Descargando...")
            
            # Descargar contenido
            filepath, result_info = await asyncio.to_thread(
                self.tiktok_downloader.download, url
            )
            
            # Verificar tamaño
            if result_info['filesize'] > MAX_FILE_SIZE:
                self.tiktok_downloader.cleanup(filepath)
                await status_msg.edit_text(MESSAGES['too_large'])
                return False
            
            # Construir caption
            caption = f"{emoji} TikTok {content_type_text}\n"
            caption += f"📝 {result_info['title'][:100]}\n"
            caption += f"👤 @{result_info['uploader']}"
            
            if content_info.content_type == 'video':
                caption += f"\n⏱ {format_duration(result_info.get('duration', 0))}"
            
            # Enviar según el tipo de contenido
            if content_info.content_type == 'photo':
                with open(filepath, 'rb') as photo_file:
                    await update.message.reply_photo(
                        photo=InputFile(photo_file, filename=f"tiktok_photo_{result_info['id']}.jpg"),
                        caption=caption,
                        read_timeout=60,
                        write_timeout=60,
                    )
            else:  # video
                with open(filepath, 'rb') as video_file:
                    await update.message.reply_video(
                        video=InputFile(video_file, filename=f"tiktok_{result_info['id']}.mp4"),
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=60,
                        write_timeout=60,
                    )
            
            # Actualizar estadísticas
            self.stats['downloads']['tiktok']['total_size'] += result_info['filesize']
            
            # Limpiar
            self.tiktok_downloader.cleanup(filepath)
            await status_msg.delete()
            
            logger.info(f"TikTok {content_info.content_type} {result_info['id']} enviado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error procesando TikTok: {e}", exc_info=True)
            error_msg = f"❌ Error TikTok: {str(e)[:200]}"
            if "No se pudo descargar" in str(e):
                error_msg += "\n\n⚠️ Posibles causas:\n• El contenido es privado\n• TikTok bloqueó la descarga\n• El enlace es inválido"
            await status_msg.edit_text(error_msg)
            return False
        
    async def _handle_pinterest_url(self, url: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar URL de Pinterest (descarga directa)"""
        # Enviar mensaje de procesamiento
        status_msg = await update.message.reply_text("⏳ Procesando Pinterest...")
        
        try:
            result = await self._process_pinterest(url, update, status_msg)
            
            if result:
                self.stats['downloads']['pinterest']['success'] += 1
            else:
                self.stats['downloads']['pinterest']['failed'] += 1
                
        except Exception as e:
            logger.error(f"Error procesando Pinterest: {e}")
            await status_msg.edit_text(f"❌ Error Pinterest: {str(e)[:200]}")
            self.stats['downloads']['pinterest']['failed'] += 1

    async def _process_pinterest(self, url: str, update: Update, status_msg) -> bool:
        """Procesar descarga de Pinterest"""
        try:
            # Obtener información primero
            content_info = self.pinterest_downloader.get_content_info(url)
            
            # Mostrar preview
            emoji = "🎬" if content_info.is_video else "📸"
            content_type_text = "Video" if content_info.is_video else "Imagen"
            
            preview_text = f"""
    {emoji} **Pinterest {content_type_text}**

    📝 **Título:** {content_info.title[:100]}
    👤 **Usuario:** {content_info.uploader or 'Desconocido'}
    """
            
            if content_info.description:
                preview_text += f"📄 **Descripción:** {content_info.description[:100]}...\n"
            
            if content_info.width and content_info.height:
                preview_text += f"📐 **Resolución:** {content_info.width}×{content_info.height}\n"
            
            await status_msg.edit_text(f"{preview_text}\n\n⏳ Descargando...")
            
            # Descargar contenido
            filepath, result_info = await asyncio.to_thread(
                self.pinterest_downloader.download, url
            )
            
            # Verificar tamaño
            if result_info['file_size'] > MAX_FILE_SIZE:
                self.pinterest_downloader.cleanup(filepath)
                await status_msg.edit_text(MESSAGES['too_large'])
                return False
            
            # Construir caption
            caption = f"{emoji} Pinterest {content_type_text}\n"
            caption += f"📝 {result_info['title'][:100]}\n"
            
            if result_info.get('uploader'):
                caption += f"👤 {result_info['uploader']}\n"
            
            if content_info.description:
                caption += f"📄 {content_info.description[:150]}"
            
            # Enviar según el tipo de contenido
            if result_info['is_video']:
                with open(filepath, 'rb') as video_file:
                    await update.message.reply_video(
                        video=InputFile(video_file, 
                                    filename=f"pinterest_{result_info['id']}.mp4"),
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=60,
                        write_timeout=60,
                    )
            else:  # imagen
                with open(filepath, 'rb') as photo_file:
                    await update.message.reply_photo(
                        photo=InputFile(photo_file, 
                                    filename=f"pinterest_{result_info['id']}.jpg"),
                        caption=caption,
                        read_timeout=60,
                        write_timeout=60,
                    )
            
            # Actualizar estadísticas
            self.stats['downloads']['pinterest']['total_size'] += result_info['file_size']
            
            # Limpiar
            self.pinterest_downloader.cleanup(filepath)
            await status_msg.delete()
            
            logger.info(f"Pinterest {content_type_text} {result_info['id']} enviado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error procesando Pinterest: {e}", exc_info=True)
            error_msg = f"❌ Error Pinterest: {str(e)[:200]}"
            
            # Mensajes específicos
            error_lower = str(e).lower()
            if "private" in error_lower or "privado" in error_lower:
                error_msg = "❌ Este Pin parece ser privado o no accesible."
            elif "api" in error_lower and "token" in error_lower:
                error_msg = "❌ Error de API. Si ves esto frecuentemente, considera obtener un token de Pinterest."
            elif "no se pudieron encontrar enlaces" in error_lower:
                error_msg = "❌ No se pudo extraer el contenido. El Pin puede no tener medios descargables."
            
            await status_msg.edit_text(error_msg)
            return False    
        
    async def error_handler(self, update: Update, context: CallbackContext):
        """Manejar errores"""
        logger.error(f"Error: {context.error}", exc_info=context.error)
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ Ocurrió un error interno. Por favor intenta de nuevo más tarde."
                )
        except:
            pass

def setup_application() -> Application:
    """Configurar y retornar la aplicación de Telegram"""
    # Crear aplicación
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Crear bot
    bot = TikTokYouTubeBot()
    
    # Añadir handlers de comandos
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("stats", bot.stats_command))
    
    # Handler para mensajes con URLs
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        bot.handle_message
    ))
    
    # Handler para botones inline
    application.add_handler(CallbackQueryHandler(bot.handle_callback_query))
    
    # Añadir handler de errores
    application.add_error_handler(bot.error_handler)
    
    return application, bot