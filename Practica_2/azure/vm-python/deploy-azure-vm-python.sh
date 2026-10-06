#!/bin/bash
# Script de referencia: creación y despliegue del Backend Python en Azure VM (Ubuntu 24.04 LTS) - PRA2-13
#
# Es la equivalencia por línea de comandos de lo realizado en el portal de Azure,
# en la consola de AWS y en la terminal para la VM taskflow-g15-python-azure.
# Documenta el procedimiento de forma reproducible. No contiene contraseñas,
# claves ni el valor de JWT_SECRET: esos valores se escriben a mano en la VM (paso 7).
#
# Requisitos: Azure CLI (az) y AWS CLI (aws) autenticados en las cuentas del
# equipo. Se ejecuta desde la máquina de desarrollo, en la raíz del repositorio:
#   SSH_PUBLIC_KEY=<ruta-a-la-llave.pub> SSH_KEY=<ruta-a-la-llave-privada> \
#     bash Practica_2/azure/vm-python/deploy-azure-vm-python.sh
#
# En el portal, Azure generó el par de claves SSH; aquí se usa una llave pública
# propia. La llave privada nunca se versiona.

set -e

SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY:?Definir SSH_PUBLIC_KEY con la ruta de la llave pública (.pub)}"
SSH_KEY="${SSH_KEY:?Definir SSH_KEY con la ruta de la llave privada}"

RESOURCE_GROUP=rg-taskflow-g15
VM_NAME=taskflow-g15-python-azure
LOCATION=westus2
IMAGE=Canonical:ubuntu-24_04-lts:server:latest
VM_SIZE=Standard_D2als_v7          # la cuota de la familia Bsv2 era 0 en la suscripción
VNET=vnet-westus2-1                # misma red que la VM de Node.js (taskflow-g15-node-azure)
SUBNET=snet-westus2-1
NSG="$VM_NAME-nsg"
PUBLIC_IP="$VM_NAME-ip"
ADMIN_USER=azureuser
PUERTO=3000

RDS_REGION=us-east-1
RDS_SG=sg-063f677d0d31377a4        # rds-taskflow-g15

echo "=== 1. Creando la VM (IP pública estándar y estática, autenticación por clave SSH) ==="
az vm create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_NAME" \
  --location "$LOCATION" \
  --image "$IMAGE" \
  --size "$VM_SIZE" \
  --security-type Standard \
  --vnet-name "$VNET" \
  --subnet "$SUBNET" \
  --public-ip-address "$PUBLIC_IP" \
  --public-ip-sku Standard \
  --public-ip-address-allocation static \
  --nsg "$NSG" \
  --nsg-rule SSH \
  --authentication-type ssh \
  --admin-username "$ADMIN_USER" \
  --ssh-key-values "$SSH_PUBLIC_KEY"

echo "=== 2. Regla del NSG para el puerto 3000 (Allow-3000-Python) ==="
az network nsg rule create \
  --resource-group "$RESOURCE_GROUP" \
  --nsg-name "$NSG" \
  --name Allow-3000-Python \
  --priority 310 \
  --direction Inbound \
  --access Allow \
  --protocol Tcp \
  --destination-port-ranges "$PUERTO"

echo "=== 3. Obteniendo la IP pública de la VM ==="
VM_IP=$(az vm show --show-details --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" \
  --query publicIps --output tsv)
echo "IP pública: $VM_IP"

echo "=== 4. Regla de entrada en el security group del RDS: TCP 5432 solo desde la IP de la VM ==="
aws ec2 authorize-security-group-ingress \
  --region "$RDS_REGION" \
  --group-id "$RDS_SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,IpRanges=[{CidrIp=$VM_IP/32,Description=taskflow-python-azure}]"

DESTINO="$ADMIN_USER@$VM_IP"

echo "=== 5. Empaquetando el backend con git archive y copiándolo a la VM ==="
git archive --format=tar.gz --output=api-python.tgz HEAD:Practica_2/api-python
scp -i "$SSH_KEY" api-python.tgz "$DESTINO:/tmp/api-python.tgz"
scp -i "$SSH_KEY" Practica_2/api-python/deploy/instalar_ec2.sh "$DESTINO:/tmp/instalar_ec2.sh"

echo "=== 6. Ejecutando el mismo instalador del backend (1ª vez: crea /etc/taskflow/python.env y NO arranca) ==="
ssh -i "$SSH_KEY" "$DESTINO" "sudo bash /tmp/instalar_ec2.sh"

echo "=== 7. Completar a mano el archivo de entorno ==="
# Reemplazar cada valor REEMPLAZAR_* (DB_PASSWORD, JWT_SECRET, CORS_ORIGINS).
# Los valores son los mismos que en la EC2 y se reciben por mensaje privado.
ssh -t -i "$SSH_KEY" "$DESTINO" "sudoedit /etc/taskflow/python.env"

echo "=== 8. Comprobando permisos del archivo de entorno y alcance del RDS desde la VM ==="
ssh -i "$SSH_KEY" "$DESTINO" "sudo stat -c '%U:%G %a' /etc/taskflow/python.env; \
  timeout 5 bash -c '</dev/tcp/taskflow-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com/5432' && echo ABIERTO || echo CERRADO"

echo "=== 9. Volviendo a ejecutar el instalador: verifica, arranca taskflow-python y consulta /health ==="
ssh -i "$SSH_KEY" "$DESTINO" "sudo bash /tmp/instalar_ec2.sh"

echo "=== 10. Prueba de humo dentro de la VM y /health desde fuera ==="
ssh -i "$SSH_KEY" "$DESTINO" "python3 /opt/taskflow-python/scripts/smoke_test.py http://localhost:$PUERTO"
curl -s -i "http://$VM_IP:$PUERTO/health"
echo

rm -f api-python.tgz
echo "=== Despliegue en Azure VM finalizado ==="
