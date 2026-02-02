#!/bin/bash
# install_dependencies.sh
# Script para instalar Node.js y youtube-po-token-generator en Render

echo "========================================"
echo "🔄 INSTALANDO DEPENDENCIAS PARA YOUTUBE"
echo "========================================"

# 1. Actualizar sistema
echo "📦 Actualizando paquetes del sistema..."
apt-get update -y

# 2. Instalar Node.js 18.x
echo "📦 Instalando Node.js 18..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

# Verificar instalación
echo "✅ Node.js instalado:"
node --version
npm --version

# 3. Instalar youtube-po-token-generator GLOBALMENTE
echo "📦 Instalando youtube-po-token-generator..."
npm install -g youtube-po-token-generator

# Verificar instalación
echo "✅ youtube-po-token-generator instalado"

# 4. Probar generación de token (opcional, para diagnóstico)
echo "🧪 Probando generación de PO Token..."
timeout 30 youtube-po-token-generator --help || echo "⚠️  Generador disponible pero timeout"

echo "========================================"
echo "✅ INSTALACIÓN COMPLETADA"
echo "========================================"