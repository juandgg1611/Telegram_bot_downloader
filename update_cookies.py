#!/usr/bin/env python3
"""
Script para actualizar cookies de YouTube en Render
EJECUTAR LOCALMENTE y subir el archivo actualizado
"""

import os
import sys

def main():
    print("=" * 60)
    print("ACTUALIZADOR DE COOKIES PARA YOUTUBE EN RENDER")
    print("=" * 60)
    print()
    print("INSTRUCCIONES PARA OBTENER COOKIES VÁLIDAS:")
    print("1. Abre Chrome/Firefox en MODO INCOGNITO")
    print("2. Ve a: https://www.youtube.com/robots.txt")
    print("3. Inicia sesión con tu cuenta de Google")
    print("4. Usa una extensión para exportar cookies (Get cookies.txt LOCALLY)")
    print("5. Guarda el archivo como 'cookies.txt'")
    print("6. Sube este archivo a tu proyecto en Render")
    print()
    
    if os.path.exists('cookies.txt'):
        print("📁 Archivo cookies.txt actual:")
        print("-" * 40)
        try:
            with open('cookies.txt', 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[:10]):  # Mostrar primeras 10 líneas
                    print(f"{i+1}: {line.strip()}")
                if len(lines) > 10:
                    print(f"... y {len(lines)-10} líneas más")
        except Exception as e:
            print(f"❌ Error leyendo archivo: {e}")
    else:
        print("❌ No existe cookies.txt en el directorio actual")
    
    print()
    print("⚠️  IMPORTANTE: Las cookies deben incluir:")
    print("   - VISITOR_INFO1_LIVE")
    print("   - __Secure-1PSID")
    print("   - __Secure-3PSID")
    print("   - __Secure-3PAPISID")
    print()
    print("✅ Comando para subir a Render:")
    print("   git add cookies.txt")
    print("   git commit -m 'update: fresh youtube cookies'")
    print("   git push origin main")
    print("=" * 60)

if __name__ == "__main__":
    main()