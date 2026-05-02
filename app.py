import customtkinter as ctk
import threading
import os
import sys

from pathlib import Path
from CTkMessagebox import CTkMessagebox
from typing import Dict, Callable, Optional, Tuple
from PIL import Image
from sudo_helper import SudoHelper
from vm_manager import VMManager

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Gestor de Máquinas Virtuales")
        self.geometry("600x550")
        self.resizable(False, False)

        self.sudo_helper = None
        self.vm_manager = None

        # Configurar UI
        self.botones: Dict[str, ctk.CTkButton] = {}
        self._setup_ui()


        # Pedir sudo después de que la ventana esté lista
        self.after(500, self.pedir_sudo)

    def _cargar_icono(self, nombre, size=(20, 20)):
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))

        ruta = Path(base) / "assets" / "icon" / nombre

        if not ruta.exists():
            self.log(f"[WARN] Icono no encontrado: {nombre}")
            return None

        try:
            img = Image.open(ruta).convert("RGBA")
            img = img.resize(size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=size
            )
        except Exception as e:
            self.log(f"[WARN] Error cargando icono {nombre}: {e}")
            return None

    def _setup_ui(self):
        """Configurar elementos de la interfaz"""
        # Frame para botones con grid
        frame_botones = ctk.CTkFrame(self, fg_color="transparent")
        frame_botones.pack(pady=10)

        iconos = {
            "Crear VM": self._cargar_icono("add.png", size=(28, 28)),
            "Encender VM": self._cargar_icono("play.png", size=(28, 28)),
            "Apagar VM": self._cargar_icono("on-off-button.png", size=(28, 28)),
            "Clonar VM": self._cargar_icono("duplicate.png", size=(28, 28)),
            "Eliminar VM": self._cargar_icono("bin.png", size=(28, 28)),
            "Salir": self._cargar_icono("exit.png", size=(28, 28)),
        }

        buttons = [
            ("Crear VM", self.crear_vm, "#526D82", "#27374D" ),
            ("Encender VM", self.encender_vm, "#40534C", "#1A3636"),
            ("Apagar VM", self.apagar_vm, "#e17055", "#fab1a0"),
            ("Clonar VM", self.clonar_vm, "#6c5ce7", "#a29bfe"),
            ("Eliminar VM", self.eliminar_vm, "#d63031", "#ff7675"),
            ("Salir", self.quit_app, "#2d3436", "#636e72"),
        ]

        for i, (text, command, color, hover) in enumerate(buttons):
            btn = ctk.CTkButton(
                frame_botones,  # ← master es frame_botones, no self
                text=text,
                text_color="#f0f0f0",
                width=180,
                height=80,
                font=ctk.CTkFont(size=14, weight="bold"),
                fg_color=color,
                command=command,
                hover_color=hover,
                state="disabled",
                image=iconos.get(text),
                compound="top",
            )
            btn.grid(row=i // 3, column=i % 3, padx=8, pady=8)
            self.botones[text] = btn

        # Barra de progreso
        self.progress = ctk.CTkProgressBar(self, width=500)
        self.progress.pack(pady=5)
        self.progress.set(0)

        # Área de logs
        self.log_box = ctk.CTkTextbox(self, width=560, height=200)
        self.log_box.pack(pady=10, padx=20)
        self.log_box.tag_config("error", foreground="#e74c3c")
        self.log_box.tag_config("ok", foreground="#2ecc71")
        self.log_box.tag_config("info", foreground="#3498db")
        self.log_box.tag_config("warn", foreground="#f39c12")
    # --------------- LOG ---------------
    def log(self, texto: str):
        self.after(0, self._log_insert, texto)

    def _log_insert(self, texto: str):
        texto_lower = texto.lower()

        if texto.startswith("[ERROR]"):
            tag = "error"
        elif texto.startswith("[OK]"):
            tag = "ok"
        elif texto.startswith("[INFO]"):
            tag = "info"
        elif texto.startswith("[WARN]"):
            tag = "warn"
        else:
            tag = ""

        self.log_box.insert("end", texto + "\n", tag)
        self.log_box.see("end")

    # --------------- PASSWORD ---------------
    def pedir_password(self):
        resultado = {"valor": None}

        dialog = ctk.CTkToplevel(self)
        dialog.title("Permisos de administrador")
        dialog.geometry("300x160")
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text="Introduce tu contraseña sudo:").pack(pady=10)

        entry = ctk.CTkEntry(dialog, show="*", width=200)
        entry.pack(pady=5)
        entry.focus_set()

        def confirmar():
            resultado["valor"] = entry.get()
            dialog.destroy()

        ctk.CTkButton(dialog, text="Aceptar", command=confirmar).pack(pady=10)
        entry.bind("<Return>", lambda e: confirmar())

        dialog.wait_window()
        return resultado["valor"]

    def pedir_sudo(self):
        self.log("Solicitando privilegios de administrador...")
        password = self.pedir_password()

        if not password:
            self.log("Cancelado por el usuario")
            self.quit_app()
            return

        helper = SudoHelper(password, self.log)

        if not helper.verificar_sudo():
            self.log("Contraseña incorrecta")
            respuesta = CTkMessagebox(
                master=self,
                title="Error",
                message="Contraseña incorrecta",
                icon="cancel",
                option_1="Reintentar",
                option_2="Cancelar",
                justify="center"
            )
            if respuesta.get() == "Reintentar":
                self.after(300, self.pedir_sudo)  # reintento recursivo
            else:
                self.destroy()
            return

        self.sudo_helper = helper
        self.vm_manager = VMManager(self.sudo_helper, self.log)
        self.log("Privilegios de sudo obtenidos correctamente")

        # Habilitar botones ahora que tenemos sudo
        for btn in self.botones.values():
            btn.configure(state="normal")

    # --------------- ACCIONES ---------------
    def crear_vm(self):
        datos = self.pedir_datos_vm()

        if not datos["nombre"] or not datos["usuario"] or not datos["password"]:
            self.log(" Todos los campos son obligatorios")
            return

        self.botones["Crear VM"].configure(state="disabled")

        def run():
            self.vm_manager.crear(datos["nombre"], datos["usuario"], datos["password"], datos["ip"])
            self.after(200, lambda: self.botones["Crear VM"].configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def clonar_vm(self):
        datos = self.pedir_datos_clonar_vm()

        if not datos["origen"] or not datos["clon"] or not datos["ip"]:
            self.log(" Todos los campos son obligatorios")
            return

        self.botones["Clonar VM"].configure(state="disabled")

        def run():
            self.vm_manager.clonar(datos["origen"], datos["clon"], datos["ip"])
            self.after(200, lambda: self.botones["Clonar VM"].configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def encender_vm(self):
        nombre = ctk.CTkInputDialog(text="Nombre de la VM:", title="Encender VM").get_input()
        if not nombre:
            return

        def run():
            self.vm_manager.encender(nombre)

        threading.Thread(target=run, daemon=True).start()

    def apagar_vm(self):
        nombre = ctk.CTkInputDialog(text="Nombre de la VM:", title="Apagar VM").get_input()
        if not nombre:
            return

        def run():
            self.vm_manager.apagar(nombre)

        threading.Thread(target=run, daemon=True).start()

    def eliminar_vm(self):
        nombre = ctk.CTkInputDialog(text="Nombre de la VM:", title="Eliminar VM").get_input()
        if not nombre:
            return
        # Confirmar antes de borrar
        respuesta = CTkMessagebox(
            master=self,
            title="Confirmar",
            message=f"¿Eliminar permanentemente la VM '{nombre}'?",
            icon="warning",
            option_1="Sí",
            option_2="No"
        )
        if respuesta.get() != "Sí":
            return
        threading.Thread(target=lambda: self.vm_manager.eliminar(nombre), daemon=True).start()

    # --------------- SALIR ---------------
    def quit_app(self):
        respuesta = CTkMessagebox(
            master=self,
            title="Confirmar salida",
            message="¿Estás seguro que deseas salir?",
            icon="question",
            option_1="Sí",
            option_2="No",
            justify="center"
        )
        if respuesta.get() == "Sí":
            self.destroy()

    # --------------- DATOS ---------------
    def pedir_datos_vm(self):
        resultado = {"nombre": None, "usuario": None, "password": None}

        dialog = ctk.CTkToplevel(self)
        dialog.title("Crear VM")
        dialog.geometry("400x400")
        dialog.resizable(False, False)

        dialog.after(100, dialog.grab_set)

        ctk.CTkLabel(dialog, text="Nombre de la VM:").pack(pady=(15, 0))
        entry_nombre = ctk.CTkEntry(dialog, width=200)
        entry_nombre.pack(pady=5)
        entry_nombre.focus_set()

        ctk.CTkLabel(dialog, text="Usuario:").pack(pady=(10, 0))
        entry_usuario = ctk.CTkEntry(dialog, width=200)
        entry_usuario.pack(pady=5)

        ctk.CTkLabel(dialog, text="Contraseña:").pack(pady=(10, 0))
        entry_password = ctk.CTkEntry(dialog, show="*", width=200)
        entry_password.pack(pady=5)

        ctk.CTkLabel(dialog, text="Ip:").pack(pady=(10, 0))
        entry_ip = ctk.CTkEntry(dialog, width=200, placeholder_text="192.168.1.100")
        entry_ip.pack(pady=5)

        def confirmar():
            ip = entry_ip.get()
            import re
            if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                ctk.CTkLabel(dialog, text="IP inválida", text_color="red").pack()
                return

            resultado["nombre"] = entry_nombre.get()
            resultado["usuario"] = entry_usuario.get()
            resultado["password"] = entry_password.get()
            resultado["ip"] = entry_ip.get()
            dialog.destroy()

        ctk.CTkButton(dialog, text="Crear", command=confirmar).pack(pady=15)
        entry_password.bind("<Return>", lambda e: confirmar())

        dialog.wait_window()
        return resultado

    # --------------- DATOS CLONAR ---------------
    def pedir_datos_clonar_vm(self):
        resultado = {"origen": None, "clon": None, "ip": None}

        dialog = ctk.CTkToplevel(self)
        dialog.title("Clonar VM")
        dialog.geometry("400x400")
        dialog.resizable(False, False)

        dialog.after(100, dialog.grab_set)

        ctk.CTkLabel(dialog, text="Nombre de la VM origen:").pack(pady=(15, 0))
        entry_origen = ctk.CTkEntry(dialog, width=200)
        entry_origen.pack(pady=5)
        entry_origen.focus_set()

        ctk.CTkLabel(dialog, text="Nombre de la VM:").pack(pady=(10, 0))
        entry_clon = ctk.CTkEntry(dialog, width=200)
        entry_clon.pack(pady=5)

        ctk.CTkLabel(dialog, text="Ip:").pack(pady=(10, 0))
        entry_ip = ctk.CTkEntry(dialog, width=200, placeholder_text="192.168.1.100")
        entry_ip.pack(pady=5)

        def confirmar():
            resultado["origen"] = entry_origen.get()
            resultado["clon"] = entry_clon.get()
            resultado["ip"] = entry_ip.get()
            dialog.destroy()

        ctk.CTkButton(dialog, text="Crear", command=confirmar).pack(pady=15)
        entry_ip.bind("<Return>", lambda e: confirmar())

        dialog.wait_window()
        return resultado