import sys
import os
import time
import urllib.request
import urllib.error
import base64
import json
import re
import calendar
import threading
from datetime import datetime
from supabase import create_client, Client
try:
    from supabase.client import ClientOptions
except ImportError:
    from supabase.lib.client_options import ClientOptions
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QStackedWidget, QFrame, QMessageBox,
                             QGraphicsDropShadowEffect, QScrollArea, QTabWidget, QTableWidget,
                             QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QInputDialog)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

if sys.platform == 'win32':
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

# === CONFIG NUBE ===
def _directorio_aplicacion():
    """Carpeta donde esta el .py o, si se compila, el .exe."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_SUPABASE_PATH = os.path.join(_directorio_aplicacion(), "config_supabase.json")
CONFIG_SUPABASE_ERROR = ""

def _cargar_config_supabase():
    global CONFIG_SUPABASE_ERROR
    try:
        with open(CONFIG_SUPABASE_PATH, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if not isinstance(datos, dict):
            raise ValueError("El contenido principal debe ser un objeto JSON.")
        return datos
    except FileNotFoundError:
        CONFIG_SUPABASE_ERROR = f"No se encontro {CONFIG_SUPABASE_PATH}"
    except json.JSONDecodeError as e:
        CONFIG_SUPABASE_ERROR = f"config_supabase.json tiene un formato JSON invalido: {e}"
    except Exception as e:
        CONFIG_SUPABASE_ERROR = f"No se pudo leer config_supabase.json: {e}"
    return {}


_CONFIG_SUPABASE = _cargar_config_supabase()
SUPABASE_URL = str(_CONFIG_SUPABASE.get("supabase_url") or "https://twqiuhxptkvnwjoewyxi.supabase.co").strip()
SUPABASE_PUBLIC_KEY = str(
    _CONFIG_SUPABASE.get("publishable_key")
    or _CONFIG_SUPABASE.get("anon_key")
    or ""
).strip()
APP_ACCESS_TOKEN = str(_CONFIG_SUPABASE.get("recepcion_access_token") or "").strip()
APP_ACCESS_HEADER = "x-la-herencia-token"

HERENCIA_MORADO = "#8b3dff"
HERENCIA_TEXTO_BOTON = "#ffffff"



# === ACTUALIZADOR REMOTO GITHUB ===
VERSION_ACTUAL = '1.0.1'
URL_VERSION = 'https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/recepcion_version.txt'
URL_UPDATE_PY = 'https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/Recepcion.py'
URL_UPDATE_EXE = 'https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/Recepcion.exe'


def _parse_version_actualizador(valor):
    """Convierte versiones como 1.2.3 o v1.2 en tuplas comparables."""
    numeros = re.findall(r"\d+", str(valor or ""))
    if not numeros:
        raise ValueError(f"Version invalida: {valor!r}")
    return tuple(int(n) for n in numeros)


def _request_github_sin_cache(url):
    separador = "&" if "?" in url else "?"
    url_nocache = f"{url}{separador}nocache={int(time.time())}"
    return urllib.request.Request(
        url_nocache,
        headers={
            "User-Agent": "LaHerenciaGym-Updater/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )


def _ruta_programa_actual():
    if getattr(sys, "frozen", False):
        return os.path.realpath(sys.executable)
    return os.path.realpath(__file__)


def _url_archivo_actualizacion():
    return URL_UPDATE_EXE if getattr(sys, "frozen", False) else URL_UPDATE_PY


def _crear_bat_reemplazo(ruta_actual, ruta_nueva):
    """Crea un .bat temporal que espera el cierre, reemplaza y vuelve a abrir el programa."""
    carpeta = os.path.dirname(ruta_actual)
    nombre_base = os.path.splitext(os.path.basename(ruta_actual))[0]
    ruta_bat = os.path.join(carpeta, f"actualizar_{nombre_base}.bat")

    if getattr(sys, "frozen", False):
        comando_reinicio = f'start "" "{ruta_actual}"'
    else:
        comando_reinicio = f'start "" "{sys.executable}" "{ruta_actual}"'

    lineas = [
        "@echo off",
        "setlocal",
        "chcp 65001 >nul",
        f'set "TARGET={ruta_actual}"',
        f'set "NEWFILE={ruta_nueva}"',
        "",
        "timeout /t 2 /nobreak >nul",
        "set /a INTENTOS=0",
        ":ESPERAR_CIERRE",
        "set /a INTENTOS+=1",
        'move /y "%NEWFILE%" "%TARGET%" >nul 2>&1',
        'if exist "%NEWFILE%" (',
        "    if %INTENTOS% GEQ 30 goto ERROR_ACTUALIZACION",
        "    timeout /t 1 /nobreak >nul",
        "    goto ESPERAR_CIERRE",
        ")",
        "",
        comando_reinicio,
        'start "" cmd /c "timeout /t 1 /nobreak >nul & del /f /q \\"%~f0\\""',
        "exit /b 0",
        "",
        ":ERROR_ACTUALIZACION",
        'msg * "No se pudo reemplazar el programa. Cerra La Herencia Gym y volve a intentar la actualizacion."',
        "exit /b 1",
    ]
    with open(ruta_bat, "w", encoding="utf-8", newline="\r\n") as archivo:
        archivo.write("\n".join(lineas))
    return ruta_bat


def _descargar_actualizacion(parent):
    if sys.platform != "win32":
        QMessageBox.warning(parent, "Actualizacion", "El actualizador por .bat esta preparado para Windows.")
        return

    ruta_actual = _ruta_programa_actual()
    url_archivo = _url_archivo_actualizacion()
    extension = os.path.splitext(ruta_actual)[1] or (".exe" if getattr(sys, "frozen", False) else ".py")
    ruta_nueva = ruta_actual + ".nueva" + extension

    try:
        req = _request_github_sin_cache(url_archivo)
        with urllib.request.urlopen(req, timeout=45) as respuesta:
            datos = respuesta.read()
        if not datos or len(datos) < 100:
            raise ValueError("El archivo descargado esta vacio o parece incompleto.")

        # Si se ejecuta como .py, valida sintaxis antes de reemplazar el archivo actual.
        if not getattr(sys, "frozen", False):
            try:
                texto = datos.decode("utf-8-sig")
                compile(texto, os.path.basename(ruta_actual), "exec")
            except Exception as e:
                raise ValueError(f"El .py descargado no paso la comprobacion de sintaxis: {e}") from e

        with open(ruta_nueva, "wb") as archivo:
            archivo.write(datos)

        ruta_bat = _crear_bat_reemplazo(ruta_actual, ruta_nueva)
        QMessageBox.information(
            parent,
            "Actualizacion descargada",
            "La nueva version ya fue descargada.\n\n"
            "El programa se cerrara, se reemplazara automaticamente y volvera a abrirse.",
        )
        os.startfile(ruta_bat)
        QApplication.instance().quit()
    except urllib.error.HTTPError as e:
        QMessageBox.critical(parent, "Error de actualizacion", f"GitHub respondio con error HTTP {e.code}.\n\n{url_archivo}")
    except urllib.error.URLError as e:
        QMessageBox.critical(parent, "Sin conexion", f"No se pudo conectar con GitHub.\n\n{e}")
    except Exception as e:
        try:
            if os.path.exists(ruta_nueva):
                os.remove(ruta_nueva)
        except Exception:
            pass
        QMessageBox.critical(parent, "Error de actualizacion", f"No se pudo instalar la actualizacion.\n\n{e}")


def comprobar_actualizacion(parent):
    """Comprueba recepcion_version.txt en GitHub y, con confirmacion, inicia el reemplazo por .bat."""
    try:
        req = _request_github_sin_cache(URL_VERSION)
        with urllib.request.urlopen(req, timeout=20) as respuesta:
            ultima_version = respuesta.read().decode("utf-8-sig").strip()

        if _parse_version_actualizador(ultima_version) > _parse_version_actualizador(VERSION_ACTUAL):
            aceptar = QMessageBox.question(
                parent,
                "Actualizacion disponible",
                f"Hay una nueva version disponible: {ultima_version}\n"
                f"Version instalada: {VERSION_ACTUAL}\n\n"
                "¿Deseas descargarla e instalarla ahora?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if aceptar == QMessageBox.StandardButton.Yes:
                _descargar_actualizacion(parent)
        else:
            QMessageBox.information(
                parent,
                "Programa actualizado",
                f"Ya tenes la ultima version instalada ({VERSION_ACTUAL}).",
            )
    except urllib.error.HTTPError as e:
        QMessageBox.critical(
            parent,
            "Error de actualizacion",
            f"No se pudo leer recepcion_version.txt en GitHub (HTTP {e.code}).\n\n"
            "Revisa que la carpeta y el archivo existan en el repositorio.",
        )
    except urllib.error.URLError as e:
        QMessageBox.critical(parent, "Sin conexion", f"No se pudo conectar con GitHub.\n\n{e}")
    except Exception as e:
        QMessageBox.critical(parent, "Error de actualizacion", f"No se pudo comprobar la actualizacion.\n\n{e}")
# === FIN ACTUALIZADOR REMOTO GITHUB ===


PLAN_SEMIPERSONALIZADO = "Semipersonalizado"
PLAN_PERSONALIZADO = "Personalizado"
PLAN_PASE_LIBRE = "Pase Libre"




def _es_service_role_key(clave):
    """Bloquea por seguridad cualquier clave service_role/secret en el cliente."""
    clave = str(clave or "").strip()
    if not clave or clave.startswith("sb_publishable_"):
        return False
    try:
        partes = clave.split(".")
        if len(partes) != 3:
            return False
        payload = partes[1] + "=" * (-len(partes[1]) % 4)
        datos = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8"))
        return str(datos.get("role", "")).lower() == "service_role"
    except Exception:
        return False


def crear_cliente_supabase_sin_login(parent):
    """Conecta sin pantalla de login usando publishable/anon key + token de instalación."""
    clave = SUPABASE_PUBLIC_KEY
    if CONFIG_SUPABASE_ERROR:
        QMessageBox.critical(
            parent,
            "Configuración de Supabase",
            f"{CONFIG_SUPABASE_ERROR}\n\n"
            "El archivo config_supabase.json debe estar en la misma carpeta que el programa."
        )
        return None
    if not clave or clave.upper().startswith("PEGA_AQUI"):
        QMessageBox.critical(
            parent,
            "Configuración de Supabase",
            "Falta completar la Publishable/anon key en config_supabase.json.\n\n"
            f"Archivo esperado:\n{CONFIG_SUPABASE_PATH}\n\n"
            "No uses una service_role/secret key."
        )
        return None
    if _es_service_role_key(clave):
        QMessageBox.critical(
            parent,
            "Clave insegura bloqueada",
            "El programa detectó una service_role key y se negó a utilizarla.\n\n"
            "Usá únicamente la Publishable/anon key de Supabase."
        )
        return None
    if not APP_ACCESS_TOKEN:
        QMessageBox.critical(
            parent,
            "Falta configurar el acceso del programa",
            "Este programa no usa usuario ni contraseña.\n\n"
            "Falta 'recepcion_access_token' dentro de config_supabase.json.\n"
            f"Archivo esperado:\n{CONFIG_SUPABASE_PATH}"
        )
        return None

    try:
        opciones = ClientOptions(headers={APP_ACCESS_HEADER: APP_ACCESS_TOKEN})
        return create_client(SUPABASE_URL, clave, options=opciones)
    except TypeError:
        # Compatibilidad con versiones de supabase-py que reciben options posicionalmente.
        try:
            opciones = ClientOptions(headers={APP_ACCESS_HEADER: APP_ACCESS_TOKEN})
            return create_client(SUPABASE_URL, clave, opciones)
        except Exception as e:
            QMessageBox.critical(parent, "Supabase", f"No se pudo crear el cliente.\n\n{e}")
            return None
    except Exception as e:
        QMessageBox.critical(parent, "Supabase", f"No se pudo crear el cliente.\n\n{e}")
        return None


class BotonHD(QPushButton):
    def __init__(self, text, color=HERENCIA_MORADO, parent=None):
        super().__init__(text, parent)
        self.color_base = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(120)
        self.setMinimumWidth(500)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(35)
        self.shadow.setOffset(0, 5)
        color_neon = QColor(self.color_base)
        color_neon.setAlpha(180)
        self.shadow.setColor(color_neon)
        self.setGraphicsEffect(self.shadow)

    def enterEvent(self, event):
        self.shadow.setBlurRadius(50)
        color_neon_fuerte = QColor(self.color_base)
        color_neon_fuerte.setAlpha(255)
        self.shadow.setColor(color_neon_fuerte)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.shadow.setBlurRadius(35)
        color_neon = QColor(self.color_base)
        color_neon.setAlpha(180)
        self.shadow.setColor(color_neon)
        super().leaveEvent(event)


class RecepcionGym(QWidget):
    actualizacion_detectada = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("La Herencia Gym - Recepcion")
        self.resize(1000, 750)

        self.c_boton = HERENCIA_MORADO
        self.c_texto = HERENCIA_TEXTO_BOTON

        self.supabase: Client = crear_cliente_supabase_sin_login(self)
        if self.supabase is None:
            sys.exit()
        try:
            self.descargar_apariencia()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar la configuración de nube: {e}")
            sys.exit()

        self.pantallas = QStackedWidget()
        self.pantallas.addWidget(self.crear_menu())
        self.pantallas.addWidget(self.crear_consulta())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pantallas)
        self.aplicar_diseno_visual()
        self._crear_boton_actualizacion()

    def _crear_boton_actualizacion(self):
        # Oculto por defecto; aparece únicamente si GitHub tiene una versión superior.
        self._version_actualizacion_disponible = ""
        self.btn_actualizacion_global = QPushButton("ACTUALIZACIÓN", self)
        self.btn_actualizacion_global.setFixedSize(150, 38)
        self.btn_actualizacion_global.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_actualizacion_global.setStyleSheet(
            f"QPushButton {{ background:#191919; color:white; border:2px solid {HERENCIA_MORADO}; "
            "border-radius:9px; font-size:12px; font-weight:900; padding:4px 10px; }} "
            "QPushButton:hover { background:white; color:black; }"
        )
        self.btn_actualizacion_global.clicked.connect(self._actualizar_desde_boton)
        self.actualizacion_detectada.connect(self._mostrar_boton_actualizacion)
        self.btn_actualizacion_global.hide()
        QTimer.singleShot(900, self._iniciar_comprobacion_actualizacion_silenciosa)

    def _iniciar_comprobacion_actualizacion_silenciosa(self):
        def tarea():
            try:
                req = _request_github_sin_cache(URL_VERSION)
                with urllib.request.urlopen(req, timeout=8) as respuesta:
                    ultima_version = respuesta.read().decode("utf-8-sig").strip()
                if _parse_version_actualizador(ultima_version) > _parse_version_actualizador(VERSION_ACTUAL):
                    self.actualizacion_detectada.emit(ultima_version)
            except Exception:
                pass

        threading.Thread(target=tarea, name="LaHerencia-UpdateCheck", daemon=True).start()

    def _mostrar_boton_actualizacion(self, ultima_version):
        self._version_actualizacion_disponible = str(ultima_version or "").strip()
        if not self._version_actualizacion_disponible:
            return
        self._reposicionar_boton_actualizacion()
        self.btn_actualizacion_global.show()
        self.btn_actualizacion_global.raise_()

    def _actualizar_desde_boton(self):
        ultima = self._version_actualizacion_disponible or "nueva versión"
        aceptar = QMessageBox.question(
            self,
            "Actualización disponible",
            f"Hay una nueva versión disponible: {ultima}\n"
            f"Versión instalada: {VERSION_ACTUAL}\n\n"
            "¿Deseas descargarla e instalarla ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if aceptar == QMessageBox.StandardButton.Yes:
            _descargar_actualizacion(self)

    def _reposicionar_boton_actualizacion(self):
        if hasattr(self, "btn_actualizacion_global"):
            margen = 14
            self.btn_actualizacion_global.move(
                max(margen, self.width() - self.btn_actualizacion_global.width() - margen),
                max(margen, self.height() - self.btn_actualizacion_global.height() - margen),
            )
            self.btn_actualizacion_global.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposicionar_boton_actualizacion()

    def descargar_apariencia(self):
        try:
            res = self.supabase.table('apariencia').select('*').eq('id', 1).execute()
            if res.data:
                self.c_boton = HERENCIA_MORADO
                self.c_texto = HERENCIA_TEXTO_BOTON
        except Exception:
            pass

    def aplicar_diseno_visual(self):
        estilo = f"""
            QWidget {{ background-color: #000000; color: white; font-family: 'Urbanist', 'Segoe UI'; }}

            QLineEdit {{
                background: #1a1a1a; border: 2px solid #444; border-radius: 15px;
                padding: 15px; font-size: 20px; color: white;
            }}
            QLineEdit:focus {{ border: 2px solid {self.c_boton}; background: #222; }}

            QPushButton.hd_btn {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.15), stop:0.1 {self.c_boton}, stop:0.9 {self.c_boton}, stop:1 rgba(0,0,0,0.4));
                color: {self.c_texto}; font-weight: 900; border-radius: 20px;
                border: 1px solid rgba(255,255,255,0.2); font-size: 26px; text-transform: uppercase; letter-spacing: 2px;
            }}
            QPushButton.hd_btn:hover {{ background: white; color: black; border: 2px solid {self.c_boton}; }}

            QFrame#Panel {{ background: rgba(20,20,20,0.8); border-radius: 25px; border: 1px solid rgba(255,255,255,0.05); }}

            QTabWidget::pane {{ border: 1px solid #333; border-radius: 10px; background: #111; }}
            QTabBar::tab {{
                background: #2a2a2a; color: #f0f0f0; padding: 10px 22px;
                margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px;
                font-weight: bold; font-size: 14px;
            }}
            QTabBar::tab:selected {{ background: {self.c_boton}; color: white; }}

            QTableWidget {{ background: #111; color: white; gridline-color: #333; border: 1px solid #333; font-size: 14px; }}
            QHeaderView::section {{ background: {self.c_boton}; color: white; font-weight: bold; padding: 10px; border: none; }}
        """
        self.setStyleSheet(estilo)

    def crear_menu(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titulo = QLabel("La Herencia Gym")
        titulo.setStyleSheet(f"font-size: 72px; font-weight: 900; color: {self.c_boton}; letter-spacing: 6px;")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subt = QLabel("RECEPCIÓN")
        subt.setStyleSheet("font-size: 22px; color: #aaa; letter-spacing: 4px; font-weight: 600;")
        subt.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn = BotonHD("CONSULTAR SOCIO", self.c_boton)
        btn.setProperty("class", "hd_btn")
        btn.clicked.connect(lambda: self.pantallas.setCurrentIndex(1))

        l.addWidget(titulo)
        l.addWidget(subt)
        l.addSpacing(60)
        l.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    def crear_consulta(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(60, 60, 60, 60)

        hl_top = QHBoxLayout()
        btn_v = QPushButton("⬅ VOLVER AL MENÚ")
        btn_v.setProperty("class", "hd_btn")
        btn_v.setFixedHeight(60)
        btn_v.clicked.connect(self.volver_al_menu)
        hl_top.addWidget(btn_v)
        hl_top.addStretch()
        l.addLayout(hl_top)

        f = QFrame()
        f.setObjectName("Panel")
        fl = QVBoxLayout(f)
        fl.setSpacing(30)
        fl.setContentsMargins(50, 50, 50, 50)

        hl = QHBoxLayout()
        self.in_dni = QLineEdit()
        self.in_dni.setPlaceholderText("Ingrese DNI del socio...")
        self.in_dni.returnPressed.connect(self.buscar_socio)
        btn_b = QPushButton("BUSCAR")
        btn_b.setProperty("class", "hd_btn")
        btn_b.setFixedHeight(60)
        btn_b.clicked.connect(self.buscar_socio)
        hl.addWidget(self.in_dni)
        hl.addWidget(btn_b)

        self.panel_resultado = QScrollArea()
        self.panel_resultado.setWidgetResizable(True)
        self.panel_resultado.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.contenedor_resultado = QWidget()
        self.layout_resultado = QVBoxLayout(self.contenedor_resultado)
        self.layout_resultado.setContentsMargins(0, 0, 0, 0)
        self.lbl_espera = QLabel("Esperando DNI...")
        self.lbl_espera.setStyleSheet("font-size: 22px; color: #888;")
        self.layout_resultado.addWidget(self.lbl_espera)
        self.layout_resultado.addStretch()
        self.panel_resultado.setWidget(self.contenedor_resultado)

        fl.addLayout(hl)
        fl.addWidget(self.panel_resultado, stretch=1)
        l.addWidget(f, stretch=1)
        return w

    def volver_al_menu(self):
        self.in_dni.clear()
        self._limpiar_resultado("Esperando DNI...")
        self.pantallas.setCurrentIndex(0)

    def _limpiar_resultado(self, mensaje=""):
        while self.layout_resultado.count():
            item = self.layout_resultado.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        lbl = QLabel(mensaje)
        lbl.setStyleSheet("font-size: 22px; color: #888;")
        self.layout_resultado.addWidget(lbl)
        self.layout_resultado.addStretch()

    def _texto_plan(self, socio):
        plan = str(socio.get('plan', '-') or '-')
        try:
            val = int(socio.get('dias', 0) or 0)
        except (TypeError, ValueError):
            val = 0
        if plan == PLAN_SEMIPERSONALIZADO:
            return f"{plan} — {val} días/semana"
        if plan == PLAN_PERSONALIZADO:
            return f"{plan} — {val} hora(s)/semana"
        if plan == PLAN_PASE_LIBRE:
            return plan
        return f"{plan} ({val})"

    def _calcular_edad(self, fecha_nacimiento):
        if not fecha_nacimiento:
            return None
        try:
            dt = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
            hoy = datetime.now().date()
            return hoy.year - dt.year - ((hoy.month, hoy.day) < (dt.month, dt.day))
        except (ValueError, TypeError):
            return None

    def _cargar_rutina(self, dni):
        try:
            res = self.supabase.table('rutinas_socios').select('rutina').eq('dni', str(dni)).execute()
            if res.data:
                rutina = res.data[0].get('rutina', {})
                return rutina if isinstance(rutina, dict) else {}
        except Exception:
            pass
        return {}

    def _guardar_rutina(self, dni, rutina):
        try:
            self.supabase.table('rutinas_socios').upsert({
                'dni': str(dni),
                'rutina': rutina,
                'actualizado_en': datetime.now().isoformat()
            }).execute()
            return True
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'No se pudo guardar la rutina.\n\n{e}')
            return False

    def _preparar_snapshot_sesion(self, rutina, dias_rutina):
        """Copia la rutina completa para que el historial del día no cambie en el futuro."""
        snapshot = {}
        rutina = rutina if isinstance(rutina, dict) else {}
        for dia_num in range(1, max(1, int(dias_rutina)) + 1):
            clave = f'Dia {dia_num}'
            ejercicios = rutina.get(clave, [])
            if not isinstance(ejercicios, list):
                ejercicios = []
            snapshot[clave] = []
            for ej in ejercicios:
                ej = ej if isinstance(ej, dict) else {}
                snapshot[clave].append({
                    'ejercicio': str(ej.get('ejercicio', '') or ''),
                    'series': str(ej.get('series', '') or ''),
                    'repeticiones': str(ej.get('repeticiones', '') or ''),
                    'elemento': str(ej.get('elemento', '') or ''),
                    'completado': bool(ej.get('completado', False)),
                    'completado_en': ej.get('completado_en') or None,
                })
        return snapshot

    def _cargar_sesion_hoy(self, dni):
        hoy = datetime.now().date().isoformat()
        try:
            res = (self.supabase.table('sesiones_entrenamiento')
                   .select('*')
                   .eq('dni', str(dni))
                   .eq('fecha', hoy)
                   .execute())
            return res.data[0] if res.data else None
        except Exception:
            return None

    def _crear_sesion_hoy(self, socio, asistencia_semana):
        dni = str(socio.get('dni', '') or '')
        hoy = datetime.now().date().isoformat()
        dias_r = self._dias_rutina(socio)
        rutina_base = self._cargar_rutina(dni)
        snapshot = self._preparar_snapshot_sesion(rutina_base, dias_r)
        try:
            dia_num = max(1, min(int(asistencia_semana or 1), max(1, dias_r)))
        except (TypeError, ValueError):
            dia_num = 1
        try:
            self.supabase.table('sesiones_entrenamiento').upsert({
                'dni': dni,
                'fecha': hoy,
                'dia_rutina': dia_num,
                'rutina': snapshot,
                'creado_en': datetime.now().isoformat(),
                'actualizado_en': datetime.now().isoformat(),
            }, on_conflict='dni,fecha').execute()
            return self._cargar_sesion_hoy(dni)
        except Exception as e:
            QMessageBox.critical(
                self,
                'Historial de rutina',
                'La asistencia se registró, pero no se pudo crear la sesión de entrenamiento.\n\n'
                'Ejecutá el SQL de sesiones_entrenamiento en Supabase.\n\n'
                f'Detalle: {e}'
            )
            return None

    def _guardar_sesion_hoy(self, dni, dia_num, rutina_snapshot, mostrar_error=True):
        hoy = datetime.now().date().isoformat()
        try:
            self.supabase.table('sesiones_entrenamiento').upsert({
                'dni': str(dni),
                'fecha': hoy,
                'dia_rutina': int(dia_num),
                'rutina': rutina_snapshot,
                'actualizado_en': datetime.now().isoformat(),
            }, on_conflict='dni,fecha').execute()
            return True
        except Exception as e:
            if mostrar_error:
                QMessageBox.critical(
                    self,
                    'Historial de rutina',
                    'No se pudo guardar el progreso de la rutina en Supabase.\n\n'
                    f'Detalle: {e}'
                )
            return False

    def _dias_rutina(self, socio):
        plan = str(socio.get('plan', '') or '')
        try:
            val = int(socio.get('dias', 3) or 3)
        except (TypeError, ValueError):
            val = 3
        if plan == PLAN_PASE_LIBRE:
            return 3
        if plan == PLAN_PERSONALIZADO:
            return max(1, min(val, 7))
        if plan == PLAN_SEMIPERSONALIZADO:
            return max(2, min(val, 6))
        return max(1, min(val, 6))

    def _rango_semana_actual(self):
        hoy = datetime.now().date()
        inicio = hoy.fromordinal(hoy.toordinal() - hoy.weekday())
        fin = hoy.fromordinal(inicio.toordinal() + 6)
        return inicio.isoformat(), fin.isoformat()

    def _total_asistencias_plan(self, socio):
        plan = str(socio.get('plan', '') or '')
        try:
            val = int(socio.get('dias', 0) or 0)
        except (TypeError, ValueError):
            val = 0
        if plan == PLAN_PASE_LIBRE:
            return self._dias_rutina(socio)
        return max(1, val or self._dias_rutina(socio))

    def _estado_asistencia(self, socio):
        hoy = datetime.now().date().isoformat()
        inicio, fin = self._rango_semana_actual()
        try:
            res = (self.supabase.table('asistencias')
                   .select('fecha')
                   .eq('dni', str(socio.get('dni', '')))
                   .gte('fecha', inicio)
                   .lte('fecha', fin)
                   .execute())
            fechas = {str(r.get('fecha', ''))[:10] for r in (res.data or []) if r.get('fecha')}
            return len(fechas), hoy in fechas
        except Exception:
            return 0, False

    def _rango_mes_actual(self):
        hoy = datetime.now().date()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        return hoy.replace(day=1).isoformat(), hoy.replace(day=ultimo_dia).isoformat()

    def _nombre_mes_actual(self):
        meses = [
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
        ]
        return meses[datetime.now().month - 1]

    def _max_asistencias_mes(self, socio):
        """Calcula el máximo mensual real según el cupo semanal del socio.

        Divide el mes por semanas reales (lunes a domingo), excluye los domingos
        y limita cada semana al número de asistencias contratado. También ajusta
        automáticamente las semanas parciales del principio y del final del mes.
        """
        hoy = datetime.now().date()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        primer_dia_mes = hoy.replace(day=1)
        ultimo_dia_mes = hoy.replace(day=ultimo_dia)

        cupo_semanal = max(1, min(int(self._total_asistencias_plan(socio)), 6))
        total = 0
        inicio_semana = primer_dia_mes.fromordinal(
            primer_dia_mes.toordinal() - primer_dia_mes.weekday()
        )

        while inicio_semana <= ultimo_dia_mes:
            dias_disponibles = 0
            for desplazamiento in range(6):  # lunes a sábado
                fecha = inicio_semana.fromordinal(inicio_semana.toordinal() + desplazamiento)
                if primer_dia_mes <= fecha <= ultimo_dia_mes:
                    dias_disponibles += 1

            total += min(cupo_semanal, dias_disponibles)
            inicio_semana = inicio_semana.fromordinal(inicio_semana.toordinal() + 7)

        return total

    def _asistencias_mes(self, socio):
        inicio, fin = self._rango_mes_actual()
        try:
            res = (self.supabase.table('asistencias')
                   .select('fecha')
                   .eq('dni', str(socio.get('dni', '')))
                   .gte('fecha', inicio)
                   .lte('fecha', fin)
                   .execute())
            fechas = set()
            for fila in (res.data or []):
                fecha_txt = str(fila.get('fecha', ''))[:10]
                if not fecha_txt:
                    continue
                try:
                    fecha = datetime.strptime(fecha_txt, '%Y-%m-%d').date()
                except ValueError:
                    continue
                if fecha.weekday() != 6:
                    fechas.add(fecha_txt)
            return len(fechas)
        except Exception:
            return 0

    def _registrar_asistencia(self, socio):
        dni = str(socio.get('dni', ''))
        hoy = datetime.now().date().isoformat()
        realizadas, ya_hoy = self._estado_asistencia(socio)
        if ya_hoy:
            return realizadas, self._total_asistencias_plan(socio), False
        try:
            self.supabase.table('asistencias').insert({
                'dni': dni,
                'fecha': hoy,
                'creado_en': datetime.now().isoformat()
            }).execute()
        except Exception as e:
            QMessageBox.critical(
                self,
                'Error de asistencia',
                'No se pudo registrar la asistencia.\n\n'
                'Verificá que exista la tabla "asistencias" en Supabase.\n\n'
                f'Detalle: {e}'
            )
            return None

        realizadas, _ = self._estado_asistencia(socio)
        total = self._total_asistencias_plan(socio)
        return realizadas, total, True

    def _campo_info(self, etiqueta, valor):
        w = QFrame()
        w.setStyleSheet('background: #111; border-radius: 10px; border: 1px solid #2a2a2a;')
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 12, 16, 12)
        le = QLabel(etiqueta)
        le.setStyleSheet('color: #888; font-size: 15px; min-width: 160px;')
        lv = QLabel(str(valor or '—'))
        lv.setStyleSheet('color: white; font-size: 16px; font-weight: bold;')
        lv.setWordWrap(True)
        h.addWidget(le)
        h.addWidget(lv, 1)
        return w

    def _mostrar_planilla_medica(self, socio):
        datos = str(socio.get('salud_info', '') or '')
        nombres = {
            'cardio': 'Problemas cardíacos',
            'presion': 'Presión arterial alta o baja',
            'diabetes': 'Diabetes',
            'respiratorio': 'Problemas respiratorios (asma, etc.)',
            'lesiones': 'Lesiones musculares o articulares',
            'cirugia': 'Cirugías recientes (menos de 6 meses)',
            'medicacion': 'Medicación regular',
            'embarazo': 'Embarazo o lactancia',
        }
        dlg = QDialog(self)
        dlg.setWindowTitle('Planilla médica del socio')
        dlg.setMinimumWidth(560)
        dlg.setStyleSheet("background:#1a1a1a; color:white; font-family:'Urbanist','Segoe UI';")
        l = QVBoxLayout(dlg)
        l.setContentsMargins(30, 25, 30, 25)
        l.setSpacing(12)
        tit = QLabel('PLANILLA MÉDICA')
        tit.setStyleSheet(f'font-size:22px; font-weight:900; color:{self.c_boton};')
        l.addWidget(tit)

        if not datos:
            l.addWidget(self._campo_info('Estado:', 'Planilla no completada'))
        else:
            condiciones = []
            observaciones = ''
            for parte in datos.split('|'):
                if parte.startswith('OBS:'):
                    observaciones = parte[4:]
                elif parte in nombres:
                    condiciones.append(nombres[parte])
            if condiciones:
                for condicion in condiciones:
                    l.addWidget(self._campo_info('Alerta:', condicion))
            else:
                l.addWidget(self._campo_info('Condiciones:', 'Sin condiciones declaradas'))
            if observaciones:
                l.addWidget(self._campo_info('Observaciones:', observaciones))

        btn = QPushButton('CERRAR')
        btn.setProperty('class', 'hd_btn')
        btn.setFixedHeight(52)
        btn.clicked.connect(dlg.accept)
        l.addSpacing(8)
        l.addWidget(btn)
        dlg.exec()

    def _crear_tabla_rutina(self, ejercicios):
        tabla = QTableWidget(0, 4)
        tabla.setHorizontalHeaderLabels(['Ejercicio', 'Series', 'Repeticiones', 'Elemento'])
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        tabla.verticalHeader().setVisible(True)
        tabla.verticalHeader().setMinimumWidth(52)
        tabla._completados = set()
        tabla._completado_en = {}

        for ej in ejercicios or []:
            ej = ej if isinstance(ej, dict) else {}
            r = tabla.rowCount()
            tabla.insertRow(r)
            tabla.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
            tabla.setItem(r, 0, QTableWidgetItem(str(ej.get('ejercicio', '') or '')))
            tabla.setItem(r, 1, QTableWidgetItem(str(ej.get('series', '') or '')))
            tabla.setItem(r, 2, QTableWidgetItem(str(ej.get('repeticiones', '') or '')))
            tabla.setItem(r, 3, QTableWidgetItem(str(ej.get('elemento', '') or '')))
            if bool(ej.get('completado', False)):
                tabla._completados.add(r)
                tabla._completado_en[r] = ej.get('completado_en') or None
                self._pintar_fila_completada(tabla, r)
        return tabla

    def _pintar_fila_completada(self, tabla, fila):
        for col in range(tabla.columnCount()):
            item = tabla.item(fila, col)
            if item is None:
                item = QTableWidgetItem('')
                tabla.setItem(fila, col, item)
            item.setBackground(QColor('#14532d'))
            item.setForeground(QColor('white'))
        tabla.setVerticalHeaderItem(fila, QTableWidgetItem(f'✓ {fila + 1}'))

    def _fila_seleccionada(self, tabla):
        fila = tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(self, 'Rutina', 'Seleccioná primero un ejercicio de la rutina.')
            return -1
        return fila

    def _rutina_desde_tabs(self, tablas):
        rutina = {}
        for dia, tabla in tablas.items():
            ejercicios = []
            completados = getattr(tabla, '_completados', set())
            completado_en = getattr(tabla, '_completado_en', {})
            for r in range(tabla.rowCount()):
                ejercicios.append({
                    'ejercicio': tabla.item(r, 0).text().strip() if tabla.item(r, 0) else '',
                    'series': tabla.item(r, 1).text().strip() if tabla.item(r, 1) else '',
                    'repeticiones': tabla.item(r, 2).text().strip() if tabla.item(r, 2) else '',
                    'elemento': tabla.item(r, 3).text().strip() if tabla.item(r, 3) else '',
                    'completado': r in completados,
                    'completado_en': completado_en.get(r) if r in completados else None,
                })
            rutina[dia] = ejercicios
        return rutina

    def _ejercicios_base_desde_tabla(self, tabla):
        ejercicios = []
        for r in range(tabla.rowCount()):
            ejercicios.append({
                'ejercicio': tabla.item(r, 0).text().strip() if tabla.item(r, 0) else '',
                'series': tabla.item(r, 1).text().strip() if tabla.item(r, 1) else '',
                'repeticiones': tabla.item(r, 2).text().strip() if tabla.item(r, 2) else '',
                'elemento': tabla.item(r, 3).text().strip() if tabla.item(r, 3) else '',
            })
        return ejercicios

    def _marcar_ejercicio_hecho(self, dni, dia_num, tabla, tablas):
        fila = self._fila_seleccionada(tabla)
        if fila < 0:
            return
        tabla._completados.add(fila)
        tabla._completado_en[fila] = datetime.now().isoformat()
        self._pintar_fila_completada(tabla, fila)
        self._guardar_sesion_hoy(dni, dia_num, self._rutina_desde_tabs(tablas))

    def _modificar_ejercicio(self, dni, dia_num, dia_clave, tabla, tablas):
        fila = self._fila_seleccionada(tabla)
        if fila < 0:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f'Modificar ejercicio {fila + 1}')
        dlg.setMinimumWidth(470)
        dlg.setStyleSheet("background:#1a1a1a; color:white; font-family:'Urbanist','Segoe UI';")
        form = QFormLayout(dlg)
        form.setContentsMargins(28, 24, 28, 24)
        form.setVerticalSpacing(14)
        inp_series = QLineEdit(tabla.item(fila, 1).text() if tabla.item(fila, 1) else '')
        inp_rep = QLineEdit(tabla.item(fila, 2).text() if tabla.item(fila, 2) else '')
        inp_elem = QLineEdit(tabla.item(fila, 3).text() if tabla.item(fila, 3) else '')
        form.addRow('Series:', inp_series)
        form.addRow('Repeticiones:', inp_rep)
        form.addRow('Elemento:', inp_elem)
        botones = QHBoxLayout()
        cancelar = QPushButton('CANCELAR')
        cancelar.setStyleSheet('background:#333; color:white; font-weight:bold; padding:12px; border-radius:10px;')
        guardar = QPushButton('GUARDAR CAMBIOS')
        guardar.setStyleSheet('background:#f59e0b; color:black; font-weight:900; padding:12px; border-radius:10px;')
        cancelar.clicked.connect(dlg.reject)

        def aplicar():
            for col, valor in ((1, inp_series.text()), (2, inp_rep.text()), (3, inp_elem.text())):
                tabla.setItem(fila, col, QTableWidgetItem(valor.strip()))
            if fila in getattr(tabla, '_completados', set()):
                self._pintar_fila_completada(tabla, fila)

            rutina_base = self._cargar_rutina(dni)
            if not isinstance(rutina_base, dict):
                rutina_base = {}
            rutina_base[dia_clave] = self._ejercicios_base_desde_tabla(tabla)
            if not self._guardar_rutina(dni, rutina_base):
                return
            if not self._guardar_sesion_hoy(dni, dia_num, self._rutina_desde_tabs(tablas)):
                return
            dlg.accept()

        guardar.clicked.connect(aplicar)
        botones.addWidget(cancelar)
        botones.addStretch()
        botones.addWidget(guardar)
        form.addRow(botones)
        dlg.exec()

    def _limpiar_ejercicio(self, dni, dia_num, dia_clave, tabla, tablas):
        fila = self._fila_seleccionada(tabla)
        if fila < 0:
            return
        resp = QMessageBox.question(
            self,
            'Limpiar ejercicio',
            f'¿Vaciar por completo el ejercicio {fila + 1}?\nEl número de slot se conservará.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        for col in range(tabla.columnCount()):
            tabla.setItem(fila, col, QTableWidgetItem(''))
        tabla._completados.discard(fila)
        tabla._completado_en.pop(fila, None)
        tabla.setVerticalHeaderItem(fila, QTableWidgetItem(str(fila + 1)))

        rutina_base = self._cargar_rutina(dni)
        if not isinstance(rutina_base, dict):
            rutina_base = {}
        rutina_base[dia_clave] = self._ejercicios_base_desde_tabla(tabla)
        if self._guardar_rutina(dni, rutina_base):
            self._guardar_sesion_hoy(dni, dia_num, self._rutina_desde_tabs(tablas))

    def _vaciar_resultado(self):
        while self.layout_resultado.count():
            item = self.layout_resultado.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _datos_vencimiento(self, socio):
        venc = socio.get('vencimiento', '—')
        try:
            venc_dt = datetime.strptime(venc, '%Y-%m-%d').date()
            venc_txt = venc_dt.strftime('%d/%m/%Y')
            dias = (venc_dt - datetime.now().date()).days
            return venc_txt, dias
        except (ValueError, TypeError):
            return str(venc or '—'), None

    def _mostrar_datos_previos_asistencia(self, socio):
        self._vaciar_resultado()
        nombre = str(socio.get('nombre', '') or '')
        apellido = str(socio.get('apellido', '') or '')
        edad = self._calcular_edad(socio.get('fecha_nacimiento', ''))
        edad_txt = f'{edad} años' if edad is not None else '—'
        venc, dias = self._datos_vencimiento(socio)
        realizadas, _ = self._estado_asistencia(socio)
        total_asistencias = self._total_asistencias_plan(socio)

        tit = QLabel(f'{nombre} {apellido}'.strip().upper())
        tit.setStyleSheet(f'font-size: 36px; font-weight: 900; color: {self.c_boton}; margin-bottom: 8px;')
        self.layout_resultado.addWidget(tit)

        # El botón de asistencia aparece antes de los datos, como acción principal.
        btn_asistencia = QPushButton('✓ REGISTRAR ASISTENCIA')
        btn_asistencia.setStyleSheet(
            'background:#10b981; color:white; font-weight:900; font-size:17px; '
            'padding:14px; border-radius:10px;'
        )
        btn_asistencia.clicked.connect(
            lambda checked=False, s=socio: self._registrar_y_abrir_rutina(s)
        )
        self.layout_resultado.addWidget(btn_asistencia)

        self.layout_resultado.addWidget(self._campo_info('Nombre:', nombre))
        self.layout_resultado.addWidget(self._campo_info('Apellido:', apellido))
        self.layout_resultado.addWidget(self._campo_info('DNI:', socio.get('dni', '')))
        self.layout_resultado.addWidget(self._campo_info('Edad:', edad_txt))
        self.layout_resultado.addWidget(self._campo_info('Vencimiento:', venc))
        self.layout_resultado.addWidget(self._campo_info('Plan:', self._texto_plan(socio)))
        self.layout_resultado.addWidget(
            self._campo_info('Asistencias esta semana:', f'{realizadas}/{total_asistencias}')
        )
        self.layout_resultado.addWidget(
            self._campo_info(
                f'Asistencias de {self._nombre_mes_actual()}:',
                f'{self._asistencias_mes(socio)}/{self._max_asistencias_mes(socio)}'
            )
        )

        if dias is not None:
            color = '#10b981' if dias >= 0 else '#ef4444'
            estado = 'ACTIVO' if dias >= 0 else 'VENCIDO'
            lbl_est = QLabel(f'● {estado} — {abs(dias)} días')
            lbl_est.setStyleSheet(f'font-size: 20px; font-weight: bold; color: {color}; margin: 12px 0;')
            self.layout_resultado.addWidget(lbl_est)

        self.layout_resultado.addStretch()

    def _registrar_y_abrir_rutina(self, socio):
        resultado = self._registrar_asistencia(socio)
        if resultado is None:
            return
        realizadas, total, fue_nueva = resultado
        if fue_nueva and self._cargar_sesion_hoy(socio.get('dni', '')) is None:
            self._crear_sesion_hoy(socio, realizadas)
        self._mostrar_vista_rutina(socio, realizadas)
        if fue_nueva:
            QMessageBox.information(self, 'Asistencia', f'Asistencia registrada: {realizadas}/{total}.')

    def _mostrar_vista_rutina(self, socio, asistencia_semana=None):
        self._vaciar_resultado()
        dni = str(socio.get('dni', '') or '')
        nombre = str(socio.get('nombre', '') or '')
        apellido = str(socio.get('apellido', '') or '')

        tit = QLabel(f'RUTINA - {nombre} {apellido}'.strip().upper())
        tit.setStyleSheet(f'font-size: 32px; font-weight: 900; color: {self.c_boton}; margin-bottom: 8px;')
        self.layout_resultado.addWidget(tit)

        btn_planilla = QPushButton('📋 VER PLANILLA MÉDICA')
        btn_planilla.setStyleSheet(
            'background:#1a3a5a; color:white; font-weight:900; padding:12px; border-radius:10px;'
        )
        btn_planilla.clicked.connect(
            lambda checked=False, s=socio: self._mostrar_planilla_medica(s)
        )
        self.layout_resultado.addWidget(btn_planilla)

        if asistencia_semana is None:
            asistencia_semana, _ = self._estado_asistencia(socio)

        # Si por algún motivo existe la asistencia pero todavía no la sesión,
        # la reconstruimos automáticamente con la rutina actual.
        sesion = self._cargar_sesion_hoy(dni)
        if sesion is None:
            sesion = self._crear_sesion_hoy(socio, asistencia_semana or 1)

        rutina = sesion.get('rutina', {}) if isinstance(sesion, dict) else {}
        if not isinstance(rutina, dict) or not rutina:
            rutina = self._preparar_snapshot_sesion(self._cargar_rutina(dni), self._dias_rutina(socio))

        dias_r = self._dias_rutina(socio)
        try:
            dia_guardado = int((sesion or {}).get('dia_rutina', asistencia_semana or 1) or 1)
        except (TypeError, ValueError):
            dia_guardado = int(asistencia_semana or 1)
        dia_guardado = max(1, min(dia_guardado, max(1, dias_r)))

        tabs = QTabWidget()
        tablas = {}
        hay_rutina = False

        for dia_num in range(1, dias_r + 1):
            key = f'Dia {dia_num}'
            ejercicios = rutina.get(key, []) if isinstance(rutina, dict) else []
            if ejercicios:
                hay_rutina = True
            pag = QWidget()
            pl = QVBoxLayout(pag)
            tabla = self._crear_tabla_rutina(ejercicios)
            tablas[key] = tabla
            if ejercicios:
                pl.addWidget(tabla)
            else:
                pl.addWidget(QLabel('Sin ejercicios cargados'))
                pl.addWidget(tabla)

            acciones = QHBoxLayout()
            btn_hecho = QPushButton('✓')
            btn_hecho.setToolTip('Marcar ejercicio como hecho y guardar el progreso')
            btn_hecho.setFixedSize(62, 46)
            btn_hecho.setStyleSheet(
                'background:#10b981; color:white; font-size:24px; font-weight:900; border-radius:10px;'
            )
            btn_hecho.clicked.connect(
                lambda checked=False, d=dia_num, t=tabla: self._marcar_ejercicio_hecho(dni, d, t, tablas)
            )

            btn_mod = QPushButton('/')
            btn_mod.setToolTip('Modificar series, repeticiones o elemento')
            btn_mod.setFixedSize(62, 46)
            btn_mod.setStyleSheet(
                'background:#f59e0b; color:black; font-size:24px; font-weight:900; border-radius:10px;'
            )
            btn_mod.clicked.connect(
                lambda checked=False, d=dia_num, k=key, t=tabla: self._modificar_ejercicio(dni, d, k, t, tablas)
            )

            btn_limpiar = QPushButton('✕')
            btn_limpiar.setToolTip('Vaciar este slot de ejercicio')
            btn_limpiar.setFixedSize(62, 46)
            btn_limpiar.setStyleSheet(
                'background:#ef4444; color:white; font-size:22px; font-weight:900; border-radius:10px;'
            )
            btn_limpiar.clicked.connect(
                lambda checked=False, d=dia_num, k=key, t=tabla: self._limpiar_ejercicio(dni, d, k, t, tablas)
            )

            acciones.addWidget(btn_hecho)
            acciones.addWidget(btn_mod)
            acciones.addWidget(btn_limpiar)
            acciones.addStretch()
            pl.addLayout(acciones)
            tabs.addTab(pag, key)

        if tabs.count() > 0:
            tabs.setCurrentIndex(dia_guardado - 1)

            # Cambiar manualmente de día también queda guardado para que Administración
            # sepa qué día de la rutina se eligió realmente en esa sesión.
            def cambio_dia(indice):
                if indice >= 0:
                    self._guardar_sesion_hoy(
                        dni,
                        indice + 1,
                        self._rutina_desde_tabs(tablas),
                        mostrar_error=False
                    )
            tabs.currentChanged.connect(cambio_dia)

        if not hay_rutina and not rutina:
            self.layout_resultado.addWidget(QLabel('Sin rutina registrada.'))
        else:
            self.layout_resultado.addWidget(tabs)
        self.layout_resultado.addStretch()

    def buscar_socio(self):
        dni = self.in_dni.text().strip()
        if not dni:
            return
        try:
            res = self.supabase.table('socios').select('*').eq('dni', dni).execute()
            if not res.data:
                self._limpiar_resultado('')
                err = QLabel('❌ SOCIO NO REGISTRADO')
                err.setStyleSheet('font-size: 28px; font-weight: 900; color: #ef4444;')
                self.layout_resultado.takeAt(0)
                self.layout_resultado.insertWidget(0, err)
                return

            socio = res.data[0]
            realizadas, ya_hoy = self._estado_asistencia(socio)

            # Si ya registró asistencia hoy, al volver a ingresar el DNI se abre
            # directamente la rutina en el día correspondiente. Al cambiar de fecha,
            # vuelve a aparecer la ficha con el botón REGISTRAR ASISTENCIA.
            if ya_hoy:
                self._mostrar_vista_rutina(socio, realizadas)
            else:
                self._mostrar_datos_previos_asistencia(socio)

        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RecepcionGym()
    window.show()
    sys.exit(app.exec())
