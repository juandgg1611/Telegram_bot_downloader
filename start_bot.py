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
    
    
    token = os.getenv('TELEGRAM_TOKEN')  
    if not token:
        print("❌ ERROR: TELEGRAM_TOKEN no configurado")
        print("   Configúralo en Railway/Render como variable de entorno")
        sys.exit(1)
    
    print(f"✅ Token encontrado (primeros 10 chars): {token[:10]}...")
    
    # Si necesitas actualizar config.py con el token
    config_path = Path(__file__).parent / 'src' / 'config.py'
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            content = re.sub(r'BOT_TOKEN\s*=\s*["\'][^"\']*["\']', 
                           f'BOT_TOKEN = "{token}"', content)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ Token actualizado en config.py")
        except Exception as e:
            print(f"⚠️  No se pudo actualizar config.py: {e}")
    
    
    from src.bot import setup_application
    
    print("✅ Configuración completada")
    print(f"📁 Directorio: {Path(__file__).parent.absolute()}")
    print("=" * 50)
    print("🤖 Iniciando bot de Telegram...")
    
    try:
        
        application, bot = setup_application()
        
        # Manejo de señales para producción
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def signal_handler(signum, frame):
            print(f"\n📶 Señal {signum} recibida, cerrando bot...")
            loop.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Ejecutar
        print("🔄 Inicializando bot...")
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Error fatal en producción: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()