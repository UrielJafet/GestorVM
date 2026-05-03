# GestorVM

Gestor de máquinas virtuales con interfaz gráfica para Xen, desarrollado en Python con CustomTkinter.

---

## Capturas de pantalla

<img width="308" height="192" alt="image" src="https://github.com/user-attachments/assets/9029b2af-8dc9-4692-901f-7e771dddaed0" /> 
<img width="608" height="582" alt="image" src="https://github.com/user-attachments/assets/2a0676d5-9b8c-447e-89e9-5ddc4f0a921d" />



---

## Requisitos del sistema

- Linux Debian o Ubuntu
- Xen instalado y configurado como hipervisor
- Las siguientes herramientas instaladas:

```bash
sudo apt install qemu-utils debootstrap kpartx parted xen-tools
```

---

## Instalación

### Opción 1 - Ejecutable (recomendada)

1. Descarga el archivo `GestorVM` desde la sección de Releases
2. Dale permisos de ejecución:

```bash
chmod +x GestorVM
```

3. Ejecuta la aplicación:

```bash
./GestorVM
```

### Opción 2 - Desde el código fuente

1. Clona el repositorio:

```bash
git clone https://github.com/UrielJafet/GestorVM.git
cd GestorVM
```

2. Instala las dependencias de Python:

```bash
pip install customtkinter CTkMessagebox Pillow
```

3. Ejecuta la aplicación:

```bash
python3 main.py
```

---

## Funcionalidades

- Crear máquinas virtuales con Debian Trixie
- Encender y apagar máquinas virtuales
- Clonar máquinas virtuales existentes
- Eliminar máquinas virtuales
- Interfaz gráfica con registro de actividad en tiempo real

---

## Estructura del proyecto

```
GestorVM/
├── main.py            # Punto de entrada
├── app.py             # Interfaz gráfica
├── vm_manager.py      # Lógica de máquinas virtuales
├── sudo_helper.py     # Manejo de comandos con sudo
├── config.py          # Configuración general
├── assets/
│   └── icons/         # Iconos de la interfaz
└── scripts/
    └── clonarVm.sh    # Script de clonación
```

---

## Configuración

Puedes modificar los valores por defecto en el archivo `config.py`:

```python
BASE_PATH = "/home/xen/domains"   # Ruta donde se guardan las VMs
DEFAULT_MEMORY = 1024             # Memoria RAM en MB
DEFAULT_VCPUS = 1                 # Número de CPUs virtuales
DEBIAN_MIRROR = "http://deb.debian.org/debian"
DEBIAN_VERSION = "trixie"
DEFAULT_GATEWAY = "192.168.84.1"
DEFAULT_DNS = "8.8.8.8"
```

---

## Autor

Robles Mora Uriel Jafet

---

## Licencia

Este proyecto fue desarrollado con fines educativos.
