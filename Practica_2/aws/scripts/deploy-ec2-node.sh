#!/bin/bash
# Script de instalación y despliegue del Backend Node.js en AWS EC2 (Ubuntu 24.04 LTS)

set -e

echo "=== Actualizando paquetes del sistema ==="
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y curl git build-essential

echo "=== Instalando Node.js v20.x ==="
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "=== Instalando PM2 globalmente ==="
sudo npm install -g pm2

echo "=== Clonando/Navegando al proyecto ==="
cd ~/SEMINARIO1_A_2S2026_G15/Practica_2/api-node || exit 1

echo "=== Instalando dependencias del proyecto ==="
npm install

echo "=== Compilando aplicación NestJS ==="
npm run build

echo "=== Iniciando aplicación con PM2 ==="
pm2 stop taskflow-node || true
pm2 delete taskflow-node || true
pm2 start dist/main.js --name "taskflow-node" --update-env

echo "=== Guardando estado de PM2 ==="
pm2 save
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u ubuntu --hp /home/ubuntu || true

echo "=== Despliegue completado con éxito ==="
pm2 status
