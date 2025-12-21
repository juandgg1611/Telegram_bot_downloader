#!/usr/bin/env python3
"""
Script principal para iniciar el bot de TikTok y YouTube
"""

import sys
import os
import signal
import asyncio
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.bot import setup_application
from src.config import LOG_CONFIG
import logging
import logging.config

def setup_logging():
    """Configurar logging"""
    logging.config.dictConfig(LOG_CONFIG)
    
    # Log adicional a consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)

async def main():
    """Función principal asíncrona"""
    print("🎬 Iniciando TikTok & YouTube Downloader Bot...")
    print("=" * 50)
    
    # Verificar token
    from src.config import TELEGRAM_TOKEN
    if TELEGRAM_TOKEN == "TU_TOKEN_AQUÍ":
        print("❌ ERROR: Debes configurar el token en src/config.py")
        print("   Obtén un token de @BotFather en Telegram")
        sys.exit(1)
    
    # Configurar logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Configurar manejo de señales
    loop = asyncio.get_event_loop()
    
    def signal_handler(signum, frame):
        logger.info(f"Recibida señal {signum}, cerrando bot...")
        # Aquí podríamos añadir limpieza si fuera necesario
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Crear aplicación
        application, bot = setup_application()
        
        print("✅ Bot configurado correctamente")
        print(f"📂 Descargas en: {Path('downloads').absolute()}")
        print(f"📝 Logs en: {Path('logs').absolute()}")
        print("=" * 50)
        print("🤖 Bot iniciado. Presiona Ctrl+C para detener.")
        print("🟢 Listo para recibir mensajes...")
        
        # Iniciar polling
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Mantener el bot corriendo
        await asyncio.Event().wait()
        
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        print(f"❌ Error fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot detenido por el usuario")
        sys.exit(0)