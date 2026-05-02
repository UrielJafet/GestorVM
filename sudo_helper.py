import subprocess


class SudoHelper:
    def __init__(self, password, log_func):
        self.password = password
        self.log = log_func

    def ejecutar(self, cmd):
        self.log(f"{cmd}")
        full_cmd = f"echo '{self.password}' | sudo -S env PATH=/usr/sbin:/usr/bin:/sbin:/bin {cmd}"
        process = subprocess.Popen(
            full_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in process.stdout:
            if line.strip():
                self.log("  " + line.strip())
        process.wait()
        if process.returncode != 0:
            raise Exception(f"Falló: {cmd}")

    def ejecutar_chroot(self, temp, cmd):
        self.ejecutar(
            f'chroot {temp} /usr/bin/env PATH=/usr/sbin:/usr/bin:/sbin:/bin /bin/bash -c "{cmd}"'
        )

    def ejecutar_silencioso(self, cmd):
        """Ejecuta un comando y retorna el stdout sin loguearlo."""
        full_cmd = f"echo '{self.password}' | sudo -S env PATH=/usr/sbin:/usr/bin:/sbin:/bin {cmd}"
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()

    def verificar_sudo(self):
        """Verifica que la contraseña es correcta. Retorna True o False."""
        try:
            subprocess.run(
                ["sudo", "-S", "-v"],
                input=self.password + "\n",
                text=True,
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False