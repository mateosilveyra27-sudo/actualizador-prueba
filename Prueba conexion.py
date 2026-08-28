import tkinter as tk
from tkinter import messagebox
import urllib.request
import urllib.error

VERSION_ACTUAL = "1.2"

URL_VERSION = "https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/version.txt"


def parse_version(v_str):
    return tuple(map(int, v_str.strip().split(".")))


def mostrar_hola():
    mensaje.config(text="Hola")


def comprobar_actualizacion():
    try:
        req = urllib.request.Request(
            URL_VERSION,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Cache-Control": "no-cache"
            }
        )

        with urllib.request.urlopen(req) as respuesta:
            ultima_version = respuesta.read().decode("utf-8").strip()

        print("================================")
        print("Versión actual:", VERSION_ACTUAL)
        print("Versión de Internet:", repr(ultima_version))
        print("================================")

        if parse_version(ultima_version) > parse_version(VERSION_ACTUAL):

            messagebox.showinfo(
                "Actualización disponible",
                f"Hay una nueva versión disponible.\n\n"
                f"Versión actual: {VERSION_ACTUAL}\n"
                f"Nueva versión: {ultima_version}"
            )

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
            f"No se pudo comprobar la actualización.\n\n{error}"
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
boton.place(
    relx=0.5,
    rely=0.35,
    anchor="center"
)
mensaje = tk.Label(
    ventana,
    text="",
    font=("Arial", 20)
)

mensaje.place(
    relx=0.5,
    rely=0.50,
    anchor="center"
)

boton_actualizar = tk.Button(
    ventana,
    text="Buscar actualizaciones",
    command=comprobar_actualizacion
)

boton_actualizar.place(
    relx=0.5,
    rely=0.75,
    anchor="center"
)

ventana.mainloop()
