import subprocess
import random
import sys
import os

from pathlib import Path
from config import BASE_PATH, DEFAULT_MEMORY, DEFAULT_VCPUS, DEBIAN_MIRROR, DEBIAN_VERSION, DEFAULT_GATEWAY, DEFAULT_DNS
def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

SCRIPT_DIR = os.path.join(get_base_path(), "scripts")

class VMManager:
    def __init__(self, sudo_helper, log_func):
        self.sudo = sudo_helper
        self.log = log_func
    # --------------- CREAR ---------------
    def crear(self, nombre, usuario, password, ip):
        ruta = f"{BASE_PATH}/{nombre}"
        disk = f"{ruta}/disk.img"
        temp = f"{ruta}/temp"
        loop_device = None

        try:
            self.log("[INFO] === FASE 1: PREPARACIÓN ===")
            self.sudo.ejecutar(f"mkdir -p {ruta}")

            self.log("[INFO] === FASE 2: CREANDO DISCO ===")
            self.sudo.ejecutar(f"qemu-img create -f raw {disk} 5G")

            self.log("[INFO] === FASE 3: PARTICIONANDO ===")
            self.sudo.ejecutar(f"parted {disk} mklabel msdos")
            self.sudo.ejecutar(f"parted {disk} mkpart primary ext4 1MiB 100%")
            self.sudo.ejecutar(f"parted {disk} set 1 boot on")

            self.log("[INFO] === FASE 4: LOOP + FORMATO ===")
            loop_device = self.sudo.ejecutar_silencioso(f"losetup -f --show {disk}")
            if not loop_device:
                raise Exception("No se pudo crear loop device")
            self.log(f"Loop device: {loop_device}")
            self.sudo.ejecutar(f"partprobe {loop_device}")
            self.sudo.ejecutar(f"mkfs.ext4 {loop_device}p1")

            self.log("[INFO] === FASE 5: MONTAJE ===")
            self.sudo.ejecutar(f"mkdir -p {temp}")
            self.sudo.ejecutar(f"mount {loop_device}p1 {temp}")

            self.log("[INFO] === FASE 6: INSTALANDO SISTEMA (esto tarda varios minutos) ===")
            self.sudo.ejecutar(
                f"debootstrap --include=linux-image-amd64,grub2-common,grub-pc,locales,locales-all,busybox,initramfs-tools,tree,openssh-server,vim "
                f"{DEBIAN_VERSION} {temp} {DEBIAN_MIRROR}"
            )

            self.log("[INFO] === FASE 7: CONFIGURANDO CHROOT ===")
            for mountpoint in ["dev", "proc", "sys", "dev/pts"]:
                self.sudo.ejecutar(f"mount --bind /{mountpoint} {temp}/{mountpoint}")

            self.sudo.ejecutar_chroot(temp, 'printf "es_MX.UTF-8 UTF-8\\n" > /etc/locale.gen')
            self.sudo.ejecutar_chroot(temp, 'locale-gen')
            self.sudo.ejecutar_chroot(temp, 'update-locale LANG=es_MX.UTF-8')

            # fstab
            self.sudo.ejecutar_chroot(temp,
                "printf 'proc /proc proc defaults 0 0\\n"
                "devpts /dev/pts devpts rw,noexec,nosuid,gid=5,mode=620 0 0\\n"
                "/dev/xvda1p1 / ext4 errors=remount-ro 0 1\\n' > /etc/fstab"
            )

            # network
            self.sudo.ejecutar_chroot(temp,
                                      f"printf 'auto lo\\niface lo inet loopback\\n\\n"
                                      f"auto enX0\\niface enX0 inet static\\n"
                                      f"    address {ip}/24\\n"
                                      f"    gateway {DEFAULT_GATEWAY}\\n"
                                      f"    dns-nameservers {DEFAULT_DNS}\\n' > /etc/network/interfaces"
                                      )

            # hostname y hosts
            self.sudo.ejecutar_chroot(temp, f"printf '{nombre}\\n' > /etc/hostname")
            self.sudo.ejecutar_chroot(temp,
                f"printf '127.0.0.1 localhost\\n{ip} {nombre}\\n"
                f"::1 ip6-localhost ip6-loopback\\n' > /etc/hosts"
            )

            self.log("[INFO] === FASE 8: USUARIOS Y GRUB ===")
            self.sudo.ejecutar_chroot(temp, f"echo 'root:{password}' | chpasswd")
            self.sudo.ejecutar_chroot(temp, f'useradd -m -s /bin/bash {usuario}')
            self.sudo.ejecutar_chroot(temp, f"echo '{usuario}:{password}' | chpasswd")
            self.sudo.ejecutar_chroot(temp, 'update-grub')
            self.sudo.ejecutar_chroot(temp,
                "printf '(hd0) /dev/xvda1p1\\n' > /boot/grub/device.map"
            )
            self.sudo.ejecutar_chroot(temp, 'apt clean')

            self.log("[INFO] === FASE 9: DESMONTANDO ===")
            for mountpoint in ["dev/pts", "dev", "proc", "sys"]:
                self.sudo.ejecutar(f"umount -lf {temp}/{mountpoint}")
            self.sudo.ejecutar(f"umount -lf {temp}")
            self.sudo.ejecutar(f"kpartx -dv {disk}")
            self.sudo.ejecutar(f"rm -rf {temp}")

            self.log("[INFO] === FASE 10: ARCHIVO DE CONFIGURACIÓN ===")
            mac = "00:16:3E:%02X:%02X:%02X" % (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )

            cfg_content = (
                f"bootloader = 'pygrub'\n"
                f"name = '{nombre}'\n"
                f"vcpus = {DEFAULT_VCPUS}\n"
                f"memory = {DEFAULT_MEMORY}\n"
                f"root = '/dev/xvda1p1 ro'\n"
                f"disk = [ 'file:{disk},xvda1,w' ]\n"
                f"vif = [ 'mac={mac},bridge=xenbr0' ]\n"
                f"on_poweroff = 'destroy'\n"
                f"on_reboot = 'restart'\n"
                f"on_crash = 'restart'\n"
            )

            tmp_cfg = f"/tmp/{nombre}.cfg"
            with open(tmp_cfg, "w") as f:
                f.write(cfg_content)
            self.sudo.ejecutar(f"mv {tmp_cfg} {ruta}/{nombre}.cfg")

            self.log("[INFO] === ENCENDIENDO VM ===")
            self.sudo.ejecutar(f"xl create {ruta}/{nombre}.cfg")
            self.log("[OK] VM creada correctamente")

        except Exception as e:
            self.log(f"[ERROR] ERROR: {str(e)}")
            self.limpiar(ruta, temp, loop_device)

    # --------------- ENCENDER ---------------
    def encender(self, nombre):
        ruta = f"{BASE_PATH}/{nombre}"
        cfg = f"{ruta}/{nombre}.cfg"

        try:
            if not os.path.exists(cfg):
                self.log(f"[ERROR] No existe la VM '{nombre}'")
                return

            # Verificar si ya está corriendo
            resultado = self.sudo.ejecutar_silencioso(f"xl list | grep {nombre}")
            if nombre in resultado:
                self.log(f"[INFO] La VM '{nombre}' ya está encendida")
                return

            self.log(f"[INFO] === ENCENDIENDO VM: {nombre} ===")
            self.sudo.ejecutar(f"xl create {cfg}")
            self.log(f"[OK] VM '{nombre}' encendida correctamente")

        except Exception as e:
            self.log(f"[ERROR] ERROR: {str(e)}")

    # --------------- APAGAR ---------------
    def apagar(self, nombre):
        try:
            self.log(f"[INFO] === APAGANDO VM: {nombre} ===")
            self.sudo.ejecutar(f"xl shutdown {nombre}")
            self.log(f"[OK] VM '{nombre}' apagada correctamente")
        except Exception as e:
            self.log(f"[ERROR] ERROR: {str(e)}")

    # --------------- LIMPIAR ---------------
    def limpiar(self, ruta, temp, loop_device):
        self.log("[INFO] Limpiando sistema...")

        for mountpoint in ["dev/pts", "dev", "proc", "sys", ""]:
            target = f"{temp}/{mountpoint}".rstrip("/")
            subprocess.run(
                f"echo '{self.sudo.password}' | sudo -S umount -lf {target} 2>/dev/null",
                shell=True
            )

        if loop_device:
            subprocess.run(
                f"echo '{self.sudo.password}' | sudo -S losetup -d {loop_device} 2>/dev/null",
                shell=True
            )

        if temp and os.path.exists(temp):
            self.sudo.ejecutar(f"find {temp} -mount -delete 2>/dev/null || true")
            self.sudo.ejecutar(f"rm -rf {temp}")

        if ruta and os.path.exists(ruta):
            self.sudo.ejecutar(f"rm -rf {ruta}")

        self.log("[OK] Limpieza completada")

    # --------------- ELIMINAR ---------------
    def eliminar(self, nombre):
        ruta = f"{BASE_PATH}/{nombre}"
        cfg = f"{ruta}/{nombre}.cfg"

        try:
            if not os.path.exists(ruta):
                self.log(f"[ERROR] No existe la VM '{nombre}'")
                return

            # Apagarla si está corriendo
            resultado = self.sudo.ejecutar_silencioso(f"xl list | grep {nombre}")
            if nombre in resultado:
                self.log(f"[INFO] Apagando VM '{nombre}'...")
                self.sudo.ejecutar(f"xl destroy {nombre}")

            # Borrar archivos
            self.log(f"[INFO] === ELIMINANDO VM: {nombre} ===")
            self.sudo.ejecutar(f"rm -rf {ruta}")
            self.log(f"[OK] VM  '{nombre}'  eliminada correctamente")

        except Exception as e:
            self.log(f"[ERROR] ERROR: {str(e)}")

    # --------------- CLONAR ---------------

    def clonar(self, origen, clon, ip):
        script = os.path.join(SCRIPT_DIR, "clonarVm.sh")
        # Path(__file__).parent / "scripts" / "clonarVm.sh"

        if not os.path.exists(script):
            self.log(f"[ERROR] No se encontró el script: {script}")
            return
        try:
            self.log("[INFO] === CLONANDO VM ===")
            self.sudo.ejecutar(f"bash {script} {origen} {clon} {ip}")
        except Exception as e:
            self.log(f"[ERROR] ERROR: {str(e)}")