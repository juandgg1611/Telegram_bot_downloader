#!/usr/bin/env python3
"""
setup_cookies.py
Configura automáticamente las cookies de YouTube desde variable de entorno
"""
import os
import sys
from pathlib import Path

def setup_youtube_cookies():
    """
    Configura cookies.txt desde variable de entorno YOUTUBE_COOKIES
    Retorna True si se configuraron correctamente, False en caso contrario
    """
    cookies_path = Path("cookies.txt")
    
    print("🍪 Iniciando configuración de cookies...")
    print("=" * 50)
    
    # Opción 1: Desde variable de entorno
    cookies_content = os.getenv('YOUTUBE_COOKIES')
    
    if cookies_content:
        print("📥 Configurando cookies desde variable de entorno...")
        try:
            # Escribir cookies en archivo
            with open(cookies_path, 'w', encoding='utf-8') as f:
                f.write(cookies_content)
            
            # Verificar que el archivo se creó correctamente
            if cookies_path.exists():
                # Contar líneas y cookies
                with open(cookies_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    cookie_lines = [l for l in lines if l.strip() and not l.startswith('#')]
                
                print(f"✅ Cookies guardadas en: {cookies_path.absolute()}")
                print(f"   • Total de líneas: {len(lines)}")
                print(f"   • Cookies activas: {len(cookie_lines)}")
                print(f"   • Tamaño: {cookies_path.stat().st_size} bytes")
                
                # Verificar cookies importantes
                check_important_cookies(cookies_path)
                return True
                
        except Exception as e:
            print(f"❌ Error al guardar cookies: {e}")
            return False
    
    # Opción 2: Archivo ya existe
    elif cookies_path.exists():
        print(f"✅ Archivo de cookies ya existe: {cookies_path}")
        print("   Usando cookies existentes...")
        check_important_cookies(cookies_path)
        return True
    
    # Opción 3: No hay cookies disponibles
    else:
        print("⚠️  ADVERTENCIA: No se encontraron cookies de YouTube")
        print("=" * 50)
        print("PARA SOLUCIONAR:")
        print("1. Exporta cookies de YouTube desde Brave (logueado)")
        print("2. En Render Dashboard, agrega variable:")
        print("   Key: YOUTUBE_COOKIES")
        print("   Value: (pega todo el contenido de cookies.txt)")
        print("=" * 50)
        return False

def check_important_cookies(cookies_path):
    """Verifica que las cookies importantes estén presentes"""
    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        important_cookies = [
            'VISITOR_INFO1_LIVE',
            'LOGIN_INFO',
            '__Secure-1PSID',
            '__Secure-3PSID',
            'PREF'
        ]
        
        print("🔍 Verificando cookies importantes:")
        found = []
        missing = []
        
        for cookie in important_cookies:
            if cookie in content:
                found.append(cookie)
            else:
                missing.append(cookie)
        
        if found:
            print(f"   ✅ Presentes: {', '.join(found)}")
        
        if missing:
            print(f"   ⚠️  Faltantes: {', '.join(missing)}")
            print("   Nota: Algunas cookies pueden tener nombres diferentes")
        
        # Verificar si hay sesión activa
        if 'LOGIN_INFO' in content:
            print("   👤 Sesión de YouTube: ACTIVA (usuario logueado)")
        else:
            print("   👤 Sesión de YouTube: NO detectada")
            
    except Exception as e:
        print(f"   ❌ Error al verificar cookies: {e}")

def test_cookies():
    """Prueba rápida de las cookies"""
    print("\n🧪 Probando configuración de cookies...")
    if setup_youtube_cookies():
        print("\n✅ Configuración de cookies COMPLETADA")
        return True
    else:
        print("\n❌ Configuración de cookies FALLÓ")
        return False

if __name__ == "__main__":
    # Ejecutar como script independiente
    success = test_cookies()
    sys.exit(0 if success else 1)