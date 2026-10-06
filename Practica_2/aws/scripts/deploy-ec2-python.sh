#!/bin/bash
# Script de referencia: despliegue del Backend Python en AWS EC2 (Ubuntu 24.04 LTS) - PRA2-12
#
# Es la equivalencia por línea de comandos de lo realizado en la consola de AWS y
# en la terminal para la instancia taskflow-g15-python. Documenta el
# procedimiento de forma reproducible. No contiene contraseñas, claves ni el
# valor de JWT_SECRET: esos valores se escriben a mano en el servidor (paso 4).
#
# Se ejecuta desde la máquina de desarrollo, en la raíz del repositorio:
#   EC2_IP=<ip-publica-ec2> SSH_KEY=<ruta-a-la-llave-privada> \
#     bash Practica_2/aws/scripts/deploy-ec2-python.sh
#
# Recursos ya creados en la consola (ver docs/pra2-15-vertical-python-azure.md):
#   Instancia      taskflow-g15-python (t3.micro, Ubuntu Server 24.04 LTS, us-east-1)
#   Security group taskflow-g15-ec2-python: TCP 3000 desde 0.0.0.0/0, SSH 22 solo desde la IP del desarrollador
#   RDS            regla TCP 5432 en rds-taskflow-g15 con origen taskflow-g15-ec2-python

set -e

EC2_IP="${EC2_IP:?Definir EC2_IP con la IP pública de la EC2}"
SSH_KEY="${SSH_KEY:?Definir SSH_KEY con la ruta de la llave privada (.pem)}"
EC2_USER="${EC2_USER:-ubuntu}"
PUERTO=3000
PAQUETE=api-python.tgz
DESTINO="$EC2_USER@$EC2_IP"

echo "=== 1. Empaquetando el backend con git archive (solo archivos versionados) ==="
# HEAD:<ruta> deja el contenido de api-python en la raíz del paquete; así nunca
# viajan .venv, .env ni archivos locales que no estén en git.
git archive --format=tar.gz --output="$PAQUETE" HEAD:Practica_2/api-python

echo "=== 2. Copiando el paquete y el instalador a la EC2 ==="
scp -i "$SSH_KEY" "$PAQUETE" "$DESTINO:/tmp/api-python.tgz"
scp -i "$SSH_KEY" Practica_2/api-python/deploy/instalar_ec2.sh "$DESTINO:/tmp/instalar_ec2.sh"

echo "=== 3. Ejecutando deploy/instalar_ec2.sh (1ª vez: crea /etc/taskflow/python.env y NO arranca) ==="
ssh -i "$SSH_KEY" "$DESTINO" "sudo bash /tmp/instalar_ec2.sh"

echo "=== 4. Completar a mano el archivo de entorno ==="
# sudoedit abre el archivo en el servidor (root:taskflow, 640). Reemplazar cada
# valor REEMPLAZAR_* (DB_PASSWORD, JWT_SECRET, CORS_ORIGINS). Los secretos se
# reciben por mensaje privado y nunca se pasan como argumento de un comando.
ssh -t -i "$SSH_KEY" "$DESTINO" "sudoedit /etc/taskflow/python.env"

echo "=== 5. Volviendo a ejecutar el instalador: verifica, arranca taskflow-python y consulta /health ==="
ssh -i "$SSH_KEY" "$DESTINO" "sudo bash /tmp/instalar_ec2.sh"

echo "=== 6. Verificando /health desde fuera de la instancia ==="
curl -s -i "http://$EC2_IP:$PUERTO/health"
echo

echo "=== 7. Prueba de humo completa contra el RDS real ==="
python Practica_2/api-python/scripts/smoke_test.py "http://$EC2_IP:$PUERTO"

rm -f "$PAQUETE"
echo "=== Despliegue en AWS EC2 completado ==="
