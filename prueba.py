import os
import sys
import time
import tkinter as tk
from tkinter import messagebox
import urllib.request
import urllib.error

VERSION_ACTUAL = "1.1"

URL_VERSION = "https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/version.txt"
URL_SCRIPT = "https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/prueba.py"


def parse_version(v_str):
    return tuple(map(int, v_str.strip().split(".")))


def mostrar_hola():
    mensaje.config(text="Hola")


def descargar_y_reemplazar():
    # Detecta la ruta exacta donde se está ejecutando este script
    ruta_script_actual = os.path.realpath(sys.argv[0])

    # Evita caché al descargar el código nuevo
    url_script_nocache = f"{URL_SCRIPT}?nocache={int(time.time())}"
    req = urllib.request.Request(
        url_script_nocache,
        headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
    )

    with urllib.request.urlopen(req) as respuesta:
        nuevo_codigo = respuesta.read()

    # Sobrescribe el archivo actual en la máquina del usuario
    with open(ruta_script_actual, "wb") as archivo:
        archivo.write(nuevo_codigo)

    messagebox.showinfo(
        "Actualizado",
        "El programa se actualizó correctamente. Se reiniciará ahora."
    )
    
    # Cierra la ventana actual y reinicia el proceso
    ventana.destroy()
    os.execv(sys.executable, [sys.executable] + sys.argv)


def comprobar_actualizacion():
    try:
        url_ver_nocache = f"{URL_VERSION}?nocache={int(time.time())}"
        req = urllib.request.Request(
            url_ver_nocache,
            headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
        )

        with urllib.request.urlopen(req) as respuesta:
            ultima_version = respuesta.read().decode("utf-8").strip()

        print("================================")
        print("Versión actual:", VERSION_ACTUAL)
        print("Versión de Internet:", repr(ultima_version))
        print("================================")

        if parse_version(ultima_version) > parse_version(VERSION_ACTUAL):
            respuesta_usuario = messagebox.askyesno(
                "Actualización disponible",
                f"Hay una nueva versión disponible: {ultima_version}\n"
                f"Tu versión actual es: {VERSION_ACTUAL}\n\n"
                f"¿Deseas descargar e instalar la actualización ahora?"
            )
            if respuesta_usuario:
                descargar_y_reemplazar()
        else:
            messagebox.showinfo(
                "Programa actualizado",
                "Ya tenés la última versión."
            )

    except urllib.error.HTTPError as e:
        messagebox.showerror(
            "Error HTTP",
            f"No se pudo acceder al archivo en GitHub ({e.code})."
        )
    except Exception as error:
        messagebox.showerror(
            "Error",
            f"No se pudo completar la actualización.\n\n{error}"
        )


ventana = tk.Tk()
ventana.title("Mi programa")
ventana.geometry("500x300")

boton = tk.Button(
    ventana,
    text="Presionar",
    font=("Arial", 14),
    command=mostrar_hola
)
boton.place(relx=0.5, rely=0.35, anchor="center")

mensaje = tk.Label(ventana, text="", font=("Arial", 20))
mensaje.place(relx=0.5, rely=0.50, anchor="center")

boton_actualizar = tk.Button(
    ventana,
    text="Buscar actualizaciones",
    command=comprobar_actualizacion
)
boton_actualizar.place(relx=0.5, rely=0.75, anchor="center")

ventana.mainloop()
