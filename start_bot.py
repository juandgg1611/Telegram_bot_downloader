#!/usr/bin/env python3
"""
Script principal para Render
"""
import os
import sys
import signal
import asyncio
from pathlib import Path
from threading import Thread
from flask import Flask

# ========== CONFIGURACIÓN DE COOKIES (AL INICIO) ==========
print("=" * 50)
print("🤖 INICIANDO BOT DE TELEGRAM - CONFIGURACIÓN")
print("=" * 50)

# Añadir directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

# Configurar cookies de YouTube
try:
    from setup_cookies import setup_youtube_cookies
    cookies_ok = setup_youtube_cookies()
    
    if not cookies_ok:
        print("\n⚠️  CONTINUANDO SIN COOKIES ÓPTIMAS")
        print("   Algunos videos pueden fallar en la descarga")
    else:
        print("\n✅ COOKIES CONFIGURADAS CORRECTAMENTE")
        
except ImportError as e:
    print(f"❌ No se pudo importar setup_cookies: {e}")
    print("   Asegúrate de que setup_cookies.py esté en la raíz del proyecto")
except Exception as e:
    print(f"❌ Error inesperado configurando cookies: {e}")

print("=" * 50)
# ========== FIN CONFIGURACIÓN DE COOKIES ==========

# Resto de tu configuración...
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "🤖 Bot de Telegram funcionando con cookies de YouTube"

@web_app.route('/cookies-status')
def cookies_status():
    """Endpoint para verificar estado de cookies"""
    cookies_path = Path("cookies.txt")
    if cookies_path.exists():
        try:
            with open(cookies_path, 'r') as f:
                lines = f.readlines()
                cookie_count = len([l for l in lines if l.strip() and not l.startswith('#')])
            return {
                "status": "active",
                "cookies_file": True,
                "cookie_count": cookie_count,
                "file_size": cookies_path.stat().st_size
            }
        except:
            return {"status": "error", "cookies_file": True}
    else:
        return {"status": "no_cookies", "cookies_file": False}

def run_flask():
    port = int(os.getenv('PORT', 8080))
    print(f"🌐 Iniciando servidor Flask en puerto {port}...")
    web_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def main():
    """Función principal"""
    # Iniciar Flask en un thread separado
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Verificar token de Telegram
    token = os.getenv('TELEGRAM_TOKEN') 
    
    if not token:
        print("❌ ERROR: TELEGRAM_TOKEN no configurado")
        print("   Configúralo en Render como variable de entorno")
        sys.exit(1)
    
    print(f"✅ Token encontrado (primeros 10 chars): {token[:10]}...")
    
    # Importar y configurar el bot
    try:
        # Asegurar que podemos importar desde src
        sys.path.insert(0, str(Path(__file__).parent / 'src'))
        from bot import setup_application
        
        application, bot = setup_application()
        
        print("✅ Configuración completada")
        print("🤖 Iniciando bot de Telegram (polling)...")
        
        # Manejo de señales
        def signal_handler(signum, frame):
            print(f"\n📶 Señal {signum} recibida, cerrando bot...")
            if application.running:
                application.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Ejecutar bot
        application.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])
        
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()