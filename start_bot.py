#!/usr/bin/env python3
"""
Script principal para Railway/Render
"""
import os
import sys
import signal
import asyncio
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def main():
    """Función principal para entornos de producción"""
    print("🚀 Iniciando Bot en Producción...")
    print("=" * 50)
    
    # Verificar variables de entorno
    token = os.getenv('8315169253:AAEHkDCqPayRQJxM6_isxBVf-7L4PFnrzkE')
    if not token:
        print("❌ ERROR: TELEGRAM_TOKEN no configurado")
        print("   Configúralo en Railway/Render como variable de entorno")
        sys.exit(1)
    
    # Actualizar config.py con el token de entorno
    config_path = Path(__file__).parent / 'src' / 'config.py'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Reemplazar el token placeholder
        content = content.replace('"8315169253:AAEHkDCqPayRQJxM6_isxBVf-7L4PFnrzkE"', f'"{token}"')
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Token configurado desde variables de entorno")
    
    # Importar después de configurar
    from src.bot import setup_application
    
    print("✅ Configuración completada")
    print(f"📁 Directorio: {Path(__file__).parent.absolute()}")
    print("=" * 50)
    print("🤖 Iniciando bot de Telegram...")
    
    try:
        # Crear y ejecutar aplicación
        application, bot = setup_application()
        
        # Manejo de señales para producción
        loop = asyncio.get_event_loop()
        
        def signal_handler(signum, frame):
            print(f"\n📶 Señal {signum} recibida, cerrando bot...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Ejecutar
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.start())
        loop.run_until_complete(application.updater.start_polling())
        
        print("🟢 Bot funcionando correctamente en producción")
        print("💡 Presiona Ctrl+C en la consola de Railway para detener")
        
        # Mantener el bot corriendo
        loop.run_forever()
        
    except Exception as e:
        print(f"❌ Error fatal en producción: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()