#!/bin/bash
# Script de instalación y despliegue del Backend Node.js en Azure VM (Ubuntu 22.04 / 24.04 LTS)

set -e

echo "=== Actualizando paquetes en Azure VM ==="
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y curl git build-essential

echo "=== Instalando Node.js v20.x ==="
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "=== Instalando PM2 ==="
sudo npm install -g pm2

echo "=== Navegando al directorio de la API Node.js ==="
cd ~/SEMINARIO1_A_2S2026_G15/Practica_2/api-node || exit 1

echo "=== Instalando dependencias ==="
npm install

echo "=== Compilando proyecto ==="
npm run build

echo "=== Iniciando aplicación con PM2 ==="
pm2 stop taskflow-node-azure || true
pm2 delete taskflow-node-azure || true
pm2 start dist/main.js --name "taskflow-node-azure" --update-env

echo "=== Guardando configuración PM2 ==="
pm2 save

echo "=== Despliegue en Azure VM finalizado ==="
pm2 status
