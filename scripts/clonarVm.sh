#!/bin/bash

# ─────────────────────────────────────────
# Uso: ./clonar_vm.sh <vm_base> <vm_nueva> <ip_nueva> [dns]
# Ejemplo: ./clonar_vm.sh pruebaxen clon1 192.168.84.100 8.8.8.8
# ─────────────────────────────────────────

BASE_VM_NAME="$1"
NEW_VM_NAME="$2"
NEW_VM_IP="$3"
NEW_VM_DNS="${4:-192.168.2.24}"

BASE_VM_DIR="/home/xen/domains/$BASE_VM_NAME"
BASE_IMG="$BASE_VM_DIR/disk.img"
NEW_VM_DIR="/home/xen/domains/$NEW_VM_NAME"
NEW_IMG="$NEW_VM_DIR/disk.img"
XEN_CFG="$NEW_VM_DIR/$NEW_VM_NAME.cfg"
MOUNT_DIR="/mnt/tmp_vm_$NEW_VM_NAME"

# ─────────────────────────────────────────
# Validaciones
# ─────────────────────────────────────────

if [ -z "$BASE_VM_NAME" ] || [ -z "$NEW_VM_NAME" ] || [ -z "$NEW_VM_IP" ]; then
    echo "Uso: $0 <vm_base> <vm_nueva> <ip_nueva> [dns]"
    echo "Ejemplo: $0 pruebaxen clon1 192.168.84.100 8.8.8.8"
    exit 1
fi

if [ ! -f "$BASE_IMG" ]; then
    echo "No existe el disco de la VM base: $BASE_VM_NAME"
    exit 1
fi

if [ -d "$NEW_VM_DIR" ]; then
    echo "Ya existe una VM llamada: $NEW_VM_NAME"
    exit 1
fi

if xl list 2>/dev/null | grep -q "^$BASE_VM_NAME "; then
    echo "La VM '$BASE_VM_NAME' está encendida. Apágala antes de clonar."
    exit 1
fi

# ─────────────────────────────────────────
# Detectar kernel e initrd dinámicamente
# ─────────────────────────────────────────

KERNEL=$(ls /boot/vmlinuz-* 2>/dev/null | tail -1)
RAMDISK=$(ls /boot/initrd.img-* 2>/dev/null | tail -1)

if [ -z "$KERNEL" ] || [ -z "$RAMDISK" ]; then
    echo "No se encontró kernel o initrd en /boot"
    exit 1
fi

echo "→ Kernel: $KERNEL"
echo "→ Ramdisk: $RAMDISK"

# ─────────────────────────────────────────
# Crear directorio y copiar disco
# ─────────────────────────────────────────

echo "→ Creando VM: $NEW_VM_NAME"
mkdir -p "$NEW_VM_DIR"

echo "→ Copiando disco (puede tardar varios minutos)..."
cp --sparse=always "$BASE_IMG" "$NEW_IMG"

if [ $? -ne 0 ]; then
    echo "Error al copiar el disco"
    rm -rf "$NEW_VM_DIR"
    exit 1
fi

# ─────────────────────────────────────────
# Montar disco con kpartx
# ─────────────────────────────────────────

echo "→ Montando disco..."
LOOP=$(losetup -f --show "$NEW_IMG")

if [ -z "$LOOP" ]; then
    echo "No se pudo crear loop device"
    rm -rf "$NEW_VM_DIR"
    exit 1
fi

partprobe "$LOOP"
sleep 1

mkdir -p "$MOUNT_DIR"
mount "${LOOP}p1" "$MOUNT_DIR"

if [ $? -ne 0 ]; then
    echo "Error al montar la partición"
    losetup -d "$LOOP"
    rm -rf "$NEW_VM_DIR"
    exit 1
fi

mount --bind /dev "$MOUNT_DIR/dev"
mount --bind /dev/pts "$MOUNT_DIR/dev/pts"
mount -t proc proc "$MOUNT_DIR/proc"
mount -t sysfs sys "$MOUNT_DIR/sys"

# ─────────────────────────────────────────
# Configurar VM dentro del chroot
# ─────────────────────────────────────────

echo "→ Configurando VM..."
chroot "$MOUNT_DIR" /usr/bin/env PATH=/usr/sbin:/usr/bin:/sbin:/bin /bin/bash <<CHROOT

# Hostname
echo "$NEW_VM_NAME" > /etc/hostname

# Hosts
cat > /etc/hosts <<EOL
127.0.0.1 localhost
127.0.1.1 $NEW_VM_NAME
::1 ip6-localhost ip6-loopback
EOL

# Red
cat > /etc/network/interfaces <<EOL
auto lo
iface lo inet loopback

auto enX0
iface enX0 inet static
    address $NEW_VM_IP
    netmask 255.255.255.0
    gateway 192.168.84.1
    dns-nameservers $NEW_VM_DNS
EOL

# DNS fijo
printf "nameserver $NEW_VM_DNS\n" > /etc/resolv.conf
chattr +i /etc/resolv.conf

# Regenerar SSH keys para que sean únicas
rm -f /etc/ssh/ssh_host_*
dpkg-reconfigure openssh-server 2>/dev/null || ssh-keygen -A

# Regenerar machine-id único
rm -f /etc/machine-id /var/lib/dbus/machine-id
systemd-machine-id-setup
cp /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null || true

CHROOT

# ─────────────────────────────────────────
# Desmontar
# ─────────────────────────────────────────

echo "→ Desmontando..."
umount -lf "$MOUNT_DIR/dev/pts" 2>/dev/null
umount -lf "$MOUNT_DIR/dev"     2>/dev/null
umount -lf "$MOUNT_DIR/proc"    2>/dev/null
umount -lf "$MOUNT_DIR/sys"     2>/dev/null
umount -lf "$MOUNT_DIR"         2>/dev/null
losetup -d "$LOOP"              2>/dev/null
rm -rf "$MOUNT_DIR"

# ─────────────────────────────────────────
# Generar MAC única y archivo de configuración
# ─────────────────────────────────────────

MAC=$(printf '00:16:3E:%02X:%02X:%02X' $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)))

echo "→ Creando configuración Xen..."
cat > "$XEN_CFG" <<EOF
bootloader = 'pygrub'
name = "$NEW_VM_NAME"
memory = 1024
vcpus = 1
root = '/dev/xvda1p1 ro'
disk = [ 'file:$NEW_IMG,xvda1,w' ]
vif = [ 'bridge=xenbr0,mac=$MAC' ]
on_poweroff = 'destroy'
on_reboot = 'restart'
on_crash = 'restart'
EOF

# ─────────────────────────────────────────
# Fin
# ─────────────────────────────────────────

echo ""
echo "   VM '$NEW_VM_NAME' clonada correctamente"
echo "   IP:  $NEW_VM_IP"
echo "   MAC: $MAC"
echo "   CFG: $XEN_CFG"
echo ""
echo "Para encenderla:"
echo "   sudo xl create $XEN_CFG"
