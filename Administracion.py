import sys
import os
import time
import urllib.request
import urllib.error
import base64
import webbrowser
import re
import json
import calendar
import gzip
import hashlib
from datetime import datetime
from urllib.parse import quote
from urllib.request import urlopen
from supabase import create_client, Client
try:
    from supabase.client import ClientOptions
except ImportError:
    from supabase.lib.client_options import ClientOptions
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLabel, QLineEdit, QComboBox, QDateEdit, QCheckBox,
                             QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
                             QMessageBox, QFileDialog, QFormLayout, QColorDialog, QGraphicsDropShadowEffect,
                             QInputDialog, QTextEdit, QDialog, QScrollArea, QSpinBox, QTabWidget,
                             QRadioButton, QButtonGroup, QCalendarWidget, QTabBar)
from PyQt6.QtCore import Qt, QDate, QTimer, QEvent
from PyQt6.QtGui import QColor, QFont, QBrush, QPainter, QIntValidator, QTextCharFormat



# === ACTUALIZADOR REMOTO GITHUB ===
VERSION_ACTUAL = '6.0.0'
URL_VERSION = 'https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/administracion/version.txt'
URL_UPDATE_PY = 'https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/administracion/Administracion.py'
URL_UPDATE_EXE = 'https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/administracion/Administracion.exe'


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
    """Comprueba version.txt en GitHub y, con confirmacion, inicia el reemplazo por .bat."""
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
            f"No se pudo leer version.txt en GitHub (HTTP {e.code}).\n\n"
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
PLANES_DISPONIBLES = [PLAN_SEMIPERSONALIZADO, PLAN_PERSONALIZADO, PLAN_PASE_LIBRE]

class DateEditSinRueda(QDateEdit):
    """Evita cambiar la fecha con la rueda del mouse."""
    def wheelEvent(self, event):
        event.ignore()

class TabBarSinRueda(QTabBar):
    """Evita cambiar de día de rutina accidentalmente con la rueda del mouse."""
    def wheelEvent(self, event):
        event.ignore()

class TabWidgetSinRueda(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(TabBarSinRueda(self))

class CalendarMesFijo(QCalendarWidget):
    """Calendario de solo lectura: no cambia de mes con la rueda."""
    def wheelEvent(self, event):
        # Consumimos el evento para que el calendario no cambie ni desplace su contenido.
        event.accept()


if sys.platform == 'win32':
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

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
APP_ACCESS_TOKEN = str(_CONFIG_SUPABASE.get("admin_access_token") or "").strip()
APP_ACCESS_HEADER = "x-la-herencia-token"
ALIAS_NEGOCIO = "LaHerenciaGym"
TELEGRAM_BOT_TOKEN = os.getenv("GYM_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("GYM_TELEGRAM_CHAT_ID", "")
TELEGRAM_HORA_RECORDATORIO = "06:00"
TELEGRAM_DIAS_ANTES_VENCIMIENTO = 2
HERENCIA_MORADO = "#8b3dff"
HERENCIA_TEXTO_BOTON = "#ffffff"

HISTORIAL_BUCKET = "historial-entrenamientos"
HISTORIAL_RETENCION_ANIOS = 2
HISTORIAL_MANTENIMIENTO_DIAS = 30



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
            "Falta 'admin_access_token' dentro de config_supabase.json.\n"
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


class BotonConNotificacion(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.count = 0
        self.setProperty("class", "hd_menu")

    def set_notification(self, count):
        self.count = count
        self.update() 

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            rect_size = 32
            # Circulito rojo
            painter.setBrush(QColor("#ef4444"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(10, 10, rect_size, rect_size)
            
            # Número adentro
            painter.setPen(QColor("white"))
            font = QFont("Urbanist", 12, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(10, 10, rect_size, rect_size, Qt.AlignmentFlag.AlignCenter, str(self.count))

# === PLANILLA DE SALUD ===
PREGUNTAS_SALUD = {
    "cardio":       "Problemas cardíacos",
    "presion":      "Presión arterial alta o baja",
    "diabetes":     "Diabetes",
    "respiratorio": "Problemas respiratorios (asma, etc.)",
    "lesiones":     "Lesiones musculares o articulares",
    "cirugia":      "Cirugías recientes (menos de 6 meses)",
    "medicacion":   "Medicación regular",
    "embarazo":     "Embarazo o lactancia",
}

class DialogPlanillaSalud(QDialog):
    def __init__(self, datos_previos="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Planilla de Salud del Socio")
        self.setMinimumWidth(520)
        self.setStyleSheet("background: #1a1a1a; color: white; font-family: 'Urbanist', 'Segoe UI';")
        l = QVBoxLayout(self)
        l.setSpacing(14); l.setContentsMargins(30, 25, 30, 25)

        tit = QLabel("EVALUACIÓN DE SALUD INICIAL")
        tit.setStyleSheet("font-size: 20px; font-weight: 900; color: #ff7a00;")
        l.addWidget(tit)
        sub = QLabel("Marcá las condiciones que apliquen al socio.")
        sub.setStyleSheet("color: #aaa; font-size: 13px;")
        l.addWidget(sub); l.addSpacing(8)

        self.checks = {}
        prev = set(datos_previos.split("|")) if datos_previos else set()
        for key, texto in PREGUNTAS_SALUD.items():
            cb = QCheckBox(texto)
            cb.setStyleSheet("QCheckBox { color: white; font-size: 14px; padding: 4px; } QCheckBox::indicator { width: 20px; height: 20px; }")
            cb.setChecked(key in prev)
            self.checks[key] = cb
            l.addWidget(cb)

        l.addSpacing(10)
        lbl_obs = QLabel("Observaciones / Notas médicas:")
        lbl_obs.setStyleSheet("color: #aaa; font-size: 13px;")
        l.addWidget(lbl_obs)
        self.obs = QTextEdit()
        self.obs.setFixedHeight(90)
        self.obs.setStyleSheet("background: #111; border: 1px solid #444; border-radius: 8px; color: white; padding: 8px;")
        obs_previa = ""
        if datos_previos and "OBS:" in datos_previos:
            obs_previa = datos_previos.split("OBS:", 1)[1]
        self.obs.setPlainText(obs_previa)
        l.addWidget(self.obs)

        l.addSpacing(10)
        h_btn = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet("background: #333; color: white; padding: 14px; border-radius: 10px;")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("✅ CONFIRMAR")
        btn_ok.setStyleSheet("background: #ff7a00; color: black; font-weight: bold; padding: 14px; border-radius: 10px;")
        btn_ok.clicked.connect(self.accept)
        h_btn.addWidget(btn_cancel); h_btn.addWidget(btn_ok)
        l.addLayout(h_btn)

    def get_datos(self):
        marcadas = [k for k, cb in self.checks.items() if cb.isChecked()]
        obs = self.obs.toPlainText().strip()
        resultado = "|".join(marcadas)
        if obs:
            resultado += f"|OBS:{obs}"
        return resultado

# === CLASE PRINCIPAL ADMINISTRACIÓN ===
class AdminGym(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Administración ULTRA HD - La Herencia Gym v6.0")
        self.resize(1100, 850)
        
        self.c_fondo = "#0a0a0a"; self.c_boton = HERENCIA_MORADO; self.c_texto = HERENCIA_TEXTO_BOTON
        self.c_app_fondo = "#000000"
        self.c_app_modo = "oscuro"
        
        self.supabase: Client = crear_cliente_supabase_sin_login(self)
        if self.supabase is None:
            sys.exit()
        try:
            self.descargar_apariencia()
        except Exception as e:
            QMessageBox.critical(self, "Error Fatal", f"No se pudo cargar la configuración de nube: {e}")
            sys.exit()

        # Timer para buscar nuevos pedidos en la web (cada 20 seg)
        self.timer_pedidos = QTimer()
        self.timer_pedidos.timeout.connect(self.chequear_pedidos_nube)
        self.timer_pedidos.start(20000)

        # Timer para mandar el resumen diario de vencimientos por Telegram.
        self.timer_telegram = QTimer()
        self.timer_telegram.timeout.connect(self.chequear_envio_diario_telegram)
        self.timer_telegram.start(60000)

        self.pantallas = QStackedWidget()
        self.pantallas.addWidget(self.crear_menu())      # 0
        self.pantallas.addWidget(self.crear_pedidos())   # 1
        self.pantallas.addWidget(self.crear_registro())  # 2
        self.pantallas.addWidget(self.crear_renovar())   # 3
        self.pantallas.addWidget(self.crear_socios())    # 4
        self.pantallas.addWidget(self.crear_precios())   # 5
        self.pantallas.addWidget(self.crear_diseno())    # 6
        self.pantallas.addWidget(self.crear_ventas())    # 7
        self.pantallas.addWidget(self.crear_stock())     # 8
        self.pantallas.addWidget(self.crear_inscripciones()) # 9
        self.pantallas.addWidget(self.crear_gestionar_planes()) # 10
        self.pantallas.addWidget(self.crear_recordatorios()) # 11
        self.pantallas.addWidget(self.crear_ficha_socio()) # 12
        self.pantallas.addWidget(self.crear_editor_plan_pantalla()) # 13
        QApplication.instance().installEventFilter(self)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.pantallas)
        
        self.aplicar_estilos_hd()
        self.chequear_pedidos_nube() # Chequeo inicial
        self.chequear_recordatorios_vencimiento()
        self.chequear_envio_diario_telegram()
        QTimer.singleShot(5000, self.ejecutar_mantenimiento_historial)
        self._crear_boton_actualizacion()

    def _crear_boton_actualizacion(self):
        self.btn_actualizacion_global = QPushButton("ACTUALIZACIÓN", self)
        self.btn_actualizacion_global.setFixedSize(150, 38)
        self.btn_actualizacion_global.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_actualizacion_global.setStyleSheet(
            f"QPushButton {{ background:#191919; color:white; border:2px solid {HERENCIA_MORADO}; "
            "border-radius:9px; font-size:12px; font-weight:900; padding:4px 10px; }} "
            "QPushButton:hover { background:white; color:black; }"
        )
        self.btn_actualizacion_global.clicked.connect(lambda: comprobar_actualizacion(self))
        self._reposicionar_boton_actualizacion()
        self.btn_actualizacion_global.raise_()
        self.btn_actualizacion_global.show()

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
                self.c_fondo = res.data[0].get('color_fondo', '#0a0a0a')
                self.c_boton = HERENCIA_MORADO
                self.c_texto = HERENCIA_TEXTO_BOTON
                self.c_app_fondo = res.data[0].get('color_app_fondo', '#000000')
                self.c_app_modo = 'oscuro'
        except: pass

    def aplicar_estilos_hd(self):
        sz = '16'
        self.c_app_modo = 'oscuro'
        self.c_app_fondo = '#000000'
        self.c_boton = HERENCIA_MORADO
        self.c_texto = HERENCIA_TEXTO_BOTON
        fondo_app = '#000000'
        texto_app = '#ffffff'
        texto_suave = '#aaa'
        input_bg = '#1a1a1a'
        input_border = '#444'
        tabla_bg = '#111'
        tabla_grid = '#222'
        tabla_border = '#333'
        vertical_header_bg = '#1a1a1a'
        sz_menu = '20'
        estilo = f"""
            QWidget {{ background-color: {fondo_app}; color: {texto_app}; font-family: 'Urbanist', 'Segoe UI'; font-size: {sz}px; }}

            QLabel {{ color: {texto_app}; }}

            QLineEdit, QComboBox, QDateEdit, QTextEdit, QSpinBox {{
                background: {input_bg}; border: 1px solid {input_border}; border-radius: 10px; padding: 12px; color: {texto_app};
            }}
            QLineEdit:focus, QTextEdit:focus {{ border: 2px solid {self.c_boton}; }}

            QPushButton {{
                background: #242424; color: {texto_app}; font-weight: bold; border-radius: 10px; padding: 8px 14px;
                border: 2px solid {input_border};
            }}
            QPushButton:hover {{ background: white; color: black; border: 2px solid {self.c_boton}; }}

            QPushButton.hd_menu {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.1), stop:0.1 {self.c_boton}, stop:0.9 {self.c_boton}, stop:1 rgba(0,0,0,0.3));
                color: {self.c_texto}; font-weight: 900; font-size: {sz_menu}px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.15);
                text-transform: uppercase;
            }}
            QPushButton.hd_menu:hover {{ background: white; color: black; border: 2px solid {self.c_boton}; }}

            QPushButton.accion {{
                background: {self.c_boton}; color: {self.c_texto}; font-weight: bold; border-radius: 10px;
                padding: 8px 14px; border: 2px solid {self.c_boton}; text-transform: uppercase;
            }}
            QPushButton.accion:hover {{ background: white; color: black; border: 2px solid {self.c_boton}; }}

            QTableWidget {{ background: {tabla_bg}; color: {texto_app}; gridline-color: {tabla_grid}; border-radius: 15px; border: 1px solid {tabla_border}; }}
            QHeaderView::section {{ background: {self.c_boton}; color: {self.c_texto}; font-weight: bold; padding: 12px; border: none; }}
            QTableWidget QHeaderView::section:vertical {{ background: {vertical_header_bg}; color: {texto_suave}; font-size: 12px; min-width: 44px; }}
        """
        self.setStyleSheet(estilo)
        self.aplicar_hover_a_botones()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, QPushButton):
                QTimer.singleShot(0, lambda b=child: self.aplicar_hover_boton(b))
        return super().eventFilter(obj, event)

    def aplicar_hover_a_botones(self):
        for btn in self.findChildren(QPushButton):
            self.aplicar_hover_boton(btn)

    def aplicar_hover_boton(self, btn):
        css = btn.styleSheet()
        if not css.strip() or "hover-la-herencia" in css:
            return
        hover = f"""
/* hover-la-herencia */
QPushButton:hover {{ background: white; color: black; border: 2px solid {HERENCIA_MORADO}; padding: 8px 14px; }}
"""
        btn.setStyleSheet(css.rstrip() + hover)

    def cabecera(self, txt):
        l = QHBoxLayout()
        btn = QPushButton("⬅ VOLVER")
        btn.setProperty("class", "accion"); btn.setFixedSize(150, 45)
        btn.clicked.connect(lambda: self.pantallas.setCurrentIndex(0))
        l.addWidget(btn); l.addSpacing(20)
        lbl = QLabel(txt); lbl.setStyleSheet(f"font-size: 30px; font-weight: bold; color: {self.c_boton};")
        l.addWidget(lbl); l.addStretch()
        return l

    def _configurar_fecha_nacimiento(self, widget):
        widget.setDisplayFormat("dd/MM/yyyy")
        widget.setMinimumWidth(200)
        widget.setMinimumHeight(44)
        widget.setMaximumDate(QDate.currentDate())
        widget.setDate(QDate(2000, 1, 1))
        cal = widget.calendarWidget()
        cal.setMinimumSize(360, 320)
        cal.setGridVisible(True)
        cal.setNavigationBarVisible(True)
        cal.setStyleSheet("""
            QCalendarWidget { background: #1a1a1a; color: white; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background: #111; min-height: 36px; }
            QCalendarWidget QToolButton {
                color: white; background: #333; border-radius: 6px; padding: 6px 12px;
                font-size: 14px; min-width: 80px;
            }
            QCalendarWidget QSpinBox { color: white; background: #333; min-width: 72px; padding: 4px; font-size: 14px; }
            QCalendarWidget QAbstractItemView:enabled { color: white; selection-background-color: #8b3dff; }
        """)

    def _estilo_tabs_rutina(self):
        return f"""
            QTabWidget::pane {{ border: 1px solid #333; border-radius: 10px; background: #111; }}
            QTabBar::tab {{
                background: #2a2a2a; color: #f0f0f0; padding: 10px 22px;
                margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px;
                font-weight: bold; font-size: 14px;
            }}
            QTabBar::tab:selected {{ background: {HERENCIA_MORADO}; color: white; }}
            QTabBar::tab:hover {{ background: #444; color: white; }}
        """

    def _clave_precio_db(self, plan, dias, transferencia=False):
        if transferencia:
            if plan == PLAN_SEMIPERSONALIZADO:
                return "Semipersonalizado_TR", int(dias)
            if plan == PLAN_PASE_LIBRE:
                return "Pase Libre_TR", 0
        if plan == PLAN_PASE_LIBRE:
            return PLAN_PASE_LIBRE, 0
        if plan == PLAN_PERSONALIZADO:
            return PLAN_PERSONALIZADO, 0
        return plan, int(dias)

    def _texto_plan_socio(self, socio):
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
            return self._dias_rutina_socio(socio)
        return max(1, val or self._dias_rutina_socio(socio))

    def _asistencias_semana(self, dni):
        inicio, fin = self._rango_semana_actual()
        try:
            res = (self.supabase.table('asistencias')
                   .select('fecha')
                   .eq('dni', str(dni))
                   .gte('fecha', inicio)
                   .lte('fecha', fin)
                   .execute())
            fechas = {str(r.get('fecha', ''))[:10] for r in (res.data or [])}
            return len([f for f in fechas if f])
        except Exception:
            return 0

    def _texto_asistencias(self, socio):
        total = self._total_asistencias_plan(socio)
        realizadas = self._asistencias_semana(socio.get('dni', ''))
        return f"{realizadas}/{total}"

    def _rango_mes_actual(self):
        hoy = datetime.now().date()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        inicio = hoy.replace(day=1)
        fin = hoy.replace(day=ultimo_dia)
        return inicio.isoformat(), fin.isoformat()

    def _nombre_mes_actual(self):
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        return meses[datetime.now().month - 1]

    def _max_asistencias_mes(self, socio):
        """Calcula el cupo mensual real según el plan y cómo cae el calendario.

        Cada semana se considera de lunes a domingo. Para cada semana que toca el
        mes actual se cuentan únicamente los días de lunes a sábado que pertenecen
        a ese mes y se suma como máximo el cupo semanal del socio. De esta forma,
        una semana parcial al inicio o al final del mes no puede aportar más
        asistencias que los días realmente disponibles.
        """
        hoy = datetime.now().date()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        primer_dia_mes = hoy.replace(day=1)
        ultimo_dia_mes = hoy.replace(day=ultimo_dia)

        cupo_semanal = max(1, min(int(self._total_asistencias_plan(socio)), 6))
        total = 0

        # Arrancamos en el lunes de la semana donde cae el día 1 del mes.
        inicio_semana = primer_dia_mes.fromordinal(
            primer_dia_mes.toordinal() - primer_dia_mes.weekday()
        )

        while inicio_semana <= ultimo_dia_mes:
            dias_disponibles = 0
            for desplazamiento in range(6):  # lunes(0) a sábado(5); domingo se excluye
                fecha = inicio_semana.fromordinal(inicio_semana.toordinal() + desplazamiento)
                if primer_dia_mes <= fecha <= ultimo_dia_mes:
                    dias_disponibles += 1

            total += min(cupo_semanal, dias_disponibles)
            inicio_semana = inicio_semana.fromordinal(inicio_semana.toordinal() + 7)

        return total

    def _asistencias_mes(self, dni):
        inicio, fin = self._rango_mes_actual()
        try:
            res = (self.supabase.table('asistencias')
                   .select('fecha')
                   .eq('dni', str(dni))
                   .gte('fecha', inicio)
                   .lte('fecha', fin)
                   .execute())
            fechas_validas = set()
            for fila in (res.data or []):
                fecha_txt = str(fila.get('fecha', ''))[:10]
                if not fecha_txt:
                    continue
                try:
                    fecha = datetime.strptime(fecha_txt, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if fecha.weekday() != 6:
                    fechas_validas.add(fecha_txt)
            return len(fechas_validas)
        except Exception:
            return 0

    def _texto_asistencias_mes(self, socio):
        realizadas = self._asistencias_mes(socio.get('dni', ''))
        maximo = self._max_asistencias_mes(socio)
        return f"{realizadas}/{maximo}"

    def _fechas_asistencia_mes(self, dni, anio, mes):
        """Devuelve las fechas (YYYY-MM-DD) con asistencia registrada en un mes."""
        try:
            ultimo = calendar.monthrange(int(anio), int(mes))[1]
            inicio = f"{int(anio):04d}-{int(mes):02d}-01"
            fin = f"{int(anio):04d}-{int(mes):02d}-{ultimo:02d}"
            res = (self.supabase.table('asistencias')
                   .select('fecha')
                   .eq('dni', str(dni))
                   .gte('fecha', inicio)
                   .lte('fecha', fin)
                   .execute())
            return {
                str(fila.get('fecha', ''))[:10]
                for fila in (res.data or [])
                if str(fila.get('fecha', ''))[:10]
            }
        except Exception as e:
            QMessageBox.critical(self, "Asistencias", f"No se pudieron cargar las asistencias.\n\n{e}")
            return set()

    def _crear_tabla_sesion_historica(self, ejercicios):
        tabla = QTableWidget(0, 5)
        tabla.setHorizontalHeaderLabels(["Ejercicio", "Series", "Repeticiones", "Elemento", "Estado"])
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        tabla.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        tabla.setColumnWidth(1, 105)
        tabla.setColumnWidth(2, 130)
        tabla.setColumnWidth(4, 125)
        tabla.verticalHeader().setMinimumWidth(48)
        tabla.verticalHeader().setDefaultSectionSize(58)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tabla.setStyleSheet(f"""
            QTableWidget {{ background:#111; color:white; gridline-color:#222; border:1px solid #333; font-size:14px; }}
            QTableWidget::item {{ padding:9px; }}
            QTableWidget::item:selected {{ background:#1a3a5a; color:white; }}
            QHeaderView::section {{ background:{HERENCIA_MORADO}; color:white; font-weight:900; padding:10px; border:none; }}
        """)

        for r, ej in enumerate(ejercicios or []):
            tabla.insertRow(r)
            tabla.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
            valores = [
                str(ej.get('ejercicio', '') or ''),
                str(ej.get('series', '') or ''),
                str(ej.get('repeticiones', '') or ''),
                str(ej.get('elemento', '') or ''),
                "✓ HECHO" if bool(ej.get('completado', False)) else "Pendiente",
            ]
            for c, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                tabla.setItem(r, c, item)
            if bool(ej.get('completado', False)):
                tabla.setVerticalHeaderItem(r, QTableWidgetItem(f"✓ {r + 1}"))
                for c in range(tabla.columnCount()):
                    item = tabla.item(r, c)
                    if item:
                        item.setBackground(QColor('#14532d'))
                        item.setForeground(QColor('white'))
        return tabla

    def _fechas_asistencia_rango(self, dni, fecha_desde, fecha_hasta):
        """Devuelve todas las asistencias de un rango inclusivo con una sola consulta."""
        try:
            res = (self.supabase.table('asistencias')
                   .select('fecha')
                   .eq('dni', str(dni))
                   .gte('fecha', str(fecha_desde))
                   .lte('fecha', str(fecha_hasta))
                   .order('fecha')
                   .execute())
            return {
                str(fila.get('fecha', ''))[:10]
                for fila in (res.data or [])
                if str(fila.get('fecha', ''))[:10]
            }
        except Exception as e:
            QMessageBox.critical(self, "Asistencias", f"No se pudieron cargar las asistencias.\n\n{e}")
            return set()

    def _nombre_mes_numero(self, mes):
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        try:
            return meses[int(mes) - 1]
        except Exception:
            return str(mes)

    def _fecha_ingreso_socio(self, socio):
        """Obtiene la fecha de ingreso real; para socios viejos usa su primera asistencia."""
        for campo in ('fecha_ingreso', 'created_at', 'creado_en'):
            valor = str(socio.get(campo, '') or '')[:10]
            q = QDate.fromString(valor, "yyyy-MM-dd")
            if q.isValid():
                return q

        dni = str(socio.get('dni', '') or '')
        try:
            res = (self.supabase.table('asistencias')
                   .select('fecha')
                   .eq('dni', dni)
                   .order('fecha')
                   .limit(1)
                   .execute())
            if res.data:
                valor = str(res.data[0].get('fecha', '') or '')[:10]
                q = QDate.fromString(valor, "yyyy-MM-dd")
                if q.isValid():
                    # Si ya se ejecutó el SQL nuevo, dejamos la fecha inferida guardada.
                    try:
                        self.supabase.table('socios').update({
                            'fecha_ingreso': q.toString('yyyy-MM-dd')
                        }).eq('dni', dni).execute()
                    except Exception:
                        pass
                    return q
        except Exception:
            pass
        return QDate.currentDate()

    def _rango_anual_socio(self, socio):
        """Año de socio actual, anclado al aniversario de su fecha de ingreso."""
        ingreso = self._fecha_ingreso_socio(socio)
        hoy = QDate.currentDate()
        inicio = ingreso
        while inicio.addYears(1) <= hoy:
            inicio = inicio.addYears(1)
        fin = inicio.addYears(1).addDays(-1)
        return inicio, fin

    def _cargar_sesion_archivada(self, dni, fecha_iso):
        """Busca una sesión antigua dentro del archivo mensual de Supabase Storage."""
        periodo = str(fecha_iso)[:7]
        try:
            meta = (self.supabase.table('historial_archivos')
                    .select('storage_path,sha256')
                    .eq('dni', str(dni))
                    .eq('periodo', periodo)
                    .limit(1)
                    .execute())
            if not meta.data:
                return None
            ruta = str(meta.data[0].get('storage_path', '') or '')
            if not ruta:
                return None
            bruto = self.supabase.storage.from_(HISTORIAL_BUCKET).download(ruta)
            bruto = bytes(bruto)
            checksum = str(meta.data[0].get('sha256', '') or '')
            if checksum and hashlib.sha256(bruto).hexdigest() != checksum:
                return None
            contenido = json.loads(gzip.decompress(bruto).decode('utf-8'))
            for sesion in contenido.get('sesiones', []):
                if str(sesion.get('fecha', ''))[:10] == str(fecha_iso)[:10]:
                    return sesion
        except Exception:
            return None
        return None

    def _cargar_sesion_historica(self, dni, fecha_iso):
        """Primero consulta PostgreSQL; si ya fue archivada, consulta Storage."""
        try:
            res = (self.supabase.table('sesiones_entrenamiento')
                   .select('*')
                   .eq('dni', str(dni))
                   .eq('fecha', str(fecha_iso))
                   .limit(1)
                   .execute())
            if res.data:
                return res.data[0]
        except Exception:
            pass
        return self._cargar_sesion_archivada(dni, fecha_iso)

    def _mostrar_sesion_historica(self, socio, fecha_iso, parent=None):
        """Muestra únicamente los ejercicios del día de rutina realizado en esa asistencia."""
        dni = str(socio.get('dni', '') or '')
        sesion = self._cargar_sesion_historica(dni, fecha_iso)

        if not sesion:
            QMessageBox.information(
                parent or self,
                "Rutina histórica",
                "La asistencia está registrada, pero no hay una rutina histórica guardada para ese día.\n\n"
                "Puede tratarse de una asistencia registrada antes de incorporar el historial detallado."
            )
            return

        rutina = sesion.get('rutina', {}) or {}
        if not isinstance(rutina, dict):
            rutina = {}
        try:
            dia_rutina = int(sesion.get('dia_rutina', 1) or 1)
        except (TypeError, ValueError):
            dia_rutina = 1

        # La sesión guarda una copia de la rutina completa. Para el historial mostramos
        # solamente el día que efectivamente se realizó en esa asistencia.
        clave_objetivo = None
        for clave in rutina.keys():
            m = re.search(r"(\d+)", str(clave))
            if m and int(m.group(1)) == dia_rutina:
                clave_objetivo = clave
                break
        ejercicios = rutina.get(clave_objetivo, []) if clave_objetivo is not None else []
        if not isinstance(ejercicios, list):
            ejercicios = []

        dlg = QDialog(parent or self)
        dlg.setWindowTitle(f"Rutina realizada - {fecha_iso}")
        dlg.setMinimumSize(900, 620)
        dlg.setStyleSheet("background:#1a1a1a; color:white; font-family:'Urbanist','Segoe UI';")
        l = QVBoxLayout(dlg)
        l.setContentsMargins(26, 24, 26, 24)
        l.setSpacing(14)

        try:
            fecha_txt = datetime.strptime(fecha_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            fecha_txt = fecha_iso
        nombre = self._nombre_completo_socio(socio)
        tit = QLabel(f"{nombre.upper()} — {fecha_txt}")
        tit.setStyleSheet(f"font-size:24px; font-weight:900; color:{self.c_boton};")
        l.addWidget(tit)
        sub = QLabel(f"RUTINA REALIZADA — DÍA {dia_rutina}")
        sub.setStyleSheet("font-size:16px; color:#aaa; font-weight:900; letter-spacing:1px;")
        l.addWidget(sub)

        if ejercicios:
            tabla = self._crear_tabla_sesion_historica(ejercicios)
            l.addWidget(tabla, 1)
        else:
            vacio = QLabel(f"No hay ejercicios guardados para el Día {dia_rutina} en esta sesión.")
            vacio.setStyleSheet("font-size:15px; color:#aaa; padding:20px;")
            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(vacio, 1)

        btn_cerrar = QPushButton("CERRAR")
        btn_cerrar.setProperty("class", "accion")
        btn_cerrar.clicked.connect(dlg.accept)
        l.addWidget(btn_cerrar)
        dlg.exec()

    def abrir_calendario_asistencias(self, socio):
        """Mes actual + dos anteriores, con acceso al detalle completo de cada sesión."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Asistencias últimos 3 meses - {self._nombre_completo_socio(socio)}")
        dlg.setMinimumSize(720, 610)
        dlg.setStyleSheet("background:#1a1a1a; color:white; font-family:'Urbanist','Segoe UI';")
        l = QVBoxLayout(dlg)
        l.setContentsMargins(26, 24, 26, 24)
        l.setSpacing(14)

        tit = QLabel("ASISTENCIAS ULT. 3 MESES")
        tit.setStyleSheet(f"font-size:24px; font-weight:900; color:{self.c_boton};")
        l.addWidget(tit)
        ayuda = QLabel(
            "Los días verdes tienen una asistencia registrada. Podés ver el mes actual y los dos anteriores. "
            "Hacé clic sobre un día verde para abrir la rutina exacta y los ejercicios realizados."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color:#aaa; font-size:14px;")
        l.addWidget(ayuda)

        cal = QCalendarWidget()
        cal.setGridVisible(True)
        cal.setNavigationBarVisible(True)
        hoy = QDate.currentDate()
        dos_meses_atras = hoy.addMonths(-2)
        minimo = QDate(dos_meses_atras.year(), dos_meses_atras.month(), 1)
        maximo = QDate(hoy.year(), hoy.month(), hoy.daysInMonth())
        cal.setMinimumDate(minimo)
        cal.setMaximumDate(maximo)
        cal.setSelectedDate(hoy)
        cal.setStyleSheet(f"""
            QCalendarWidget {{ background:#111; color:white; border:1px solid #333; border-radius:12px; }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{ background:#111; min-height:42px; }}
            QCalendarWidget QToolButton {{ color:white; background:#242424; border-radius:7px; padding:7px 12px; font-weight:800; }}
            QCalendarWidget QToolButton:hover {{ background:white; color:black; border:1px solid {HERENCIA_MORADO}; }}
            QCalendarWidget QSpinBox {{ color:white; background:#242424; padding:5px; min-width:70px; }}
            QCalendarWidget QAbstractItemView:enabled {{ color:white; background:#111; selection-background-color:{HERENCIA_MORADO}; selection-color:white; }}
        """)
        l.addWidget(cal, 1)

        estado = {"fechas": set(), "formateadas": set()}
        dni = str(socio.get('dni', '') or '')

        def cargar_mes(anio, mes):
            for fecha_anterior in list(estado["formateadas"]):
                try:
                    y, m, d = map(int, fecha_anterior.split('-'))
                    cal.setDateTextFormat(QDate(y, m, d), QTextCharFormat())
                except Exception:
                    pass
            estado["formateadas"].clear()
            estado["fechas"] = self._fechas_asistencia_mes(dni, anio, mes)
            for fecha_iso in estado["fechas"]:
                try:
                    y, m, d = map(int, fecha_iso.split('-'))
                    q = QDate(y, m, d)
                except Exception:
                    continue
                if q < minimo or q > maximo:
                    continue
                formato = QTextCharFormat()
                formato.setBackground(QBrush(QColor('#10b981')))
                formato.setForeground(QBrush(QColor('white')))
                formato.setFontWeight(QFont.Weight.Bold.value)
                cal.setDateTextFormat(q, formato)
                estado["formateadas"].add(fecha_iso)

        def fecha_elegida(qdate):
            fecha_iso = qdate.toString("yyyy-MM-dd")
            if fecha_iso in estado["fechas"]:
                self._mostrar_sesion_historica(socio, fecha_iso, dlg)

        cal.currentPageChanged.connect(cargar_mes)
        cal.clicked.connect(fecha_elegida)
        cargar_mes(cal.yearShown(), cal.monthShown())

        btn = QPushButton("CERRAR")
        btn.setProperty("class", "accion")
        btn.clicked.connect(dlg.accept)
        l.addWidget(btn)
        dlg.exec()

    def abrir_asistencias_ultimo_anio(self, socio):
        """Vista anual estática: calendarios fijos, sin semanas ni detalle de rutinas."""
        inicio, fin = self._rango_anual_socio(socio)
        dni = str(socio.get('dni', '') or '')
        fechas = self._fechas_asistencia_rango(
            dni,
            inicio.toString('yyyy-MM-dd'),
            fin.toString('yyyy-MM-dd')
        )

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Asistencias último año - {self._nombre_completo_socio(socio)}")
        dlg.setMinimumSize(1120, 800)
        dlg.resize(1240, 900)
        dlg.setStyleSheet("background:#1a1a1a; color:white; font-family:'Urbanist','Segoe UI';")
        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(9)

        tit = QLabel("ASISTENCIAS ULT. AÑO")
        tit.setStyleSheet(f"font-size:24px; font-weight:900; color:{self.c_boton};")
        outer.addWidget(tit)
        rango = QLabel(
            f"Año de socio: {inicio.toString('dd/MM/yyyy')} → {fin.toString('dd/MM/yyyy')}  •  "
            f"{len(fechas)} asistencias registradas"
        )
        rango.setStyleSheet("color:#aaa; font-size:14px; font-weight:700;")
        outer.addWidget(rango)
        nota = QLabel("Vista fija de asistencias. Los días verdes indican que el socio asistió.")
        nota.setStyleSheet("color:#888; font-size:13px;")
        outer.addWidget(nota)

        # Calendarios dibujados como paneles estáticos. No son QCalendarWidget, por lo
        # tanto no responden a la rueda, clics ni teclado y tampoco muestran número de semana.
        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(9)

        fechas_set = set(fechas)
        nombres_dia = ["lu.", "ma.", "mi.", "ju.", "vi.", "sá.", "do."]

        def crear_mes_estatico(anio, mes):
            card = QFrame()
            card.setMinimumHeight(160)
            card.setStyleSheet("QFrame { background:#111; border:1px solid #2d2d2d; border-radius:10px; }")
            vl = QVBoxLayout(card)
            vl.setContentsMargins(7, 6, 7, 7)
            vl.setSpacing(4)

            titulo_mes = QLabel(f"{self._nombre_mes_numero(mes).upper()} {anio}")
            titulo_mes.setAlignment(Qt.AlignmentFlag.AlignCenter)
            titulo_mes.setStyleSheet(f"color:{self.c_boton}; font-size:14px; font-weight:900; border:none;")
            vl.addWidget(titulo_mes)

            cal_grid = QGridLayout()
            cal_grid.setContentsMargins(0, 0, 0, 0)
            cal_grid.setHorizontalSpacing(2)
            cal_grid.setVerticalSpacing(2)

            for col, nombre_dia in enumerate(nombres_dia):
                h = QLabel(nombre_dia)
                h.setAlignment(Qt.AlignmentFlag.AlignCenter)
                color = "#ef4444" if col >= 5 else "#cfcfcf"
                h.setStyleSheet(f"color:{color}; font-size:11px; font-weight:800; border:none; background:transparent;")
                cal_grid.addWidget(h, 0, col)

            cal_mes = calendar.Calendar(firstweekday=0)  # lunes
            semanas = cal_mes.monthdayscalendar(anio, mes)
            for fila, semana in enumerate(semanas, start=1):
                for col, dia in enumerate(semana):
                    celda = QLabel("" if dia == 0 else str(dia))
                    celda.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    celda.setFixedHeight(16)
                    if dia == 0:
                        celda.setStyleSheet("border:none; background:transparent;")
                    else:
                        fecha_iso = f"{anio:04d}-{mes:02d}-{dia:02d}"
                        if fecha_iso in fechas_set:
                            celda.setStyleSheet(
                                "background:#10b981; color:white; font-size:11px; font-weight:900; "
                                "border:1px solid #34d399; border-radius:4px;"
                            )
                        else:
                            color = "#ef4444" if col == 6 else "white"
                            celda.setStyleSheet(
                                f"background:transparent; color:{color}; font-size:11px; "
                                "border:1px solid transparent;"
                            )
                    cal_grid.addWidget(celda, fila, col)

            # Reservamos seis filas de semanas para que todos los meses midan exactamente igual.
            for fila in range(len(semanas) + 1, 7):
                for col in range(7):
                    relleno = QLabel("")
                    relleno.setFixedHeight(16)
                    relleno.setStyleSheet("border:none; background:transparent;")
                    cal_grid.addWidget(relleno, fila, col)

            vl.addLayout(cal_grid)
            return card

        cursor = QDate(inicio.year(), inicio.month(), 1)
        ultimo_mes = QDate(fin.year(), fin.month(), 1)
        meses = []
        while cursor <= ultimo_mes:
            meses.append((cursor.year(), cursor.month()))
            cursor = cursor.addMonths(1)

        # Hasta 12/13 meses caben sin scroll usando 4 columnas.
        for indice, (anio, mes) in enumerate(meses):
            grid.addWidget(crear_mes_estatico(anio, mes), indice // 4, indice % 4)

        for col in range(4):
            grid.setColumnStretch(col, 1)
        outer.addLayout(grid, 1)

        btn = QPushButton("CERRAR")
        btn.setProperty("class", "accion")
        btn.clicked.connect(dlg.accept)
        outer.addWidget(btn)
        dlg.exec()

    def _subir_archivo_storage(self, ruta, contenido):
        bucket = self.supabase.storage.from_(HISTORIAL_BUCKET)
        opciones = {"content-type": "application/gzip", "upsert": "true"}
        try:
            return bucket.upload(path=ruta, file=contenido, file_options=opciones)
        except TypeError:
            return bucket.upload(ruta, contenido, opciones)
        except Exception:
            # Algunas versiones del SDK no respetan upsert en upload; update reemplaza el objeto.
            try:
                return bucket.update(path=ruta, file=contenido, file_options={"content-type": "application/gzip"})
            except TypeError:
                return bucket.update(ruta, contenido, {"content-type": "application/gzip"})

    def _archivar_mes_socio(self, dni, anio, mes):
        inicio = QDate(anio, mes, 1)
        fin = QDate(anio, mes, inicio.daysInMonth())
        inicio_iso = inicio.toString('yyyy-MM-dd')
        fin_iso = fin.toString('yyyy-MM-dd')
        try:
            res = (self.supabase.table('sesiones_entrenamiento')
                   .select('*')
                   .eq('dni', str(dni))
                   .gte('fecha', inicio_iso)
                   .lte('fecha', fin_iso)
                   .order('fecha')
                   .execute())
            sesiones = res.data or []
            if not sesiones:
                return True

            periodo = f"{anio:04d}-{mes:02d}"
            payload = {
                'version': 1,
                'dni': str(dni),
                'periodo': periodo,
                'fecha_desde': inicio_iso,
                'fecha_hasta': fin_iso,
                'sesiones': sesiones,
            }
            json_bytes = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            comprimido = gzip.compress(json_bytes, compresslevel=9)
            checksum = hashlib.sha256(comprimido).hexdigest()
            dni_seguro = re.sub(r'[^0-9A-Za-z_-]', '_', str(dni))
            ruta = f"historiales/{dni_seguro}/{periodo}.json.gz"

            self._subir_archivo_storage(ruta, comprimido)

            # Verificación obligatoria antes de borrar PostgreSQL.
            descargado = bytes(self.supabase.storage.from_(HISTORIAL_BUCKET).download(ruta))
            if hashlib.sha256(descargado).hexdigest() != checksum:
                raise RuntimeError("La copia subida a Storage no pasó la verificación SHA-256.")
            verificado = json.loads(gzip.decompress(descargado).decode('utf-8'))
            if len(verificado.get('sesiones', [])) != len(sesiones):
                raise RuntimeError("La copia histórica no contiene todas las sesiones esperadas.")

            self.supabase.table('historial_archivos').upsert({
                'dni': str(dni),
                'periodo': periodo,
                'fecha_desde': inicio_iso,
                'fecha_hasta': fin_iso,
                'storage_path': ruta,
                'cantidad_sesiones': len(sesiones),
                'sha256': checksum,
                'tamano_bytes': len(comprimido),
                'verificado': True,
                'actualizado_en': datetime.now().isoformat(),
            }, on_conflict='dni,periodo').execute()

            # Recién después de subir + descargar + verificar se limpian los detalles pesados.
            (self.supabase.table('sesiones_entrenamiento')
             .delete()
             .eq('dni', str(dni))
             .gte('fecha', inicio_iso)
             .lte('fecha', fin_iso)
             .execute())
            return True
        except Exception as e:
            print(f"[Historial] No se pudo archivar {dni} {anio:04d}-{mes:02d}: {e}")
            return False

    def _dnis_con_sesiones_mes(self, anio, mes):
        inicio = QDate(anio, mes, 1)
        fin = QDate(anio, mes, inicio.daysInMonth())
        dnis = set()
        desde = 0
        paso = 1000
        while True:
            try:
                res = (self.supabase.table('sesiones_entrenamiento')
                       .select('dni')
                       .gte('fecha', inicio.toString('yyyy-MM-dd'))
                       .lte('fecha', fin.toString('yyyy-MM-dd'))
                       .order('dni')
                       .range(desde, desde + paso - 1)
                       .execute())
                filas = res.data or []
            except Exception:
                return dnis
            for fila in filas:
                dni = str(fila.get('dni', '') or '')
                if dni:
                    dnis.add(dni)
            if len(filas) < paso:
                break
            desde += paso
        return dnis

    def _ultima_ejecucion_mantenimiento(self):
        try:
            res = (self.supabase.table('mantenimiento_historial')
                   .select('ultima_ejecucion')
                   .eq('id', 1)
                   .limit(1)
                   .execute())
            if res.data:
                txt = str(res.data[0].get('ultima_ejecucion', '') or '')
                if txt:
                    return datetime.fromisoformat(txt.replace('Z', '+00:00')).date()
        except Exception:
            pass
        return None

    def ejecutar_mantenimiento_historial(self, forzar=False):
        """Cada ~30 días mueve a Storage meses completos con más de 2 años."""
        try:
            ultima = self._ultima_ejecucion_mantenimiento()
            hoy_py = datetime.now().date()
            if not forzar and ultima is not None and (hoy_py - ultima).days < HISTORIAL_MANTENIMIENTO_DIAS:
                return

            # Primer mes que todavía exista en la tabla detallada.
            primera = (self.supabase.table('sesiones_entrenamiento')
                       .select('fecha')
                       .order('fecha')
                       .limit(1)
                       .execute())
            if not primera.data:
                self.supabase.table('mantenimiento_historial').upsert({
                    'id': 1, 'ultima_ejecucion': datetime.now().isoformat()
                }, on_conflict='id').execute()
                return

            q_primera = QDate.fromString(str(primera.data[0].get('fecha', ''))[:10], 'yyyy-MM-dd')
            if not q_primera.isValid():
                return
            cursor = QDate(q_primera.year(), q_primera.month(), 1)
            corte = QDate.currentDate().addYears(-HISTORIAL_RETENCION_ANIOS)

            while cursor.isValid():
                fin_mes = QDate(cursor.year(), cursor.month(), cursor.daysInMonth())
                if fin_mes > corte:
                    break
                dnis = self._dnis_con_sesiones_mes(cursor.year(), cursor.month())
                for dni in sorted(dnis):
                    self._archivar_mes_socio(dni, cursor.year(), cursor.month())
                cursor = cursor.addMonths(1)

            self.supabase.table('mantenimiento_historial').upsert({
                'id': 1,
                'ultima_ejecucion': datetime.now().isoformat(),
            }, on_conflict='id').execute()
        except Exception as e:
            # El programa puede seguir funcionando aunque todavía no se haya ejecutado el SQL nuevo.
            print(f"[Historial] Mantenimiento omitido: {e}")

    def _calcular_edad(self, fecha_nacimiento):
        if not fecha_nacimiento:
            return None
        try:
            dt = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
            hoy = datetime.now().date()
            edad = hoy.year - dt.year - ((hoy.month, hoy.day) < (dt.month, dt.day))
            return edad
        except (ValueError, TypeError):
            return None

    # === MENÚ ===
    def crear_menu(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(55, 35, 55, 35)
        l.setSpacing(22)

        tit = QLabel("PANEL DE CONTROL")
        tit.setStyleSheet(f"font-size: 46px; font-weight: 900; color: {self.c_boton}; letter-spacing: 2px;")
        l.addWidget(tit, alignment=Qt.AlignmentFlag.AlignCenter)

        sub = QLabel("Accesos organizados por tarea")
        sub.setStyleSheet("font-size: 16px; color: #aaa; font-weight: 600;")
        l.addWidget(sub, alignment=Qt.AlignmentFlag.AlignCenter)
        l.addSpacing(10)

        def aplicar_efecto_card(widget, es_primario=True):
            sh = QGraphicsDropShadowEffect()
            sh.setBlurRadius(35 if es_primario else 20)
            sh.setOffset(0, 5 if es_primario else 3)
            color_resplandor = QColor(self.c_boton)
            color_resplandor.setAlpha(180 if es_primario else 120)
            sh.setColor(color_resplandor)
            widget.setGraphicsEffect(sh)

        def crear_boton(texto, accion, primario=False, notificacion=False):
            btn = BotonConNotificacion(texto) if notificacion else QPushButton(texto)
            btn.setProperty("class", "hd_menu")
            btn.setMinimumHeight(68 if primario else 58)
            btn.setStyleSheet(f"border-radius: {'18' if primario else '14'}px;")
            aplicar_efecto_card(btn, primario)
            btn.clicked.connect(accion)
            return btn

        def crear_grupo(titulo, botones):
            grupo = QFrame()
            grupo.setObjectName("grupoMenu")
            grupo.setStyleSheet("QFrame#grupoMenu { background: #111; border: 1px solid #2a2a2a; border-radius: 18px; }")
            gl = QVBoxLayout(grupo)
            gl.setContentsMargins(18, 16, 18, 18)
            gl.setSpacing(12)
            lbl = QLabel(titulo)
            lbl.setStyleSheet(f"background: transparent; border: none; color: {self.c_boton}; font-size: 24px; font-weight: 900;")
            gl.addWidget(lbl)
            for btn in botones:
                gl.addWidget(btn)
            gl.addStretch()
            return grupo

        b_reg = crear_boton("REGISTRAR NUEVO SOCIO", lambda: self.pantallas.setCurrentIndex(2), True)
        b_ren = crear_boton("RENOVAR MEMBRESIA", lambda: self.pantallas.setCurrentIndex(3), True)
        b_soc = crear_boton("LISTA DE CLIENTES", lambda: [self.pantallas.setCurrentIndex(4), self.cargar_tabla()], True)
        self.btn_recordatorios = crear_boton("RECORDATORIO DE VENCIMIENTO", lambda: [self.pantallas.setCurrentIndex(11), self.cargar_recordatorios()], True, True)

        self.btn_pedidos = crear_boton("PEDIDOS ONLINE", lambda: [self.pantallas.setCurrentIndex(1), self.cargar_tabla_pedidos()], False, True)
        self.btn_inscripciones = crear_boton("INSCRIPCIONES WEB", lambda: [self.pantallas.setCurrentIndex(9), self.cargar_tabla_inscripciones()], False, True)
        b_ven = crear_boton("REGISTRO DE VENTAS", lambda: [self.pantallas.setCurrentIndex(7), self.cargar_ventas()])
        b_stk = crear_boton("STOCK DE PRODUCTOS", lambda: [self.pantallas.setCurrentIndex(8), self.cargar_stock()])

        b_pre = crear_boton("PRECIOS DE PLANES", lambda: [self.pantallas.setCurrentIndex(5), self.cargar_precios()])
        b_dis = crear_boton("TEMAS", lambda: [self.pantallas.setCurrentIndex(6), self.cargar_diseno()])

        grid = QGridLayout()
        grid.setSpacing(18)
        grid.addWidget(crear_grupo("SOCIOS", [b_reg, b_ren, b_soc, self.btn_recordatorios]), 0, 0)
        grid.addWidget(crear_grupo("VENTAS Y STOCK", [self.btn_pedidos, self.btn_inscripciones, b_ven, b_stk]), 0, 1)
        grid.addWidget(crear_grupo("CONFIGURACIÓN", [b_pre, b_dis]), 0, 2)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 1)
        l.addLayout(grid)
        l.addStretch()

        return w

    def refrescar_datos(self, idx):
        if idx == 4: self.cargar_tabla()
        if idx == 5: self.cargar_precios()
        if idx == 6: self.cargar_diseno()
        if idx == 7: self.cargar_ventas()
        if idx == 8: self.cargar_stock()
        if idx == 9: self.cargar_tabla_inscripciones()
        if idx == 11: self.cargar_recordatorios()

    # === 0. PEDIDOS WEB ===
    def chequear_pedidos_nube(self):
        try:
            res = self.supabase.table('pedidos').select('id', count='exact').eq('estado', 'Pendiente').execute()
            c = res.count if res.count else 0
            self.btn_pedidos.set_notification(c)
        except: pass
        try:
            res = self.supabase.table('inscripciones').select('id', count='exact').eq('estado', 'Pendiente').execute()
            c = res.count if res.count else 0
            if hasattr(self, "btn_inscripciones"):
                self.btn_inscripciones.set_notification(c)
        except: pass
        self.chequear_recordatorios_vencimiento()

    def crear_pedidos(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(40,40,40,40); l.addLayout(self.cabecera("PEDIDOS ONLINE"))
        
        self.tabla_p = QTableWidget(0, 6)
        self.tabla_p.setHorizontalHeaderLabels(["CLIENTE", "PRODUCTO", "TOTAL", "TELÉFONO", "FECHA DE LA ORDEN", "ACCIÓN"])
        self.tabla_p.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_p.verticalHeader().setMinimumWidth(44); self.tabla_p.verticalHeader().setDefaultSectionSize(42)
        self.tabla_p.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_p.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        l.addWidget(self.tabla_p)
        
        hl = QHBoxLayout()
        btn_act = QPushButton("🔄 ACTUALIZAR LISTA"); btn_act.setProperty("class", "accion")
        btn_act.clicked.connect(self.cargar_tabla_pedidos)
        btn_ent = QPushButton("✅ MARCAR COMO ENTREGADO"); btn_ent.setStyleSheet("background: #10b981; color: white; padding: 15px; font-weight: bold; border-radius: 10px;")
        btn_ent.clicked.connect(self.marcar_entregado)
        hl.addWidget(btn_act); hl.addStretch(); hl.addWidget(btn_ent)
        l.addLayout(hl)
        return w

    def _formatear_precio_pedido(self, total):
        try:
            valor = float(total or 0)
            if valor.is_integer():
                return "$" + f"{valor:,.0f}".replace(",", ".")
            entero, decimales = f"{valor:,.2f}".split(".")
            return "$" + entero.replace(",", ".") + "," + decimales
        except (TypeError, ValueError):
            return f"${total}"

    def _fecha_orden_pedido(self, pedido):
        # Acepta los nombres de fecha más habituales para no romper pedidos ya existentes.
        raw = (pedido.get('fecha_orden') or pedido.get('creado_en') or
               pedido.get('created_at') or pedido.get('fecha_pedido') or pedido.get('fecha'))
        if not raw:
            return "—"
        texto = str(raw).strip()
        try:
            dt = datetime.fromisoformat(texto.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            return dt.strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            pass
        try:
            return datetime.strptime(texto[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return texto

    def cargar_tabla_pedidos(self):
        self.tabla_p.setRowCount(0)
        self.ids_pedidos = []
        self.pedidos_data = []
        try:
            res = self.supabase.table('pedidos').select('*').eq('estado', 'Pendiente').execute()
            self.pedidos_data = res.data or []
            for r, p in enumerate(self.pedidos_data):
                self.tabla_p.insertRow(r)
                self.ids_pedidos.append(p['id'])
                self.tabla_p.setItem(r, 0, QTableWidgetItem(str(p.get('cliente_nombre', ''))))
                self.tabla_p.setItem(r, 1, QTableWidgetItem(str(p.get('producto', ''))))
                self.tabla_p.setItem(r, 2, QTableWidgetItem(self._formatear_precio_pedido(p.get('total', 0))))
                self.tabla_p.setItem(r, 3, QTableWidgetItem(str(p.get('cliente_telefono', ''))))
                self.tabla_p.setItem(r, 4, QTableWidgetItem(self._fecha_orden_pedido(p)))
                
                btn_wa = QPushButton("📲 AVISAR POR WA")
                btn_wa.setStyleSheet("background: #25D366; color: white; font-weight: bold; border-radius: 5px;")
                btn_wa.clicked.connect(
                    lambda checked=False, tel=p.get('cliente_telefono', ''), prod=p.get('producto', ''), total=p.get('total', 0):
                    self.enviar_wa(tel, prod, total)
                )
                self.tabla_p.setCellWidget(r, 5, btn_wa)
            self.btn_pedidos.set_notification(len(self.pedidos_data))
        except Exception:
            pass

    def enviar_wa(self, tel, prod, total):
        total_txt = self._formatear_precio_pedido(total)
        msg = (
            f"Hola! Soy de La Herencia Gym. Ya tengo separado tu pedido de {prod}. "
            f"El total de la orden es {total_txt}. "
            "Avisame a qué hora pasás a retirarlo por el mostrador!"
        )
        url = f"https://wa.me/{tel}?text={quote(msg)}"
        webbrowser.open(url)

    def marcar_entregado(self):
        f = self.tabla_p.currentRow()
        if f < 0:
            QMessageBox.warning(self, "Atención", "Seleccioná un pedido de la lista primero.")
            return
        pid = self.ids_pedidos[f]
        # Datos limpios del pedido (para guardarlo en el registro de ventas)
        p = self.pedidos_data[f] if f < len(self.pedidos_data) else {}
        cliente = p.get('cliente_nombre', '')
        producto = p.get('producto', '')
        try:
            total = float(p.get('total', 0) or 0)
        except:
            total = 0
        try:
            # 1. Queda guardado para siempre en el registro de ventas
            self.supabase.table('ventas').insert({
                "cliente_nombre": cliente,
                "producto": producto,
                "total": total,
                "fecha": QDate.currentDate().toString("yyyy-MM-dd")
            }).execute()
            # 2. Se descuenta del stock
            aviso_stock = self.descontar_stock_pedido(producto)
            # 3. Se marca el pedido como entregado
            self.supabase.table('pedidos').update({'estado': 'Entregado'}).eq('id', pid).execute()
            self.cargar_tabla_pedidos()
            mensaje = "Pedido entregado, venta guardada y stock actualizado."
            if aviso_stock:
                mensaje += f"\n\nAtencion:\n{aviso_stock}"
            QMessageBox.information(self, "OK", mensaje)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def parsear_productos_pedido(self, texto):
        items = []
        for parte in str(texto or "").split(","):
            parte = parte.strip()
            if not parte:
                continue
            m = re.match(r"^(\d+)\s*x\s+(.+)$", parte, re.IGNORECASE)
            if m:
                items.append((m.group(2).strip(), int(m.group(1))))
            else:
                items.append((parte, 1))
        return items

    def descontar_stock_pedido(self, texto_pedido):
        avisos = []
        for nombre, cantidad_vendida in self.parsear_productos_pedido(texto_pedido):
            res = self.supabase.table('productos').select('id,nombre,cantidad').eq('nombre', nombre).execute()
            if not res.data:
                avisos.append(f"- No encontre '{nombre}' en stock.")
                continue

            producto = res.data[0]
            actual = int(producto.get('cantidad', 0) or 0)
            nueva = max(0, actual - cantidad_vendida)
            self.supabase.table('productos').update({"cantidad": nueva}).eq('id', producto['id']).execute()

            if nueva < 10:
                avisos.append(f"- {producto.get('nombre', nombre)} quedo con pocas unidades: {nueva}.")
        return "\n".join(avisos)

    # === INSCRIPCIONES WEB ===
    def crear_inscripciones(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(40,40,40,40); l.addLayout(self.cabecera("INSCRIPCIONES WEB"))

        self.tabla_i = QTableWidget(0, 6)
        self.tabla_i.setHorizontalHeaderLabels(["DNI", "NOMBRE Y APELLIDO", "PLAN", "TELEFONO", "FECHA", "ID"])
        self.tabla_i.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_i.verticalHeader().setMinimumWidth(44); self.tabla_i.verticalHeader().setDefaultSectionSize(42)
        self.tabla_i.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_i.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_i.setColumnHidden(5, True)
        l.addWidget(self.tabla_i)

        h = QHBoxLayout()
        btn_act = QPushButton("ACTUALIZAR"); btn_act.setProperty("class", "accion")
        btn_act.clicked.connect(self.cargar_tabla_inscripciones)
        btn_ok = QPushButton("ACEPTAR CLIENTE"); btn_ok.setStyleSheet("background:#10b981; color:white; font-weight:bold; padding:14px; border-radius:10px;")
        btn_ok.clicked.connect(self.aceptar_inscripcion)
        btn_no = QPushButton("RECHAZAR"); btn_no.setStyleSheet("background:#d13636; color:white; font-weight:bold; padding:14px; border-radius:10px;")
        btn_no.clicked.connect(self.rechazar_inscripcion)
        h.addWidget(btn_act); h.addStretch(); h.addWidget(btn_ok); h.addWidget(btn_no)
        l.addLayout(h)
        return w

    def cargar_tabla_inscripciones(self):
        self.tabla_i.setRowCount(0)
        self.inscripciones_data = []
        try:
            res = self.supabase.table('inscripciones').select('*').eq('estado', 'Pendiente').order('id').execute()
            self.inscripciones_data = res.data
            for r, i in enumerate(res.data):
                self.tabla_i.insertRow(r)
                self.tabla_i.setItem(r, 0, QTableWidgetItem(str(i.get('dni', ''))))
                self.tabla_i.setItem(r, 1, QTableWidgetItem(str(i.get('nombre_apellido', ''))))
                self.tabla_i.setItem(r, 2, QTableWidgetItem(f"{i.get('plan', '-')} ({i.get('dias', '-')} dias)"))
                self.tabla_i.setItem(r, 3, QTableWidgetItem(str(i.get('telefono', ''))))
                self.tabla_i.setItem(r, 4, QTableWidgetItem(str(i.get('creado_en', '-'))[:10]))
                self.tabla_i.setItem(r, 5, QTableWidgetItem(str(i.get('id', ''))))
            if hasattr(self, "btn_inscripciones"):
                self.btn_inscripciones.set_notification(len(res.data))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _inscripcion_seleccionada(self):
        f = self.tabla_i.currentRow()
        if f < 0:
            QMessageBox.warning(self, "Atención", "Seleccioná una inscripción de la lista.")
            return None
        return self.inscripciones_data[f] if f < len(self.inscripciones_data) else None

    def obtener_precio_plan(self, plan, dias, transferencia=False):
        try:
            plan_key, dias_key = self._clave_precio_db(plan, dias, transferencia)
            rp = self.supabase.table('precios').select('precio').eq('plan', plan_key).eq('dias', int(dias_key)).execute()
            if rp.data:
                return float(rp.data[0].get('precio', 0) or 0)
        except Exception:
            pass
        return 0

    def enviar_whatsapp_inscripcion(self, telefono, nombre, plan, dias, precio, vencimiento):
        tel = re.sub(r"\D", "", str(telefono or ""))
        if not tel:
            return
        precio_txt = f"${precio:,.0f}".replace(",", ".") if precio else "a confirmar"
        msg = (
            f"Hola {nombre}! Tu inscripción en La Herencia Gym fue aceptada. "
            f"Plan: {plan} ({dias} días por semana). "
            f"Precio: {precio_txt}. "
            f"Vencimiento: {vencimiento}. "
            "Te esperamos para arrancar con todo!"
        )
        webbrowser.open(f"https://wa.me/{tel}?text={msg.replace(' ', '%20')}")

    def aceptar_inscripcion(self):
        i = self._inscripcion_seleccionada()
        if not i: return
        dni = str(i.get('dni', '')).strip()
        nombre = str(i.get('nombre_apellido', '')).strip()
        plan = i.get('plan', 'Mensual')
        dias = int(i.get('dias', 3) or 3)
        vencimiento_qdate = QDate.currentDate().addDays(30)
        vencimiento = vencimiento_qdate.toString("yyyy-MM-dd")
        vencimiento_msg = vencimiento_qdate.toString("dd/MM/yyyy")
        precio = self.obtener_precio_plan(plan, dias)
        if not dni or not nombre:
            QMessageBox.warning(self, "Atención", "La inscripción no tiene DNI o nombre.")
            return
        try:
            existe = self.supabase.table('socios').select('dni').eq('dni', dni).execute()
            if existe.data:
                QMessageBox.warning(self, "Atención", "Ese DNI ya está registrado como socio.")
                return
            self.supabase.table('socios').insert({
                "dni": dni,
                "nombre": nombre,
                "plan": plan,
                "dias": dias,
                "vencimiento": vencimiento,
                "fecha_ingreso": QDate.currentDate().toString("yyyy-MM-dd"),
            }).execute()
            self.supabase.table('inscripciones').update({'estado': 'Aceptada'}).eq('id', i['id']).execute()
            self.cargar_tabla_inscripciones()
            self.enviar_whatsapp_inscripcion(i.get('telefono', ''), nombre, plan, dias, precio, vencimiento_msg)
            QMessageBox.information(self, "OK", "Cliente aceptado y registrado como socio.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def rechazar_inscripcion(self):
        i = self._inscripcion_seleccionada()
        if not i: return
        if QMessageBox.question(self, "Rechazar", "¿Rechazar esta inscripción?") == QMessageBox.StandardButton.Yes:
            try:
                self.supabase.table('inscripciones').update({'estado': 'Rechazada'}).eq('id', i['id']).execute()
                self.cargar_tabla_inscripciones()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ==========================================
    # === 1. REGISTRAR (Con bloqueo de DNI duplicado) ===
    # ==========================================
    def crear_registro(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(60, 40, 60, 40)

        hdr = QHBoxLayout()
        col_btns = QVBoxLayout()
        col_btns.setSpacing(8)
        btn_volver = QPushButton("⬅ VOLVER")
        btn_volver.setProperty("class", "accion")
        btn_volver.setFixedSize(150, 45)
        btn_volver.clicked.connect(lambda: [self.limpiar_form_registro(), self.pantallas.setCurrentIndex(0)])
        btn_limpiar = QPushButton("LIMPIAR")
        btn_limpiar.setProperty("class", "accion")
        btn_limpiar.setFixedSize(150, 45)
        btn_limpiar.clicked.connect(self.limpiar_form_registro)
        col_btns.addWidget(btn_volver)
        col_btns.addWidget(btn_limpiar)
        hdr.addLayout(col_btns)
        hdr.addSpacing(20)
        lbl_tit = QLabel("REGISTRO DE SOCIO")
        lbl_tit.setStyleSheet(f"font-size: 30px; font-weight: bold; color: {self.c_boton};")
        hdr.addWidget(lbl_tit)
        hdr.addStretch()
        outer.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollBar:vertical { background: #222; width: 8px; border-radius: 4px; } QScrollBar::handle:vertical { background: #555; border-radius: 4px; }")

        inner_w = QWidget()
        f = QFormLayout(inner_w)
        f.setVerticalSpacing(20); f.setContentsMargins(0, 20, 20, 20)

        self.r_dni = QLineEdit(); self.r_dni.setValidator(QIntValidator(0, 999999999, self)); self.r_dni.setMaxLength(9)
        self.r_nom = QLineEdit(); self.r_nom.setPlaceholderText("Nombre(s)")
        self.r_apellido = QLineEdit(); self.r_apellido.setPlaceholderText("Apellido(s)")
        self.r_telefono = QLineEdit(); self.r_telefono.setPlaceholderText("Ej: 5491112345678")
        self.r_email = QLineEdit(); self.r_email.setPlaceholderText("correo@ejemplo.com")
        self.r_nacimiento = DateEditSinRueda(); self.r_nacimiento.setCalendarPopup(True)
        self._configurar_fecha_nacimiento(self.r_nacimiento)
        self.r_plan = QComboBox(); self.r_plan.addItems(PLANES_DISPONIBLES)
        self.r_dias = QComboBox(); self.r_dias.addItems(["2", "3", "4", "5", "6"])
        self.r_horas = QSpinBox(); self.r_horas.setRange(1, 20); self.r_horas.setValue(1); self.r_horas.setSuffix(" hora(s)/sem")
        self.r_venc = DateEditSinRueda(); self.r_venc.setCalendarPopup(True)
        self.r_venc.setDate(QDate.currentDate().addDays(31))
        self.r_plan.currentIndexChanged.connect(self._actualizar_opciones_plan_registro)
        self.r_plan.currentIndexChanged.connect(lambda _: self.r_venc.setDate(QDate.currentDate().addDays(31)))
        self.r_salud_data = ""

        self.lbl_r_dias = QLabel("Días por semana:")
        self.lbl_r_horas = QLabel("Horas de asistencia:")
        self.r_plan_extra = QWidget()
        extra_l = QVBoxLayout(self.r_plan_extra)
        extra_l.setContentsMargins(0, 0, 0, 0)
        extra_l.setSpacing(8)
        extra_l.addWidget(self.lbl_r_dias)
        extra_l.addWidget(self.r_dias)
        extra_l.addWidget(self.lbl_r_horas)
        extra_l.addWidget(self.r_horas)

        btn_salud = QPushButton("📋 COMPLETAR PLANILLA DE SALUD")
        btn_salud.setStyleSheet("background: #1a3a5a; color: white; padding: 12px; border-radius: 10px; font-weight: bold;")
        btn_salud.clicked.connect(self.abrir_planilla_salud)
        self.lbl_salud_estado = QLabel("Sin completar")
        self.lbl_salud_estado.setStyleSheet("color: #888; font-size: 13px;")

        btn = QPushButton("💾 GUARDAR SOCIO EN NUBE"); btn.setProperty("class", "accion"); btn.clicked.connect(self.guardar_socio)

        f.addRow("DNI:", self.r_dni)
        f.addRow("Nombre:", self.r_nom)
        f.addRow("Apellido:", self.r_apellido)
        f.addRow("Teléfono:", self.r_telefono)
        f.addRow("Email:", self.r_email)
        f.addRow("Fecha de nacimiento:", self.r_nacimiento)
        f.addRow("Plan:", self.r_plan)
        f.addRow("", self.r_plan_extra)
        f.addRow("Vencimiento:", self.r_venc)
        f.addRow("Salud:", btn_salud)
        f.addRow("", self.lbl_salud_estado)
        f.addRow("", btn)

        self._actualizar_opciones_plan_registro()

        scroll.setWidget(inner_w)
        outer.addWidget(scroll)
        return w

    def _actualizar_opciones_plan_registro(self):
        plan = self.r_plan.currentText()
        semi = plan == PLAN_SEMIPERSONALIZADO
        pers = plan == PLAN_PERSONALIZADO
        self.lbl_r_dias.setVisible(semi)
        self.r_dias.setVisible(semi)
        self.lbl_r_horas.setVisible(pers)
        self.r_horas.setVisible(pers)
        self.r_plan_extra.setVisible(semi or pers)

    def limpiar_form_registro(self):
        self.r_dni.clear()
        self.r_nom.clear()
        self.r_apellido.clear()
        self.r_telefono.clear()
        self.r_email.clear()
        self.r_plan.setCurrentIndex(0)
        self.r_dias.setCurrentIndex(0)
        self.r_horas.setValue(1)
        self.r_nacimiento.setDate(QDate(2000, 1, 1))
        self.r_venc.setDate(QDate.currentDate().addDays(31))
        self.r_salud_data = ""
        self.lbl_salud_estado.setText("Sin completar")
        self.lbl_salud_estado.setStyleSheet("color: #888; font-size: 13px;")
        self._actualizar_opciones_plan_registro()

    def _valor_plan_registro(self):
        plan = self.r_plan.currentText()
        if plan == PLAN_SEMIPERSONALIZADO:
            return plan, int(self.r_dias.currentText())
        if plan == PLAN_PERSONALIZADO:
            return plan, int(self.r_horas.value())
        return plan, 0

    def abrir_planilla_salud(self):
        dlg = DialogPlanillaSalud(self.r_salud_data, self)
        if dlg.exec():
            self.r_salud_data = dlg.get_datos()
            self.lbl_salud_estado.setText("✅ Planilla completada")
            self.lbl_salud_estado.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")

    def guardar_socio(self):
        dni = self.r_dni.text().strip()
        nombre = self.r_nom.text().strip()
        if not dni or not nombre: return

        # 1. Chequeo de DNI Duplicado
        try:
            chequeo = self.supabase.table('socios').select('dni').eq('dni', dni).execute()
            if chequeo.data:
                QMessageBox.warning(self, "Atención", "Ese DNI ya está registrado en el sistema.")
                return
        except Exception as e:
            QMessageBox.critical(self, "Error de red", str(e))
            return

        # 2. Guardado
        try:
            plan, dias_val = self._valor_plan_registro()
            self.supabase.table('socios').insert({
                "dni": dni,
                "nombre": nombre,
                "apellido": self.r_apellido.text().strip(),
                "telefono": self.r_telefono.text().strip(),
                "email": self.r_email.text().strip(),
                "fecha_nacimiento": self.r_nacimiento.date().toString("yyyy-MM-dd"),
                "salud_info": self.r_salud_data,
                "plan": plan,
                "dias": dias_val,
                "vencimiento": self.r_venc.date().toString("yyyy-MM-dd"),
                "fecha_ingreso": QDate.currentDate().toString("yyyy-MM-dd"),
            }).execute()
            QMessageBox.information(self, "OK", "Socio guardado correctamente.")
            self.limpiar_form_registro()
            self.chequear_recordatorios_vencimiento()
        except Exception as e: QMessageBox.critical(self, "Error", str(e))


    # ==========================================
    # === 2. RENOVAR (Dinámico con costo) ===
    # ==========================================
    def crear_renovar(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(60,60,60,60); l.addLayout(self.cabecera("CARGA DE PAGO"))
        
        # A) Buscador
        h_busc = QHBoxLayout()
        self.rn_dni = QLineEdit(); self.rn_dni.setPlaceholderText("DNI del socio que va a pagar"); self.rn_dni.setValidator(QIntValidator(0, 999999999, self)); self.rn_dni.setMaxLength(9)
        btn_buscar = QPushButton("🔍 BUSCAR SOCIO"); btn_buscar.setProperty("class", "accion")
        btn_buscar.clicked.connect(self.buscar_para_renovar)
        h_busc.addWidget(self.rn_dni); h_busc.addWidget(btn_buscar)
        l.addLayout(h_busc)
        l.addSpacing(20)
        
        # B) Tarjeta de Información (Oculta al inicio)
        self.f_info = QFrame()
        self.f_info.setStyleSheet("background: #1a1a1a; border-radius: 15px; border: 1px solid #333;")
        f_info_l = QVBoxLayout(self.f_info); f_info_l.setSpacing(10); f_info_l.setContentsMargins(30,30,30,30)
        
        self.lbl_rn_nombre = QLabel("Nombre: -")
        self.lbl_rn_apellido = QLabel("Apellido: -")
        self.lbl_rn_dni = QLabel("DNI: -")
        self.lbl_rn_plan = QLabel("Plan actual: -")
        self.lbl_rn_precio = QLabel("A COBRAR: $0")
        self.lbl_rn_precio.setStyleSheet("font-size: 32px; font-weight: 900; color: #10b981; margin-top: 10px;")
        for lbl in (self.lbl_rn_nombre, self.lbl_rn_apellido, self.lbl_rn_dni, self.lbl_rn_plan):
            lbl.setStyleSheet("font-size: 18px; color: #ddd;")
        self.lbl_rn_nombre.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {self.c_boton};")
        
        f_info_l.addWidget(self.lbl_rn_nombre)
        f_info_l.addWidget(self.lbl_rn_apellido)
        f_info_l.addWidget(self.lbl_rn_dni)
        f_info_l.addWidget(self.lbl_rn_plan)
        f_info_l.addWidget(self.lbl_rn_precio)
        l.addWidget(self.f_info)
        self.f_info.setVisible(False)
        self.rn_socio_actual = None
        
        # C) Formulario de Pago (Oculto al inicio)
        self.w_pago = QWidget()
        f_pago = QFormLayout(self.w_pago); f_pago.setVerticalSpacing(25); f_pago.setContentsMargins(0,30,0,0)
        
        self.rn_venc = DateEditSinRueda(); self.rn_venc.setCalendarPopup(True)
        self.rn_pago_transferencia = QCheckBox("El socio paga con transferencia")
        self.rn_pago_transferencia.stateChanged.connect(self._actualizar_precio_renovacion)
        btn_conf = QPushButton("✅ CONFIRMAR PAGO RECIBIDO"); btn_conf.setProperty("class", "accion")
        btn_conf.clicked.connect(self.renovar_socio)
        
        f_pago.addRow("Extender hasta el:", self.rn_venc)
        f_pago.addRow("Forma de pago:", self.rn_pago_transferencia)
        f_pago.addRow("", btn_conf)
        l.addWidget(self.w_pago)
        self.w_pago.setVisible(False)
        
        l.addStretch(); return w

    def _actualizar_precio_renovacion(self):
        if not self.rn_socio_actual:
            return
        s = self.rn_socio_actual
        transferencia = self.rn_pago_transferencia.isChecked()
        precio = self.obtener_precio_plan(s.get('plan', ''), s.get('dias', 0), transferencia)
        metodo = "TRANSFERENCIA" if transferencia else "EFECTIVO"
        if precio:
            self.lbl_rn_precio.setText(f"A COBRAR ({metodo}): {self._formatear_precio(precio)}")
        else:
            self.lbl_rn_precio.setText(f"A COBRAR ({metodo}): Indefinido (revisar Precios de Planes)")

    def buscar_para_renovar(self):
        dni = self.rn_dni.text().strip()
        if not dni: return
        try:
            res = self.supabase.table('socios').select('*').eq('dni', dni).execute()
            if not res.data:
                QMessageBox.warning(self, "Error", "El socio no existe en la base de datos.")
                self.f_info.setVisible(False); self.w_pago.setVisible(False)
                self.rn_socio_actual = None
                return
                
            s = res.data[0]
            self.rn_socio_actual = s
            self.lbl_rn_nombre.setText(f"Nombre: {s.get('nombre', '-').upper()}")
            self.lbl_rn_apellido.setText(f"Apellido: {s.get('apellido', '-').upper()}")
            self.lbl_rn_dni.setText(f"DNI: {s.get('dni', '-')}")
            self.lbl_rn_plan.setText(f"Plan: {self._texto_plan_socio(s)}")
            self.rn_pago_transferencia.setChecked(False)
            self._actualizar_precio_renovacion()
            self.rn_venc.setDate(QDate.currentDate().addMonths(1))
            self.f_info.setVisible(True)
            self.w_pago.setVisible(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def renovar_socio(self):
        dni = self.rn_dni.text().strip()
        try:
            res = self.supabase.table('socios').update({"vencimiento": self.rn_venc.date().toString("yyyy-MM-dd")}).eq('dni', dni).execute()
            if res.data: 
                QMessageBox.information(self, "Éxito", "Pago registrado. Membresía renovada.")
                self.rn_dni.clear()
                self.rn_socio_actual = None
                self.f_info.setVisible(False)
                self.w_pago.setVisible(False)
                self.chequear_recordatorios_vencimiento()
            else: 
                QMessageBox.warning(self, "Error", "Hubo un problema actualizando al socio.")
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    # === RECORDATORIOS DE VENCIMIENTO ===
    def crear_recordatorios(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(40, 40, 40, 40)
        l.addLayout(self.cabecera("RECORDATORIO DE VENCIMIENTO"))

        aviso = QLabel("Socios que vencen exactamente dentro de 2 días.")
        aviso.setStyleSheet("color: #aaa; font-size: 15px; font-weight: 600;")
        l.addWidget(aviso)

        self.tabla_recordatorios = QTableWidget(0, 7)
        self.tabla_recordatorios.setHorizontalHeaderLabels(["DNI", "NOMBRE", "TELEFONO", "PLAN", "VENCIMIENTO", "DEBE", "WHATSAPP"])
        self.tabla_recordatorios.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_recordatorios.verticalHeader().setMinimumWidth(44)
        self.tabla_recordatorios.verticalHeader().setDefaultSectionSize(46)
        self.tabla_recordatorios.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_recordatorios.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        l.addWidget(self.tabla_recordatorios)

        h = QHBoxLayout()
        btn_act = QPushButton("ACTUALIZAR")
        btn_act.setProperty("class", "accion")
        btn_act.clicked.connect(self.cargar_recordatorios)
        h.addWidget(btn_act)
        h.addStretch()
        l.addLayout(h)
        return w

    def _socios_por_vencer_en_dias(self, dias_objetivo):
        res = self.supabase.table('socios').select('*').order('vencimiento').execute()
        socios = []
        hoy = datetime.now().date()
        for s in res.data:
            try:
                dias = (datetime.strptime(s.get('vencimiento', ''), "%Y-%m-%d").date() - hoy).days
            except:
                continue
            if dias == dias_objetivo:
                socios.append(s)
        return socios

    def _socios_por_vencer_en_dos_dias(self):
        return self._socios_por_vencer_en_dias(2)

    def _nombre_completo_socio(self, socio):
        nombre = str(socio.get('nombre', '') or '').strip()
        apellido = str(socio.get('apellido', '') or '').strip()
        return f"{nombre} {apellido}".strip() or "Socio"

    def _precio_recordatorio(self, socio):
        precio = self.obtener_precio_plan(socio.get('plan', ''), socio.get('dias', 0), transferencia=False)
        return precio, self._formatear_precio(precio)

    def _formatear_precio(self, precio):
        return f"${precio:,.0f}".replace(",", ".") if precio else "a confirmar"

    def chequear_recordatorios_vencimiento(self):
        if not hasattr(self, "btn_recordatorios"):
            return
        try:
            self.btn_recordatorios.set_notification(len(self._socios_por_vencer_en_dos_dias()))
        except:
            self.btn_recordatorios.set_notification(0)

    def cargar_recordatorios(self):
        if not hasattr(self, "tabla_recordatorios"):
            return
        self.tabla_recordatorios.setRowCount(0)
        self.recordatorios_data = []
        try:
            self.recordatorios_data = self._socios_por_vencer_en_dos_dias()
            for r, s in enumerate(self.recordatorios_data):
                precio, precio_txt = self._precio_recordatorio(s)
                nombre = self._nombre_completo_socio(s)
                plan = self._texto_plan_socio(s)

                self.tabla_recordatorios.insertRow(r)
                self.tabla_recordatorios.setItem(r, 0, QTableWidgetItem(str(s.get('dni', ''))))
                self.tabla_recordatorios.setItem(r, 1, QTableWidgetItem(nombre))
                self.tabla_recordatorios.setItem(r, 2, QTableWidgetItem(str(s.get('telefono', ''))))
                self.tabla_recordatorios.setItem(r, 3, QTableWidgetItem(plan))
                self.tabla_recordatorios.setItem(r, 4, QTableWidgetItem(str(s.get('vencimiento', ''))))
                self.tabla_recordatorios.setItem(r, 5, QTableWidgetItem(precio_txt))

                btn_wa = QPushButton("MANDAR MENSAJE")
                btn_wa.setStyleSheet("background: #25D366; color: white; font-weight: bold; border-radius: 6px; padding: 6px;")
                btn_wa.clicked.connect(lambda checked, socio=s, deuda=precio_txt: self.enviar_recordatorio_whatsapp(socio, deuda))
                self.tabla_recordatorios.setCellWidget(r, 6, btn_wa)

            if hasattr(self, "btn_recordatorios"):
                self.btn_recordatorios.set_notification(len(self.recordatorios_data))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def enviar_recordatorio_whatsapp(self, socio, deuda_txt):
        telefono = re.sub(r"\D", "", str(socio.get('telefono', '') or ''))
        if not telefono:
            QMessageBox.warning(self, "Sin telefono", "Este socio no tiene telefono cargado.")
            return

        nombre = self._nombre_completo_socio(socio)
        try:
            venc = datetime.strptime(socio.get('vencimiento', ''), "%Y-%m-%d").strftime("%d/%m/%Y")
        except:
            venc = str(socio.get('vencimiento', ''))

        msg = (
            f"Hola {nombre}! Te recordamos que tu cuota de La Herencia Gym esta a punto de vencer. "
            f"Vence el {venc}. "
            f"El monto a abonar es {deuda_txt}. "
            f"Alias para transferir: {ALIAS_NEGOCIO}. "
            "Cuando realices el pago, envianos el comprobante por este medio. Muchas gracias!"
        )
        webbrowser.open(f"https://wa.me/{telefono}?text={quote(msg)}")

    def _archivo_estado_telegram(self):
        base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        estado_dir = os.path.join(base_dir, "LaHerenciaGym")
        os.makedirs(estado_dir, exist_ok=True)
        return os.path.join(estado_dir, "telegram_recordatorio_estado.json")

    def _leer_ultimo_envio_telegram(self):
        try:
            with open(self._archivo_estado_telegram(), "r", encoding="utf-8") as f:
                return json.load(f).get("ultimo_envio", "")
        except:
            return ""

    def _guardar_ultimo_envio_telegram(self, fecha):
        try:
            with open(self._archivo_estado_telegram(), "w", encoding="utf-8") as f:
                json.dump({"ultimo_envio": fecha}, f)
        except:
            pass

    def enviar_notificacion_telegram(self, mensaje):
        token = str(TELEGRAM_BOT_TOKEN or "").strip()
        chat_id = str(TELEGRAM_CHAT_ID or "").strip()
        if not token or not chat_id:
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={quote(chat_id)}&text={quote(mensaje)}"
        with urlopen(url, timeout=15) as resp:
            return resp.status == 200

    def construir_mensaje_telegram_vencimientos(self, socios):
        dias = TELEGRAM_DIAS_ANTES_VENCIMIENTO
        titulo_dias = "mañana" if dias == 1 else f"en {dias} días"
        lineas = [f"La Herencia Gym - socios por vencer {titulo_dias}", ""]
        for i, s in enumerate(socios, 1):
            nombre = self._nombre_completo_socio(s)
            _, deuda = self._precio_recordatorio(s)
            telefono = str(s.get('telefono', '') or 'Sin telefono')
            try:
                venc = datetime.strptime(s.get('vencimiento', ''), "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                venc = str(s.get('vencimiento', ''))
            lineas.append(f"{i}. {nombre} - vence {venc} - debe {deuda} - tel: {telefono}")
        return "\n".join(lineas)

    def chequear_envio_diario_telegram(self):
        ahora = datetime.now()
        hoy = ahora.strftime("%Y-%m-%d")
        if self._leer_ultimo_envio_telegram() == hoy:
            return
        if ahora.strftime("%H:%M") < TELEGRAM_HORA_RECORDATORIO:
            return
        try:
            socios = self._socios_por_vencer_en_dias(TELEGRAM_DIAS_ANTES_VENCIMIENTO)
            if not socios:
                return
            mensaje = self.construir_mensaje_telegram_vencimientos(socios)
            if self.enviar_notificacion_telegram(mensaje):
                self._guardar_ultimo_envio_telegram(hoy)
        except:
            pass

    # === 3. SOCIOS ===
    def crear_socios(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(40,40,40,40); l.addLayout(self.cabecera("ADMINISTRAR SOCIOS"))
        self.busqueda_socios = QLineEdit()
        self.busqueda_socios.setPlaceholderText("Buscar socio por DNI o nombre...")
        self.busqueda_socios.textChanged.connect(self.filtrar_socios)
        l.addWidget(self.busqueda_socios)
        hl = QHBoxLayout(); b_del = QPushButton("🗑 DAR DE BAJA"); b_del.setStyleSheet("background:#d13636; color: white; padding:12px; font-weight:bold; border-radius:8px;")
        b_del.clicked.connect(self.borrar_socio); hl.addStretch(); hl.addWidget(b_del); l.addLayout(hl)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(["DNI", "NOMBRE", "PLAN", "VENCIMIENTO", "ESTADO", "DETALLE"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.verticalHeader().setMinimumWidth(44); self.tabla.verticalHeader().setDefaultSectionSize(42)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.itemDoubleClicked.connect(lambda item: self.mostrar_info_socio(self.tabla.item(item.row(), 0).text()))
        l.addWidget(self.tabla); return w

    def cargar_tabla(self):
        self.tabla.setRowCount(0)
        self.socios_data = []
        try:
            res = self.supabase.table('socios').select('*').order('vencimiento').execute()
            self.socios_data = res.data
            for r, s in enumerate(res.data):
                self.tabla.insertRow(r)
                d = (datetime.strptime(s['vencimiento'], "%Y-%m-%d").date() - datetime.now().date()).days
                col = QColor("#10b981") if d >= 0 else QColor("#ef4444")
                self.tabla.setItem(r, 0, QTableWidgetItem(s['dni']))
                nombre_completo = s['nombre']
                if s.get('apellido'):
                    nombre_completo += f" {s['apellido']}"
                self.tabla.setItem(r, 1, QTableWidgetItem(nombre_completo))
                plan = self._texto_plan_socio(s)
                self.tabla.setItem(r, 2, QTableWidgetItem(plan))
                self.tabla.setItem(r, 3, QTableWidgetItem(s['vencimiento']))
                i = QTableWidgetItem("ACTIVO" if d >= 0 else "VENCIDO"); i.setForeground(QBrush(col)); i.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                self.tabla.setItem(r, 4, i)
                btn_info = QPushButton("🔍 MÁS INFO")
                btn_info.setStyleSheet("background: #1a3a5a; color: white; font-weight: bold; border-radius: 6px; padding: 6px;")
                btn_info.clicked.connect(lambda checked, dni=s['dni']: self.mostrar_info_socio(dni))
                self.tabla.setCellWidget(r, 5, btn_info)
        except: pass
        self.filtrar_socios()

    def filtrar_socios(self):
        if not hasattr(self, "tabla") or not hasattr(self, "busqueda_socios"):
            return
        texto = self.busqueda_socios.text().strip().lower()
        for r in range(self.tabla.rowCount()):
            dni = self.tabla.item(r, 0).text().lower() if self.tabla.item(r, 0) else ""
            nombre = self.tabla.item(r, 1).text().lower() if self.tabla.item(r, 1) else ""
            self.tabla.setRowHidden(r, bool(texto) and texto not in dni and texto not in nombre)

    def borrar_socio(self):
        f = self.tabla.currentRow()
        if f >= 0 and QMessageBox.question(self, "Borrar", "¿Eliminar socio?") == QMessageBox.StandardButton.Yes:
            self.supabase.table('socios').delete().eq('dni', self.tabla.item(f, 0).text()).execute(); self.cargar_tabla()

    def mostrar_info_socio(self, dni):
        try:
            res = self.supabase.table('socios').select('*').eq('dni', dni).execute()
            if not res.data:
                QMessageBox.warning(self, "Error", "No se encontró el socio."); return
            s = res.data[0]
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Ficha del Socio — {s['nombre']}")
        dlg.setMinimumWidth(580)
        dlg.setStyleSheet("background: #1a1a1a; color: white; font-family: 'Urbanist', 'Segoe UI';")

        scroll = QScrollArea(dlg)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollBar:vertical { background: #222; width: 8px; border-radius: 4px; } QScrollBar::handle:vertical { background: #555; border-radius: 4px; }")

        inner = QWidget()
        l = QVBoxLayout(inner)
        l.setContentsMargins(30, 25, 30, 25); l.setSpacing(0)

        def sec(txt):
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"font-size: 12px; font-weight: 900; color: {self.c_boton}; letter-spacing: 2px; margin-top: 18px; margin-bottom: 4px; background: transparent;")
            return lbl

        def campo(etiqueta, valor):
            w = QWidget(); w.setStyleSheet("background: #111; border-radius: 8px; margin: 2px 0;")
            h = QHBoxLayout(w); h.setContentsMargins(14, 10, 14, 10)
            le = QLabel(etiqueta); le.setStyleSheet("color: #888; font-size: 13px; min-width: 170px; background: transparent;")
            lv = QLabel(str(valor or "—")); lv.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
            lv.setWordWrap(True)
            h.addWidget(le); h.addWidget(lv, 1)
            return w

        nombre_completo = s['nombre']
        if s.get('apellido'):
            nombre_completo += f" {s['apellido']}"
        d = (datetime.strptime(s['vencimiento'], "%Y-%m-%d").date() - datetime.now().date()).days
        estado = "ACTIVO" if d >= 0 else "VENCIDO"
        color_estado = "#10b981" if d >= 0 else "#ef4444"

        tit_n = QLabel(nombre_completo.upper())
        tit_n.setStyleSheet(f"font-size: 22px; font-weight: 900; color: {self.c_boton}; background: transparent;")
        lbl_est = QLabel(f"● {estado}")
        lbl_est.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color_estado}; background: transparent;")
        h_top = QHBoxLayout()
        h_top.addWidget(tit_n); h_top.addStretch(); h_top.addWidget(lbl_est)
        l.addLayout(h_top); l.addSpacing(8)

        l.addWidget(sec("DATOS PERSONALES"))
        l.addWidget(campo("DNI:", s.get('dni', '')))
        l.addWidget(campo("Teléfono:", s.get('telefono', '')))
        l.addWidget(campo("Email:", s.get('email', '')))
        nacimiento = s.get('fecha_nacimiento', '') or ''
        if nacimiento and not nacimiento.startswith('2000-01-01') and not nacimiento.startswith('1900'):
            try:
                dt = datetime.strptime(nacimiento, "%Y-%m-%d")
                edad = (datetime.now().date() - dt.date()).days // 365
                nacimiento = f"{dt.strftime('%d/%m/%Y')}  ({edad} años)"
            except: pass
        l.addWidget(campo("Fecha de nacimiento:", nacimiento))

        l.addWidget(sec("MEMBRESÍA"))
        l.addWidget(campo("Plan:", self._texto_plan_socio(s)))
        l.addWidget(campo("Vencimiento:", s.get('vencimiento', '')))
        dias_txt = f"Vence en {d} días" if d >= 0 else f"Venció hace {abs(d)} días"
        l.addWidget(campo("Estado:", dias_txt))

        l.addWidget(sec("PLANILLA DE SALUD"))
        salud_raw = s.get('salud_info', '') or ''
        if salud_raw:
            partes = salud_raw.split("|")
            condiciones, obs_txt = [], ""
            for p in partes:
                if p.startswith("OBS:"):
                    obs_txt = p[4:]
                elif p in PREGUNTAS_SALUD:
                    condiciones.append(PREGUNTAS_SALUD[p])
            if condiciones:
                for cond in condiciones:
                    l.addWidget(campo("⚠", cond))
            else:
                l.addWidget(campo("Condiciones:", "Sin condiciones declaradas"))
            if obs_txt:
                l.addWidget(campo("Observaciones:", obs_txt))
        else:
            l.addWidget(campo("Estado:", "Planilla no completada"))

        l.addSpacing(18)
        btn_cerrar = QPushButton("CERRAR")
        btn_cerrar.setStyleSheet(f"background: {self.c_boton}; color: black; font-weight: bold; padding: 14px; border-radius: 10px;")
        btn_cerrar.clicked.connect(dlg.accept)
        l.addWidget(btn_cerrar)

        scroll.setWidget(inner)
        outer_l = QVBoxLayout(dlg); outer_l.setContentsMargins(0, 0, 0, 0)
        outer_l.addWidget(scroll)
        dlg.resize(600, 700)
        dlg.exec()

    # === FICHA DE SOCIO EN PANTALLA ===
    def crear_ficha_socio(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(40, 40, 40, 40)
        h = QHBoxLayout()
        btn = QPushButton("VOLVER")
        btn.setProperty("class", "accion")
        btn.setFixedSize(150, 45)
        btn.clicked.connect(lambda: [self.pantallas.setCurrentIndex(4), self.cargar_tabla()])
        self.lbl_ficha_titulo = QLabel("FICHA DEL SOCIO")
        self.lbl_ficha_titulo.setStyleSheet(f"font-size: 30px; font-weight: bold; color: {self.c_boton};")
        h.addWidget(btn); h.addSpacing(20); h.addWidget(self.lbl_ficha_titulo); h.addStretch()
        l.addLayout(h)
        self.scroll_ficha_socio = QScrollArea()
        self.scroll_ficha_socio.setWidgetResizable(True)
        self.scroll_ficha_socio.setStyleSheet("QScrollArea { border: none; } QScrollBar:vertical { background: #222; width: 8px; border-radius: 4px; } QScrollBar::handle:vertical { background: #555; border-radius: 4px; }")
        l.addWidget(self.scroll_ficha_socio)
        return w

    def _limpiar_ficha_socio(self):
        old = self.scroll_ficha_socio.widget()
        if old:
            old.deleteLater()
        inner = QWidget()
        self.ficha_layout = QVBoxLayout(inner)
        self.ficha_layout.setContentsMargins(30, 25, 30, 25)
        self.ficha_layout.setSpacing(0)
        self.scroll_ficha_socio.setWidget(inner)
        return self.ficha_layout

    def _sec_ficha(self, txt):
        lbl = QLabel(txt)
        lbl.setStyleSheet(f"font-size: 12px; font-weight: 900; color: {self.c_boton}; letter-spacing: 2px; margin-top: 18px; margin-bottom: 4px; background: transparent;")
        return lbl

    def _campo_ficha(self, etiqueta, valor):
        w = QWidget(); w.setStyleSheet("background: #111; border-radius: 8px; margin: 2px 0;")
        h = QHBoxLayout(w); h.setContentsMargins(14, 10, 14, 10)
        le = QLabel(etiqueta); le.setStyleSheet("color: #888; font-size: 13px; min-width: 170px; background: transparent;")
        lv = QLabel(str(valor or "-")); lv.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
        lv.setWordWrap(True)
        h.addWidget(le); h.addWidget(lv, 1)
        return w

    def _dias_rutina_socio(self, socio):
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

    def _cargar_rutina_supabase(self, dni):
        try:
            res = self.supabase.table('rutinas_socios').select('rutina').eq('dni', str(dni)).execute()
            if res.data:
                rutina = res.data[0].get('rutina', {})
                return rutina if isinstance(rutina, dict) else {}
        except:
            pass
        return {}

    def _guardar_rutina_supabase(self, dni, rutina):
        try:
            self.supabase.table('rutinas_socios').upsert({
                "dni": str(dni),
                "rutina": rutina,
                "actualizado_en": datetime.now().isoformat()
            }).execute()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la rutina en Supabase.\n\nRevisa que exista la tabla rutinas_socios.\n\nDetalle: {e}")
            return False

    def _rutina_socio(self, socio):
        rutina = self._cargar_rutina_supabase(socio.get('dni', ''))
        dias = self._dias_rutina_socio(socio)
        if not isinstance(rutina, dict):
            rutina = {}
        for dia in range(1, dias + 1):
            rutina.setdefault(f"Dia {dia}", [])
        return {f"Dia {dia}": rutina.get(f"Dia {dia}", []) for dia in range(1, dias + 1)}

    def _crear_tabla_rutina(self, ejercicios, editable=False):
        tabla = QTableWidget(0, 4)
        tabla.setHorizontalHeaderLabels(["Ejercicio", "Series", "Repeticiones", "Elemento"])
        tabla.setShowGrid(True)
        tabla.setGridStyle(Qt.PenStyle.SolidLine)
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        tabla.setColumnWidth(1, 130); tabla.setColumnWidth(2, 170)
        tabla.verticalHeader().setMinimumWidth(44); tabla.verticalHeader().setDefaultSectionSize(68)
        tabla.setWordWrap(True)
        tabla.setStyleSheet(f"""
            QTableWidget {{ background: #111; color: white; gridline-color: #000; border: 1px solid #000; font-size: 15px; }}
            QTableWidget::item {{ padding: 12px; border-right: 1px solid #000; border-bottom: 1px solid #000; }}
            QTableWidget::item:selected {{ background: #1a3a5a; color: white; }}
            QHeaderView::section {{ background: {HERENCIA_MORADO}; color: white; font-weight: 900; font-size: 14px; padding: 12px 10px; border: 1px solid #000; }}
            QTableWidget QLineEdit {{ background: #111; color: white; border: 2px solid {HERENCIA_MORADO}; border-radius: 8px; padding: 4px 8px; margin: 4px; min-height: 34px; font-size: 15px; }}
        """)
        if not editable:
            tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for r, ej in enumerate(ejercicios or []):
            tabla.insertRow(r); tabla.setRowHeight(r, 68)
            tabla.setItem(r, 0, QTableWidgetItem(str(ej.get("ejercicio", ""))))
            tabla.setItem(r, 1, QTableWidgetItem(str(ej.get("series", ""))))
            tabla.setItem(r, 2, QTableWidgetItem(str(ej.get("repeticiones", ""))))
            tabla.setItem(r, 3, QTableWidgetItem(str(ej.get("elemento", ""))))
        return tabla

    def _rutina_desde_tabla(self, tabla):
        ejercicios = []
        for r in range(tabla.rowCount()):
            ejercicio = tabla.item(r, 0).text().strip() if tabla.item(r, 0) else ""
            series = tabla.item(r, 1).text().strip() if tabla.item(r, 1) else ""
            repeticiones = tabla.item(r, 2).text().strip() if tabla.item(r, 2) else ""
            elemento = tabla.item(r, 3).text().strip() if tabla.item(r, 3) else ""
            if ejercicio or series or repeticiones or elemento:
                ejercicios.append({"ejercicio": ejercicio, "series": series, "repeticiones": repeticiones, "elemento": elemento})
        return ejercicios

    def abrir_editor_rutina(self, socio):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Modificar rutina - {self._nombre_completo_socio(socio)}")
        dlg.setMinimumSize(920, 650)
        dlg.setStyleSheet("background: #1a1a1a; color: white; font-family: 'Urbanist', 'Segoe UI';")
        l = QVBoxLayout(dlg); l.setContentsMargins(24, 22, 24, 22)
        titulo = QLabel("RUTINA DEL SOCIO")
        titulo.setStyleSheet(f"font-size: 22px; font-weight: 900; color: {self.c_boton};")
        l.addWidget(titulo)
        tabs = TabWidgetSinRueda()
        tabs.setStyleSheet(self._estilo_tabs_rutina())
        tablas = {}
        for dia, ejercicios in self._rutina_socio(socio).items():
            pag = QWidget(); pl = QVBoxLayout(pag)
            tabla = self._crear_tabla_rutina(ejercicios, editable=True)
            tablas[dia] = tabla; pl.addWidget(tabla)
            h = QHBoxLayout()
            btn_add = QPushButton("AGREGAR EJERCICIO"); btn_add.setProperty("class", "accion")
            btn_add.clicked.connect(lambda checked, t=tabla: [t.insertRow(t.rowCount()), t.setRowHeight(t.rowCount() - 1, 68)])
            btn_del = QPushButton("BORRAR FILA")
            btn_del.setStyleSheet(f"background:{HERENCIA_MORADO}; color:white; font-weight:bold; padding:12px; border-radius:8px;")
            btn_del.clicked.connect(lambda checked, t=tabla: t.removeRow(t.currentRow()) if t.currentRow() >= 0 else None)
            h.addWidget(btn_add); h.addWidget(btn_del); h.addStretch(); pl.addLayout(h)
            tabs.addTab(pag, dia)
        l.addWidget(tabs)
        h_btn = QHBoxLayout()
        btn_cancel = QPushButton("CANCELAR")
        btn_cancel.setStyleSheet("background:#333; color:white; font-weight:bold; padding:14px; border-radius:10px;")
        btn_cancel.clicked.connect(dlg.reject)
        btn_save = QPushButton("GUARDAR RUTINA"); btn_save.setProperty("class", "accion")
        h_btn.addWidget(btn_cancel); h_btn.addStretch(); h_btn.addWidget(btn_save); l.addLayout(h_btn)

        def guardar():
            rutina = {dia: self._rutina_desde_tabla(tabla) for dia, tabla in tablas.items()}
            if self._guardar_rutina_supabase(socio.get('dni', ''), rutina):
                QMessageBox.information(self, "OK", "Rutina guardada correctamente.")
                dlg.accept(); self.mostrar_info_socio(socio.get('dni', ''))

        btn_save.clicked.connect(guardar)
        dlg.exec()

    def mostrar_info_socio(self, dni):
        try:
            res = self.supabase.table('socios').select('*').eq('dni', dni).execute()
            if not res.data:
                QMessageBox.warning(self, "Error", "No se encontro el socio."); return
            s = res.data[0]
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return

        l = self._limpiar_ficha_socio()
        nombre_completo = self._nombre_completo_socio(s)
        self.lbl_ficha_titulo.setText(f"FICHA DEL SOCIO - {nombre_completo.upper()}")
        try:
            d = (datetime.strptime(s['vencimiento'], "%Y-%m-%d").date() - datetime.now().date()).days
        except:
            d = 0
        estado = "ACTIVO" if d >= 0 else "VENCIDO"
        color_estado = "#10b981" if d >= 0 else "#ef4444"
        h_top = QHBoxLayout()
        tit_n = QLabel(nombre_completo.upper())
        tit_n.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {self.c_boton}; background: transparent;")
        lbl_est = QLabel(f"* {estado}")
        lbl_est.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color_estado}; background: transparent;")
        h_top.addWidget(tit_n); h_top.addStretch(); h_top.addWidget(lbl_est); l.addLayout(h_top)

        l.addWidget(self._sec_ficha("DATOS PERSONALES"))
        l.addWidget(self._campo_ficha("DNI:", s.get('dni', '')))
        l.addWidget(self._campo_ficha("Teléfono:", s.get('telefono', '')))
        l.addWidget(self._campo_ficha("Email:", s.get('email', '')))
        nacimiento = s.get('fecha_nacimiento', '') or ''
        if nacimiento and not nacimiento.startswith('2000-01-01') and not nacimiento.startswith('1900'):
            try:
                dt = datetime.strptime(nacimiento, "%Y-%m-%d")
                edad = self._calcular_edad(nacimiento)
                nacimiento = f"{dt.strftime('%d/%m/%Y')} ({edad} años)" if edad is not None else dt.strftime('%d/%m/%Y')
            except Exception:
                pass
        l.addWidget(self._campo_ficha("Fecha de nacimiento:", nacimiento))

        l.addWidget(self._sec_ficha("MEMBRESÍA"))
        l.addWidget(self._campo_ficha("Plan:", self._texto_plan_socio(s)))
        l.addWidget(self._campo_ficha("Vencimiento:", s.get('vencimiento', '')))
        dias_txt = f"Vence en {d} días" if d >= 0 else f"Venció hace {abs(d)} días"
        l.addWidget(self._campo_ficha("Estado:", dias_txt))
        l.addWidget(self._campo_ficha("Asistencias esta semana:", self._texto_asistencias(s)))
        l.addWidget(self._campo_ficha(
            f"Asistencias de {self._nombre_mes_actual()}:",
            self._texto_asistencias_mes(s)
        ))
        h_asistencias = QHBoxLayout()
        btn_ver_asistencias = QPushButton("ASISTENCIAS ULT. 3 MESES")
        btn_ver_asistencias.setStyleSheet(
            f"background:{self.c_boton}; color:white; font-weight:900; padding:10px 14px; "
            "border-radius:9px;"
        )
        btn_ver_asistencias.clicked.connect(lambda checked=False, socio=s: self.abrir_calendario_asistencias(socio))
        btn_anio = QPushButton("ASISTENCIAS ULT. AÑO")
        btn_anio.setStyleSheet(
            "background:#242424; color:white; font-weight:900; padding:10px 14px; "
            f"border-radius:9px; border:2px solid {self.c_boton};"
        )
        btn_anio.clicked.connect(lambda checked=False, socio=s: self.abrir_asistencias_ultimo_anio(socio))
        h_asistencias.addWidget(btn_ver_asistencias)
        h_asistencias.addWidget(btn_anio)
        h_asistencias.addStretch()
        l.addLayout(h_asistencias)

        l.addWidget(self._sec_ficha("PLANILLA DE SALUD"))
        salud_raw = s.get('salud_info', '') or ''
        if salud_raw:
            partes = salud_raw.split("|"); condiciones, obs_txt = [], ""
            for p in partes:
                if p.startswith("OBS:"):
                    obs_txt = p[4:]
                elif p in PREGUNTAS_SALUD:
                    condiciones.append(PREGUNTAS_SALUD[p])
            if condiciones:
                for cond in condiciones:
                    l.addWidget(self._campo_ficha("Alerta:", cond))
            else:
                l.addWidget(self._campo_ficha("Condiciones:", "Sin condiciones declaradas"))
            if obs_txt:
                l.addWidget(self._campo_ficha("Observaciones:", obs_txt))
        else:
            l.addWidget(self._campo_ficha("Estado:", "Planilla no completada"))

        l.addWidget(self._sec_ficha("RUTINA"))
        tabs_rutina = TabWidgetSinRueda()
        tabs_rutina.setStyleSheet(self._estilo_tabs_rutina())
        for dia, ejercicios in self._rutina_socio(s).items():
            pag = QWidget(); pl = QVBoxLayout(pag)
            tabla_r = self._crear_tabla_rutina(ejercicios, editable=False)
            tabla_r.setMinimumHeight(230)
            pl.addWidget(tabla_r)
            tabs_rutina.addTab(pag, dia)
        l.addWidget(tabs_rutina)
        btn_rutina = QPushButton("MODIFICAR RUTINA")
        btn_rutina.setProperty("class", "accion")
        btn_rutina.clicked.connect(lambda: self.abrir_editor_rutina(s))
        l.addWidget(btn_rutina)
        l.addStretch()
        self.pantallas.setCurrentIndex(12)

    # === 4. PRECIOS DE PLANES (FIJOS) ===
    def crear_precios(self):
        outer = QWidget()
        outer_l = QVBoxLayout(outer)
        outer_l.setContentsMargins(0, 0, 0, 0); outer_l.setSpacing(0)

        hdr_w = QWidget(); hdr_l = QHBoxLayout(hdr_w)
        hdr_l.setContentsMargins(40, 30, 40, 10)
        hdr_l.addLayout(self.cabecera("PRECIOS DE PLANES"))
        outer_l.addWidget(hdr_w)

        self._scroll_precios = QScrollArea()
        self._scroll_precios.setWidgetResizable(True)
        self._scroll_precios.setStyleSheet("QScrollArea { border:none; } QScrollBar:vertical { background:#1a1a1a; width:8px; border-radius:4px; } QScrollBar::handle:vertical { background:#444; border-radius:4px; }")
        outer_l.addWidget(self._scroll_precios)

        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(40, 10, 40, 30)
        btn_guardar = QPushButton("💾 GUARDAR TODOS LOS PRECIOS")
        btn_guardar.setProperty("class", "accion")
        btn_guardar.clicked.connect(self.guardar_precios)
        btn_bar.addStretch(); btn_bar.addWidget(btn_guardar)
        outer_l.addLayout(btn_bar)

        self.in_p = {}
        return outer

    def _titulo_seccion_precios(self, texto):
        lbl = QLabel(texto)
        lbl.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {self.c_boton}; margin-top: 18px; margin-bottom: 8px;")
        return lbl

    def _fila_precio_doble(self, layout, etiqueta, plan_ef, dias_ef, plan_tr, dias_tr, precios_map):
        fila = QFrame()
        fila.setStyleSheet("QFrame { background:#141414; border-radius:10px; border:1px solid #2a2a2a; }")
        fl = QHBoxLayout(fila)
        fl.setContentsMargins(18, 12, 18, 12); fl.setSpacing(14)
        lbl = QLabel(etiqueta)
        lbl.setStyleSheet("font-weight:bold; min-width:140px;")
        lbl.setMinimumWidth(140)
        fl.addWidget(lbl)

        def inp_precio(plan_key, dias_key):
            val = precios_map.get((plan_key, int(dias_key)), 0)
            inp = QLineEdit(str(int(float(val or 0))))
            inp.setFixedWidth(120)
            inp.setPlaceholderText("$")
            self.in_p[f"{plan_key}|{dias_key}"] = inp
            return inp

        fl.addWidget(QLabel("Efectivo:"))
        fl.addWidget(inp_precio(plan_ef, dias_ef))
        fl.addSpacing(12)
        fl.addWidget(QLabel("Transferencia:"))
        fl.addWidget(inp_precio(plan_tr, dias_tr))
        fl.addStretch()
        layout.addWidget(fila)

    def _fila_precio_simple(self, layout, etiqueta, plan_key, dias_key, precios_map):
        fila = QFrame()
        fila.setStyleSheet("QFrame { background:#141414; border-radius:10px; border:1px solid #2a2a2a; }")
        fl = QHBoxLayout(fila)
        fl.setContentsMargins(18, 12, 18, 12); fl.setSpacing(14)
        lbl = QLabel(etiqueta)
        lbl.setStyleSheet("font-weight:bold; min-width:180px;")
        fl.addWidget(lbl)
        val = precios_map.get((plan_key, int(dias_key)), 0)
        inp = QLineEdit(str(int(float(val or 0))))
        inp.setFixedWidth(140)
        inp.setPlaceholderText("$")
        self.in_p[f"{plan_key}|{dias_key}"] = inp
        fl.addWidget(inp)
        fl.addStretch()
        layout.addWidget(fila)

    def cargar_precios(self):
        self.in_p = {}
        try:
            res_pr = self.supabase.table('precios').select('*').execute()
            precios_map = {}
            for r in (res_pr.data or []):
                precios_map[(r.get('plan', ''), int(r.get('dias', 0) or 0))] = r.get('precio', 0)

            content = QWidget()
            main_l = QVBoxLayout(content)
            main_l.setContentsMargins(30, 15, 30, 30); main_l.setSpacing(12)

            main_l.addWidget(self._titulo_seccion_precios("SEMIPERSONALIZADO"))
            sub_semi = QLabel("Precio mensual según cantidad de días por semana (efectivo y transferencia).")
            sub_semi.setStyleSheet("color:#aaa; font-size:13px; margin-bottom:6px;")
            main_l.addWidget(sub_semi)
            for d in range(2, 7):
                self._fila_precio_doble(
                    main_l, f"{d} días/semana",
                    PLAN_SEMIPERSONALIZADO, d,
                    "Semipersonalizado_TR", d,
                    precios_map
                )

            main_l.addWidget(self._titulo_seccion_precios("PERSONALIZADO"))
            sub_pers = QLabel("Precio por hora de entrenamiento personalizado.")
            sub_pers.setStyleSheet("color:#aaa; font-size:13px; margin-bottom:6px;")
            main_l.addWidget(sub_pers)
            self._fila_precio_simple(main_l, "Precio por hora:", PLAN_PERSONALIZADO, 0, precios_map)

            main_l.addWidget(self._titulo_seccion_precios("PASE LIBRE"))
            sub_libre = QLabel("Precio mensual con acceso libre al gimnasio.")
            sub_libre.setStyleSheet("color:#aaa; font-size:13px; margin-bottom:6px;")
            main_l.addWidget(sub_libre)
            self._fila_precio_doble(
                main_l, "Mensualidad",
                PLAN_PASE_LIBRE, 0,
                "Pase Libre_TR", 0,
                precios_map
            )

            main_l.addStretch()
            self._scroll_precios.setWidget(content)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _upsert_precio(self, plan, dias, precio):
        rp = self.supabase.table('precios').select('id').eq('plan', plan).eq('dias', int(dias)).execute()
        if rp.data:
            self.supabase.table('precios').update({'precio': precio}).eq('id', rp.data[0]['id']).execute()
        else:
            self.supabase.table('precios').insert({'plan': plan, 'dias': int(dias), 'precio': precio}).execute()

    def _guardar_precio_individual(self, k, inp):
        try:
            plan, dias = k.split('|', 1)
            v = float(inp.text().strip() or 0)
            self._upsert_precio(plan, dias, v)
            inp.setStyleSheet("border: 2px solid #10b981;")
            inp.setToolTip(f"Precio actualizado: ${int(v):,}".replace(',', '.'))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def guardar_precios(self):
        try:
            for k, inp in self.in_p.items():
                self._guardar_precio_individual(k, inp)
            QMessageBox.information(self, "OK", "Precios guardados correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _form_plan_widgets(self, datos=None):
        d = datos or {}
        e_nombre  = QLineEdit(d.get('nombre', ''))
        e_tag     = QLineEdit(d.get('tag', ''))
        e_desc    = QLineEdit(d.get('descripcion', ''))
        e_plankey = QComboBox(); e_plankey.addItems(["Mensual", "Personalizado"])
        idx = e_plankey.findText(d.get('plan_key', 'Mensual'))
        if idx >= 0: e_plankey.setCurrentIndex(idx)
        e_dias = QSpinBox(); e_dias.setRange(1, 7); e_dias.setValue(int(d.get('dias', 3) or 3)); e_dias.setSuffix(" días")
        e_tipo = QComboBox(); e_tipo.addItems(["inscripcion", "contacto"])
        idx_t = e_tipo.findText(d.get('tipo', 'inscripcion'))
        if idx_t >= 0: e_tipo.setCurrentIndex(idx_t)
        e_btnlabel = QLineEdit(d.get('btn_label', ''))
        e_featured = QCheckBox("Destacado en la web"); e_featured.setChecked(bool(d.get('featured', False)))
        e_items = QTextEdit()
        items = d.get('items', [])
        e_items.setPlainText('\n'.join(items) if isinstance(items, list) else str(items))
        e_items.setMinimumHeight(90); e_items.setMaximumHeight(120)
        return e_nombre, e_tag, e_desc, e_plankey, e_dias, e_tipo, e_btnlabel, e_featured, e_items

    def crear_editor_plan_pantalla(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(40, 40, 40, 40)

        h = QHBoxLayout()
        btn_volver = QPushButton("VOLVER")
        btn_volver.setProperty("class", "accion")
        btn_volver.setFixedSize(150, 45)
        btn_volver.clicked.connect(lambda: [self.pantallas.setCurrentIndex(5), self.cargar_precios()])
        self.lbl_editor_plan_titulo = QLabel("EDITAR PLAN")
        self.lbl_editor_plan_titulo.setStyleSheet(f"font-size: 30px; font-weight: bold; color: {self.c_boton};")
        h.addWidget(btn_volver)
        h.addSpacing(20)
        h.addWidget(self.lbl_editor_plan_titulo)
        h.addStretch()
        l.addLayout(h)

        self.scroll_editor_plan = QScrollArea()
        self.scroll_editor_plan.setWidgetResizable(True)
        self.scroll_editor_plan.setStyleSheet("QScrollArea { border:none; } QScrollBar:vertical { background:#1a1a1a; width:8px; border-radius:4px; } QScrollBar::handle:vertical { background:#444; border-radius:4px; }")
        l.addWidget(self.scroll_editor_plan)
        return w

    def _mostrar_editor_plan_pantalla(self, titulo, datos=None, precio_actual="0", plan_data=None):
        self.lbl_editor_plan_titulo.setText(titulo.upper())

        content = QWidget()
        main_l = QVBoxLayout(content)
        main_l.setContentsMargins(20, 20, 20, 20)
        main_l.setSpacing(16)

        form_box = QFrame()
        form_box.setStyleSheet("QFrame { background:#111; border:1px solid #2a2a2a; border-radius:12px; }")
        ff = QFormLayout(form_box)
        ff.setVerticalSpacing(18)
        ff.setContentsMargins(26, 24, 26, 24)

        e_nombre, e_tag, e_desc, e_plankey, e_dias, e_tipo, e_btnlabel, e_featured, e_items = self._form_plan_widgets(datos)
        e_nombre.setPlaceholderText("Ej: 3 dias por semana")
        e_tag.setPlaceholderText("Ej: Mas elegido")
        e_desc.setPlaceholderText("Descripcion visible en la web")
        e_btnlabel.setPlaceholderText("Ej: Inscribirme")
        e_items.setPlaceholderText("Un beneficio por linea:\nAcceso 3 veces por semana\nRutina incluida")
        e_precio = QLineEdit(str(precio_actual))
        e_precio.setPlaceholderText("Ej: 30000")

        ff.addRow("Nombre del plan:", e_nombre)
        ff.addRow("Etiqueta (tag):", e_tag)
        ff.addRow("Descripcion:", e_desc)
        ff.addRow("Plan base:", e_plankey)
        ff.addRow("Dias por semana:", e_dias)
        ff.addRow("Accion del boton:", e_tipo)
        ff.addRow("Texto del boton:", e_btnlabel)
        ff.addRow("", e_featured)
        ff.addRow("Beneficios:", e_items)
        ff.addRow("Precio: $", e_precio)
        main_l.addWidget(form_box)

        h_btn = QHBoxLayout()
        btn_cancel = QPushButton("CANCELAR")
        btn_cancel.setStyleSheet("background:#333; color:white; font-weight:bold; padding:14px; border-radius:10px;")
        btn_cancel.clicked.connect(lambda: [self.pantallas.setCurrentIndex(5), self.cargar_precios()])
        btn_save = QPushButton("GUARDAR PLAN")
        btn_save.setProperty("class", "accion")
        h_btn.addWidget(btn_cancel)
        h_btn.addStretch()
        h_btn.addWidget(btn_save)
        main_l.addLayout(h_btn)
        main_l.addStretch()
        self.scroll_editor_plan.setWidget(content)

        def guardar():
            nombre = e_nombre.text().strip()
            if not nombre:
                QMessageBox.warning(self, "Atencion", "El nombre del plan es obligatorio.")
                return

            items_list = [x.strip() for x in e_items.toPlainText().split('\n') if x.strip()]
            data = {
                "nombre": nombre,
                "tag": e_tag.text().strip(),
                "descripcion": e_desc.text().strip(),
                "plan_key": e_plankey.currentText(),
                "dias": e_dias.value(),
                "tipo": e_tipo.currentText(),
                "btn_label": e_btnlabel.text().strip() or "Inscribirme",
                "featured": e_featured.isChecked(),
                "items": items_list
            }
            try:
                if plan_data:
                    self.supabase.table('planes').update(data).eq('id', plan_data['id']).execute()
                    msg = "Plan actualizado. La web lo refleja automaticamente."
                else:
                    data["orden"] = 99
                    self.supabase.table('planes').insert(data).execute()
                    msg = "Plan creado. La web lo muestra automaticamente."

                v = float(e_precio.text().strip() or 0)
                rp = self.supabase.table('precios').select('id').eq('plan', data['plan_key']).eq('dias', data['dias']).execute()
                if rp.data:
                    self.supabase.table('precios').update({'precio': v}).eq('id', rp.data[0]['id']).execute()
                else:
                    self.supabase.table('precios').insert({'plan': data['plan_key'], 'dias': data['dias'], 'precio': v}).execute()

                self.cargar_precios()
                self.cargar_tabla_planes()
                self.pantallas.setCurrentIndex(5)
                QMessageBox.information(self, "OK", msg)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

        btn_save.clicked.connect(guardar)
        self.pantallas.setCurrentIndex(13)

    def _abrir_editor_plan_pantalla(self, plan_data, inp_precio_ref):
        precio_actual = inp_precio_ref.text() if inp_precio_ref else "0"
        self._mostrar_editor_plan_pantalla(f"Editar: {plan_data.get('nombre', '')}", plan_data, precio_actual, plan_data)

    def _nuevo_plan_pantalla(self):
        self._mostrar_editor_plan_pantalla("Nuevo Plan", None, "0", None)

    def _construir_dialog_plan(self, titulo, datos=None, precio_actual="0"):
        dlg = QDialog(self); dlg.setWindowTitle(titulo); dlg.setMinimumWidth(520)
        dlg.setStyleSheet(self.styleSheet() + "QDialog { background:#0a0a0a; }")
        l = QVBoxLayout(dlg); l.setContentsMargins(30, 25, 30, 25); l.setSpacing(14)

        tit_lbl = QLabel(titulo)
        tit_lbl.setStyleSheet(f"font-size:18px; font-weight:900; color:{self.c_boton}; background:transparent;")
        l.addWidget(tit_lbl)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; } QScrollBar:vertical { background:#1a1a1a; width:8px; border-radius:4px; } QScrollBar::handle:vertical { background:#444; border-radius:4px; }")
        scroll.setMinimumHeight(420)
        inner = QWidget(); ff = QFormLayout(inner); ff.setVerticalSpacing(15); ff.setContentsMargins(5, 10, 5, 10)

        ws = self._form_plan_widgets(datos)
        e_nombre, e_tag, e_desc, e_plankey, e_dias, e_tipo, e_btnlabel, e_featured, e_items = ws
        e_nombre.setPlaceholderText("Ej: 3 días por semana")
        e_tag.setPlaceholderText("Ej: Más elegido")
        e_desc.setPlaceholderText("Descripción visible en la web")
        e_btnlabel.setPlaceholderText("Ej: Inscribirme")
        e_items.setPlaceholderText("Un beneficio por línea:\nAcceso 3 veces por semana\nRutina incluida")

        e_precio = QLineEdit(str(precio_actual))
        e_precio.setPlaceholderText("Ej: 30000")

        ff.addRow("Nombre del plan:", e_nombre)
        ff.addRow("Etiqueta (tag):",  e_tag)
        ff.addRow("Descripción:",     e_desc)
        ff.addRow("Plan base:",       e_plankey)
        ff.addRow("Días por semana:", e_dias)
        ff.addRow("Acción del botón:",e_tipo)
        ff.addRow("Texto del botón:", e_btnlabel)
        ff.addRow("",                 e_featured)
        ff.addRow("Beneficios:",      e_items)
        ff.addRow("Precio: $",        e_precio)
        scroll.setWidget(inner); l.addWidget(scroll)

        h = QHBoxLayout()
        btn_c = QPushButton("CANCELAR"); btn_c.setStyleSheet("background:#333; color:white; font-weight:bold; padding:12px 20px; border-radius:8px;")
        btn_s = QPushButton("💾 GUARDAR"); btn_s.setProperty("class", "accion")
        btn_c.clicked.connect(dlg.reject)
        h.addWidget(btn_c); h.addStretch(); h.addWidget(btn_s)
        l.addLayout(h)
        return dlg, btn_s, e_nombre, e_tag, e_desc, e_plankey, e_dias, e_tipo, e_btnlabel, e_featured, e_items, e_precio

    def _abrir_editor_plan(self, plan_data, inp_precio_ref):
        precio_actual = inp_precio_ref.text() if inp_precio_ref else "0"
        dlg, btn_s, e_nombre, e_tag, e_desc, e_plankey, e_dias, e_tipo, e_btnlabel, e_featured, e_items, e_precio = \
            self._construir_dialog_plan(f"Editar: {plan_data.get('nombre','')}", plan_data, precio_actual)

        def guardar():
            items_list = [x.strip() for x in e_items.toPlainText().split('\n') if x.strip()]
            data = {"nombre": e_nombre.text().strip(), "tag": e_tag.text().strip(),
                    "descripcion": e_desc.text().strip(), "plan_key": e_plankey.currentText(),
                    "dias": e_dias.value(), "tipo": e_tipo.currentText(),
                    "btn_label": e_btnlabel.text().strip() or "Inscribirme",
                    "featured": e_featured.isChecked(), "items": items_list}
            try:
                self.supabase.table('planes').update(data).eq('id', plan_data['id']).execute()
                v = float(e_precio.text().strip() or 0)
                rp = self.supabase.table('precios').select('id').eq('plan', data['plan_key']).eq('dias', data['dias']).execute()
                if rp.data: self.supabase.table('precios').update({'precio': v}).eq('id', rp.data[0]['id']).execute()
                else: self.supabase.table('precios').insert({'plan': data['plan_key'], 'dias': data['dias'], 'precio': v}).execute()
                dlg.accept(); self.cargar_precios(); self.cargar_tabla_planes()
                QMessageBox.information(self, "OK", "Plan actualizado. La web lo refleja automáticamente.")
            except Exception as e: QMessageBox.critical(dlg, "Error", str(e))

        btn_s.clicked.connect(guardar); dlg.exec()

    def _nuevo_plan_dialog(self):
        dlg, btn_s, e_nombre, e_tag, e_desc, e_plankey, e_dias, e_tipo, e_btnlabel, e_featured, e_items, e_precio = \
            self._construir_dialog_plan("Nuevo Plan")

        def guardar():
            nombre = e_nombre.text().strip()
            if not nombre: QMessageBox.warning(dlg, "Atención", "El nombre es obligatorio."); return
            items_list = [x.strip() for x in e_items.toPlainText().split('\n') if x.strip()]
            data = {"nombre": nombre, "tag": e_tag.text().strip(),
                    "descripcion": e_desc.text().strip(), "plan_key": e_plankey.currentText(),
                    "dias": e_dias.value(), "tipo": e_tipo.currentText(),
                    "btn_label": e_btnlabel.text().strip() or "Inscribirme",
                    "featured": e_featured.isChecked(), "items": items_list, "orden": 99}
            try:
                self.supabase.table('planes').insert(data).execute()
                v = float(e_precio.text().strip() or 0)
                rp = self.supabase.table('precios').select('id').eq('plan', data['plan_key']).eq('dias', data['dias']).execute()
                if rp.data: self.supabase.table('precios').update({'precio': v}).eq('id', rp.data[0]['id']).execute()
                else: self.supabase.table('precios').insert({'plan': data['plan_key'], 'dias': data['dias'], 'precio': v}).execute()
                dlg.accept(); self.cargar_precios(); self.cargar_tabla_planes()
                QMessageBox.information(self, "OK", "Plan creado. La web lo muestra automáticamente.")
            except Exception as e: QMessageBox.critical(dlg, "Error", str(e))

        btn_s.clicked.connect(guardar); dlg.exec()

    def _borrar_plan_completo(self, plan, pk, d):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este plan y su precio?") != QMessageBox.StandardButton.Yes: return
        try:
            if plan: self.supabase.table('planes').delete().eq('id', plan['id']).execute()
            rp = self.supabase.table('precios').select('id').eq('plan', pk).eq('dias', d).execute()
            if rp.data: self.supabase.table('precios').delete().eq('id', rp.data[0]['id']).execute()
            self.cargar_precios(); self.cargar_tabla_planes()
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    # === 5. DISENO HD ===
    def crear_diseno(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(60,60,60,60); l.addLayout(self.cabecera("DISEÑO Y APARIENCIA"))
        f = QFormLayout(); f.setVerticalSpacing(18); f.setContentsMargins(0,30,0,0)

        def sep(txt):
            s = QLabel(f"── {txt} ──")
            s.setStyleSheet(f"color:{self.c_boton}; font-size:13px; font-weight:900; letter-spacing:2px; margin:14px 0 4px 0; background:transparent;")
            return s

        # ---- WEB ----
        f.addRow("", sep("DISEÑO DE LA WEB"))
        self.val_fondo = self.c_fondo; self.val_boton = self.c_boton
        self.btn_f = QPushButton("ELEGIR COLOR (FONDO WEB)"); self.btn_f.setMinimumHeight(48)
        self.btn_f.clicked.connect(lambda: self.abrir_paleta("fondo"))
        self.btn_b = QPushButton("ELEGIR COLOR (BOTONES)"); self.btn_b.setMinimumHeight(48)
        self.btn_b.clicked.connect(lambda: self.abrir_paleta("boton"))
        self.in_dt = QLineEdit(); self.in_dt.setPlaceholderText("Color de letra en botones (#000000 o #ffffff)")
        self.lbl_l = QLabel("Logo no seleccionado"); self.b64 = ""
        btn_i = QPushButton("Subir Logo (PNG/JPG)"); btn_i.setStyleSheet("background:#444; padding:10px; border-radius:8px;")
        btn_i.clicked.connect(self.seleccionar_img)
        f.addRow("Fondo de la web:", self.btn_f)
        f.addRow("Color de botones:", self.btn_b)
        f.addRow("Texto en botones:", self.in_dt)
        f.addRow("Logo:", btn_i); f.addRow("", self.lbl_l)


        btn_g = QPushButton("💾 APLICAR Y GUARDAR CAMBIOS"); btn_g.setProperty("class", "accion"); btn_g.clicked.connect(self.guardar_diseno)
        f.addRow("", btn_g)

        l.addLayout(f); l.addStretch(); return w

    def aplicar_tema(self, app_fondo, boton, texto):
        self.val_app_fondo = app_fondo; self.val_boton = boton
        if hasattr(self, "btn_af"):
            self.btn_af.setStyleSheet(f"background:{app_fondo}; color:white; border:2px solid white;")
            self.aplicar_hover_boton(self.btn_af)
            self.btn_af.setText(f"FONDO: {app_fondo}")
        self.btn_b.setStyleSheet(f"background:{boton}; color:{'black' if texto=='#000000' else 'white'}; border:2px solid white;")
        self.aplicar_hover_boton(self.btn_b)
        self.btn_b.setText(f"BOTONES: {boton}")
        self.in_dt.setText(texto)

    def aplicar_modo_preview(self):
        self.val_app_modo = "oscuro"
        self.c_app_modo = "oscuro"
        self.c_app_fondo = "#000000"
        self.aplicar_estilos_hd()

    def abrir_paleta(self, tipo):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_col = color.name()
            if tipo == "fondo":
                self.val_fondo = hex_col
                self.btn_f.setStyleSheet(f"background:{hex_col}; color:white; border:2px solid white;")
                self.aplicar_hover_boton(self.btn_f)
                self.btn_f.setText(f"FONDO WEB: {hex_col}")
            elif tipo == "boton":
                self.val_boton = hex_col
                self.btn_b.setStyleSheet(f"background:{hex_col}; color:black; border:2px solid white;")
                self.aplicar_hover_boton(self.btn_b)
                self.btn_b.setText(f"BOTONES: {hex_col}")
            elif tipo == "app_fondo":
                self.val_app_fondo = hex_col
                if hasattr(self, "btn_af"):
                    self.btn_af.setStyleSheet(f"background:{hex_col}; color:white; border:2px solid white;")
                    self.aplicar_hover_boton(self.btn_af)
                    self.btn_af.setText(f"FONDO PROGRAMA: {hex_col}")

    def cargar_diseno(self):
        self.val_fondo = self.c_fondo; self.val_boton = HERENCIA_MORADO
        self.val_app_modo = "oscuro"
        self.btn_f.setStyleSheet(f"background:{self.c_fondo}; color:white;")
        self.aplicar_hover_boton(self.btn_f)
        self.btn_f.setText(f"FONDO WEB: {self.c_fondo}")
        self.btn_b.setStyleSheet(f"background:{HERENCIA_MORADO}; color:white;")
        self.aplicar_hover_boton(self.btn_b)
        self.btn_b.setText(f"BOTONES: {HERENCIA_MORADO}")
        self.in_dt.setText(HERENCIA_TEXTO_BOTON)

    def seleccionar_img(self):
        r, _ = QFileDialog.getOpenFileName(self, "Logo", "", "Images (*.png *.jpg *.jpeg)")
        if r:
            self.lbl_l.setText("✅ Cargado"); 
            with open(r, "rb") as i: self.b64 = base64.b64encode(i.read()).decode('utf-8')

    def guardar_diseno(self):
        self.val_boton = HERENCIA_MORADO
        self.in_dt.setText(HERENCIA_TEXTO_BOTON)
        d_web = {"color_fondo": self.val_fondo, "color_boton": HERENCIA_MORADO,
                 "color_texto_boton": HERENCIA_TEXTO_BOTON}
        if self.b64: d_web["logo_b64"] = self.b64
        try:
            self.supabase.table('apariencia').update(d_web).eq('id', 1).execute()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return
        # Columnas extra (pueden no existir en la tabla aún — se ignoran si fallan)
        modo_app = "oscuro"
        app_fondo = "#000000"
        try:
            self.supabase.table('apariencia').update({
                "color_app_fondo": app_fondo,
            }).eq('id', 1).execute()
        except: pass
        try:
            self.supabase.table('apariencia').update({"modo_app": modo_app}).eq('id', 1).execute()
        except: pass
        # Aplicar cambios localmente siempre
        self.c_fondo = d_web['color_fondo']; self.c_boton = d_web['color_boton']; self.c_texto = d_web['color_texto_boton']
        self.c_app_modo = modo_app
        self.c_app_fondo = app_fondo
        self.aplicar_estilos_hd()
        QMessageBox.information(self, "Éxito", "Cambios aplicados y guardados en la nube.")

    # ==========================================
    # === 6. REGISTRO DE VENTAS (pedidos entregados) ===
    # ==========================================
    def crear_ventas(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(40,40,40,40); l.addLayout(self.cabecera("REGISTRO DE VENTAS"))

        # Resumen total facturado
        self.lbl_total_ventas = QLabel("TOTAL FACTURADO: $0")
        self.lbl_total_ventas.setStyleSheet("font-size: 26px; font-weight: 900; color: #10b981; margin-top: 10px;")
        l.addWidget(self.lbl_total_ventas)
        l.addSpacing(10)

        self.tabla_v = QTableWidget(0, 4)
        self.tabla_v.setHorizontalHeaderLabels(["FECHA", "CLIENTE", "PRODUCTO", "TOTAL"])
        self.tabla_v.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_v.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_v.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_v.verticalHeader().setMinimumWidth(55)
        self.tabla_v.verticalHeader().setDefaultSectionSize(42)
        self.tabla_v.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(self.tabla_v)

        btn_act = QPushButton("🔄 ACTUALIZAR"); btn_act.setProperty("class", "accion")
        btn_act.clicked.connect(self.cargar_ventas)
        l.addWidget(btn_act)
        return w

    def cargar_ventas(self):
        self.tabla_v.setRowCount(0)
        total_acum = 0
        try:
            res = self.supabase.table('ventas').select('*').order('fecha', desc=True).execute()
            for r, v in enumerate(res.data):
                self.tabla_v.insertRow(r)
                self.tabla_v.setItem(r, 0, QTableWidgetItem(str(v.get('fecha', '-'))))
                self.tabla_v.setItem(r, 1, QTableWidgetItem(v.get('cliente_nombre', '-')))
                self.tabla_v.setItem(r, 2, QTableWidgetItem(v.get('producto', '-')))
                monto = v.get('total', 0) or 0
                item_total = QTableWidgetItem(f"${monto:,.0f}".replace(',', '.'))
                item_total.setForeground(QBrush(QColor("#10b981")))
                item_total.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                self.tabla_v.setItem(r, 3, item_total)
                total_acum += monto
            self.lbl_total_ventas.setText(f"TOTAL FACTURADO: ${total_acum:,.0f}".replace(',', '.'))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ==========================================
    # === 7. STOCK DE PRODUCTOS ===
    # ==========================================
    def crear_stock(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(40,40,40,40); l.addLayout(self.cabecera("STOCK DE PRODUCTOS"))

        # Fila para agregar un producto nuevo
        h_add = QHBoxLayout()
        self.st_nombre = QLineEdit(); self.st_nombre.setPlaceholderText("Nombre del producto")
        self.st_cant = QLineEdit(); self.st_cant.setPlaceholderText("Cantidad"); self.st_cant.setFixedWidth(130)
        self.st_precio = QLineEdit(); self.st_precio.setPlaceholderText("Precio $"); self.st_precio.setFixedWidth(150)
        btn_add = QPushButton("➕ AGREGAR"); btn_add.setProperty("class", "accion"); btn_add.setFixedWidth(170)
        btn_add.clicked.connect(self.agregar_producto)
        h_add.addWidget(self.st_nombre); h_add.addWidget(self.st_cant); h_add.addWidget(self.st_precio); h_add.addWidget(btn_add)
        l.addLayout(h_add)
        l.addSpacing(15)

        self.lbl_alerta_stock = QLabel("")
        self.lbl_alerta_stock.setStyleSheet("font-size: 18px; font-weight: 900; color: #f59e0b; margin: 6px 0;")
        l.addWidget(self.lbl_alerta_stock)

        self.tabla_s = QTableWidget(0, 5)
        self.tabla_s.setHorizontalHeaderLabels(["PRODUCTO", "CANTIDAD", "PRECIO", "ESTADO", "ID"])
        self.tabla_s.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_s.verticalHeader().setMinimumWidth(44); self.tabla_s.verticalHeader().setDefaultSectionSize(42)
        self.tabla_s.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_s.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_s.itemSelectionChanged.connect(self.cargar_cantidad_seleccionada)
        self.tabla_s.setColumnHidden(4, True)  # el ID queda oculto
        l.addWidget(self.tabla_s)

        # Controles de cantidad y borrado
        h_ctrl = QHBoxLayout()
        btn_menos = QPushButton("➖ QUITAR 1"); btn_menos.setStyleSheet("background:#f59e0b; color:black; font-weight:bold; padding:14px; border-radius:10px;")
        btn_menos.clicked.connect(lambda: self.ajustar_cantidad(-1))
        btn_mas = QPushButton("➕ SUMAR 1"); btn_mas.setStyleSheet("background:#10b981; color:white; font-weight:bold; padding:14px; border-radius:10px;")
        btn_mas.clicked.connect(lambda: self.ajustar_cantidad(1))
        self.st_nueva_cant = QLineEdit()
        self.st_nueva_cant.setPlaceholderText("Nueva cantidad")
        self.st_nueva_cant.setFixedWidth(170)
        btn_set = QPushButton("✏️ FIJAR CANTIDAD"); btn_set.setProperty("class", "accion")
        btn_set.clicked.connect(self.fijar_cantidad)
        btn_del = QPushButton("🗑 ELIMINAR PRODUCTO"); btn_del.setStyleSheet("background:#d13636; color:white; font-weight:bold; padding:14px; border-radius:10px;")
        btn_del.clicked.connect(self.borrar_producto)
        h_ctrl.addWidget(btn_menos); h_ctrl.addWidget(btn_mas); h_ctrl.addWidget(self.st_nueva_cant); h_ctrl.addWidget(btn_set); h_ctrl.addStretch(); h_ctrl.addWidget(btn_del)
        l.addLayout(h_ctrl)
        return w

    def cargar_stock(self):
        self.tabla_s.setRowCount(0)
        productos_bajos = []
        try:
            res = self.supabase.table('productos').select('*').order('nombre').execute()
            for r, p in enumerate(res.data):
                self.tabla_s.insertRow(r)
                nombre = p.get('nombre', '-')
                self.tabla_s.setItem(r, 0, QTableWidgetItem(nombre))
                cant = int(p.get('cantidad', 0) or 0)
                item_cant = QTableWidgetItem(str(cant))
                if cant <= 0: col = QColor("#ef4444")
                elif cant < 10: col = QColor("#f59e0b")
                else: col = QColor("#10b981")
                item_cant.setForeground(QBrush(col)); item_cant.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                self.tabla_s.setItem(r, 1, item_cant)
                precio = p.get('precio', 0) or 0
                self.tabla_s.setItem(r, 2, QTableWidgetItem(f"${precio:,.0f}".replace(',', '.')))
                if cant <= 0:
                    estado_txt = "SIN STOCK"
                    productos_bajos.append(f"{nombre} (0)")
                elif cant < 10:
                    estado_txt = "POCO STOCK"
                    productos_bajos.append(f"{nombre} ({cant})")
                else:
                    estado_txt = "OK"

                item_estado = QTableWidgetItem(estado_txt)
                item_estado.setForeground(QBrush(col))
                item_estado.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                self.tabla_s.setItem(r, 3, item_estado)
                self.tabla_s.setItem(r, 4, QTableWidgetItem(str(p.get('id', ''))))

                if cant < 10:
                    fondo = QColor("#3a2410") if cant > 0 else QColor("#3a1111")
                    for c in range(4):
                        item = self.tabla_s.item(r, c)
                        if item:
                            item.setBackground(QBrush(fondo))

            if productos_bajos:
                self.lbl_alerta_stock.setText("ALERTA: pocos productos en stock: " + ", ".join(productos_bajos))
            else:
                self.lbl_alerta_stock.setText("Stock en buen estado.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def agregar_producto(self):
        nombre = self.st_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Atención", "Escribí el nombre del producto.")
            return
        try: cant = int(self.st_cant.text()) if self.st_cant.text().strip() else 0
        except: cant = 0
        try: precio = float(self.st_precio.text()) if self.st_precio.text().strip() else 0
        except: precio = 0
        try:
            self.supabase.table('productos').insert({"nombre": nombre, "cantidad": cant, "precio": precio}).execute()
            self.st_nombre.clear(); self.st_cant.clear(); self.st_precio.clear()
            self.cargar_stock()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _producto_seleccionado(self):
        f = self.tabla_s.currentRow()
        if f < 0:
            QMessageBox.warning(self, "Atención", "Seleccioná un producto de la lista.")
            return None
        pid = self.tabla_s.item(f, 4).text()
        cant_actual = int(self.tabla_s.item(f, 1).text())
        return pid, cant_actual

    def cargar_cantidad_seleccionada(self):
        f = self.tabla_s.currentRow()
        if f < 0 or not hasattr(self, "st_nueva_cant"):
            return
        item = self.tabla_s.item(f, 1)
        if item:
            self.st_nueva_cant.setText(item.text())

    def ajustar_cantidad(self, delta):
        sel = self._producto_seleccionado()
        if not sel: return
        pid, cant_actual = sel
        nueva = max(0, cant_actual + delta)
        try:
            self.supabase.table('productos').update({"cantidad": nueva}).eq('id', pid).execute()
            self.cargar_stock()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def fijar_cantidad(self):
        sel = self._producto_seleccionado()
        if not sel: return
        pid, _ = sel
        texto = self.st_nueva_cant.text().strip()
        if not texto:
            QMessageBox.warning(self, "Atencion", "Escribi la nueva cantidad.")
            return
        try:
            nueva = int(texto)
        except:
            QMessageBox.warning(self, "Atencion", "La cantidad tiene que ser un numero entero.")
            return
        if nueva < 0:
            QMessageBox.warning(self, "Atencion", "La cantidad no puede ser negativa.")
            return
        try:
            self.supabase.table('productos').update({"cantidad": nueva}).eq('id', pid).execute()
            self.cargar_stock()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def borrar_producto(self):
        sel = self._producto_seleccionado()
        if not sel: return
        pid, _ = sel
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este producto del stock?") == QMessageBox.StandardButton.Yes:
            try:
                self.supabase.table('productos').delete().eq('id', pid).execute()
                self.cargar_stock()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ==========================================
    # === 8. GESTIONAR PLANES ===
    # ==========================================
    def crear_gestionar_planes(self):
        outer = QWidget()
        outer_l = QVBoxLayout(outer)
        outer_l.setContentsMargins(0, 0, 0, 0)
        outer_l.setSpacing(0)

        # Cabecera fija
        hdr_w = QWidget()
        hdr_l = QVBoxLayout(hdr_w)
        hdr_l.setContentsMargins(40, 30, 40, 15)
        hdr_l.addLayout(self.cabecera("GESTIONAR PLANES"))
        outer_l.addWidget(hdr_w)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollBar:vertical { background: #1a1a1a; width: 8px; border-radius: 4px; } QScrollBar::handle:vertical { background: #444; border-radius: 4px; }")
        outer_l.addWidget(scroll)

        content = QWidget()
        l = QVBoxLayout(content)
        l.setContentsMargins(40, 10, 40, 40)
        l.setSpacing(18)

        # ── Selector de plan existente ──
        sel_frame = QFrame()
        sel_frame.setStyleSheet("QFrame { background:#111; border-radius:12px; border:1px solid #2a2a2a; }")
        sel_l = QHBoxLayout(sel_frame)
        sel_l.setContentsMargins(20, 14, 20, 14)
        lbl_sel = QLabel("Editar plan existente:")
        lbl_sel.setStyleSheet("background:transparent; border:none; color:#aaa; font-weight:600;")
        self.cmb_planes_selector = QComboBox()
        self.cmb_planes_selector.setMinimumHeight(40)
        self.cmb_planes_selector.currentIndexChanged.connect(self._selector_plan_changed)
        sel_l.addWidget(lbl_sel)
        sel_l.addWidget(self.cmb_planes_selector, 1)
        l.addWidget(sel_frame)

        # ── Formulario ──
        self.f_plan = QFrame()
        self.f_plan.setStyleSheet("QFrame { background:#1a1a1a; border-radius:15px; border:1px solid #333; }")
        ff = QFormLayout(self.f_plan)
        ff.setVerticalSpacing(18)
        ff.setContentsMargins(30, 25, 30, 25)
        ff.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.pl_nombre   = QLineEdit(); self.pl_nombre.setPlaceholderText("Ej: 3 días")
        self.pl_tag      = QLineEdit(); self.pl_tag.setPlaceholderText("Ej: Más elegido")
        self.pl_desc     = QLineEdit(); self.pl_desc.setPlaceholderText("Descripción visible en la web")
        self.pl_plankey  = QComboBox(); self.pl_plankey.addItems(["Mensual", "Personalizado"])
        self.pl_dias     = QSpinBox(); self.pl_dias.setRange(1, 7); self.pl_dias.setValue(3); self.pl_dias.setSuffix(" días")
        self.pl_tipo     = QComboBox(); self.pl_tipo.addItems(["inscripcion", "contacto"])
        self.pl_btnlabel = QLineEdit(); self.pl_btnlabel.setPlaceholderText("Ej: Inscribirme")
        self.pl_featured = QCheckBox("Destacar este plan (resaltado en la web)")
        self.pl_items    = QTextEdit()
        self.pl_items.setMinimumHeight(110); self.pl_items.setMaximumHeight(150)
        self.pl_items.setPlaceholderText("Un beneficio por línea:\nAcceso 3 veces por semana\nSala de musculación\nRutina incluida")
        self.pl_id_oculto = ""
        self.planes_data  = []

        ff.addRow("Nombre del plan:",  self.pl_nombre)
        ff.addRow("Etiqueta (tag):",   self.pl_tag)
        ff.addRow("Descripción:",      self.pl_desc)
        ff.addRow("Plan base:",        self.pl_plankey)
        ff.addRow("Días por semana:",  self.pl_dias)
        ff.addRow("Acción del botón:", self.pl_tipo)
        ff.addRow("Texto del botón:",  self.pl_btnlabel)
        ff.addRow("",                  self.pl_featured)
        ff.addRow("Beneficios:",       self.pl_items)
        l.addWidget(self.f_plan)

        # ── Botones ──
        h = QHBoxLayout(); h.setSpacing(12)
        btn_new  = QPushButton("➕ NUEVO PLAN"); btn_new.setProperty("class", "accion"); btn_new.clicked.connect(self.limpiar_form_plan)
        btn_save = QPushButton("💾 GUARDAR");    btn_save.setProperty("class", "accion"); btn_save.clicked.connect(self.guardar_plan)
        btn_del  = QPushButton("🗑 ELIMINAR");   btn_del.setStyleSheet("background:#d13636; color:white; font-weight:bold; padding:14px; border-radius:10px;")
        btn_del.clicked.connect(self.borrar_plan_tabla)
        h.addWidget(btn_new); h.addWidget(btn_save); h.addStretch(); h.addWidget(btn_del)
        l.addLayout(h)
        l.addStretch()

        scroll.setWidget(content)
        return outer

    def cargar_tabla_planes(self):
        self.planes_data = []
        try:
            res = self.supabase.table('planes').select('*').order('orden').execute()
            self.planes_data = res.data
            # Bloquear señal para no disparar _selector_plan_changed mientras se carga
            self.cmb_planes_selector.blockSignals(True)
            self.cmb_planes_selector.clear()
            self.cmb_planes_selector.addItem("── Nuevo plan ──", userData=None)
            for p in res.data:
                label = p.get('nombre', '-')
                tag = p.get('tag', '')
                self.cmb_planes_selector.addItem(f"{label}  {('· ' + tag) if tag else ''}".strip(), userData=p.get('id'))
            self.cmb_planes_selector.blockSignals(False)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _selector_plan_changed(self, idx):
        if idx <= 0:
            self.limpiar_form_plan(limpiar_combo=False)
            return
        pid = self.cmb_planes_selector.itemData(idx)
        p = next((x for x in self.planes_data if str(x.get('id', '')) == str(pid)), None)
        if not p: return
        self.pl_id_oculto = str(p.get('id', ''))
        self.pl_nombre.setText(p.get('nombre', ''))
        self.pl_tag.setText(p.get('tag', ''))
        self.pl_desc.setText(p.get('descripcion', ''))
        idx_k = self.pl_plankey.findText(p.get('plan_key', 'Mensual'))
        if idx_k >= 0: self.pl_plankey.setCurrentIndex(idx_k)
        self.pl_dias.setValue(int(p.get('dias', 3) or 3))
        idx_t = self.pl_tipo.findText(p.get('tipo', 'inscripcion'))
        if idx_t >= 0: self.pl_tipo.setCurrentIndex(idx_t)
        self.pl_btnlabel.setText(p.get('btn_label', ''))
        self.pl_featured.setChecked(bool(p.get('featured', False)))
        items = p.get('items', [])
        self.pl_items.setPlainText('\n'.join(items) if isinstance(items, list) else str(items))

    def limpiar_form_plan(self, limpiar_combo=True):
        self.pl_id_oculto = ""
        self.pl_nombre.clear(); self.pl_tag.clear(); self.pl_desc.clear()
        self.pl_plankey.setCurrentIndex(0); self.pl_dias.setValue(3)
        self.pl_tipo.setCurrentIndex(0); self.pl_btnlabel.clear()
        self.pl_featured.setChecked(False); self.pl_items.clear()
        if limpiar_combo:
            self.cmb_planes_selector.blockSignals(True)
            self.cmb_planes_selector.setCurrentIndex(0)
            self.cmb_planes_selector.blockSignals(False)

    def guardar_plan(self):
        nombre = self.pl_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Atención", "El nombre del plan es obligatorio."); return
        items = [l.strip() for l in self.pl_items.toPlainText().split('\n') if l.strip()]
        orden = len(self.planes_data) if not self.pl_id_oculto else next(
            (i for i, p in enumerate(self.planes_data) if str(p.get('id','')) == self.pl_id_oculto), 0)
        data = {
            "nombre": nombre,
            "tag": self.pl_tag.text().strip(),
            "descripcion": self.pl_desc.text().strip(),
            "plan_key": self.pl_plankey.currentText(),
            "dias": self.pl_dias.value(),
            "tipo": self.pl_tipo.currentText(),
            "btn_label": self.pl_btnlabel.text().strip() or "Inscribirme",
            "featured": self.pl_featured.isChecked(),
            "items": items,
            "orden": orden
        }
        try:
            if self.pl_id_oculto:
                self.supabase.table('planes').update(data).eq('id', self.pl_id_oculto).execute()
                msg = "Plan actualizado. La web lo mostrará automáticamente."
            else:
                self.supabase.table('planes').insert(data).execute()
                msg = "Plan agregado. La web lo mostrará automáticamente."

            # Crear entrada en precios si no existe para este plan_key + dias
            pk, dias = data['plan_key'], data['dias']
            try:
                rp = self.supabase.table('precios').select('id').eq('plan', pk).eq('dias', dias).execute()
                if not rp.data:
                    self.supabase.table('precios').insert({'plan': pk, 'dias': dias, 'precio': 0}).execute()
                    msg += f"\n\nSe creó una entrada en Precios para '{pk} · {dias} días' con $0. Actualizala en PRECIOS DE PLANES."
            except: pass

            self.cargar_tabla_planes(); self.limpiar_form_plan()
            # Refrescar precios si el scroll ya fue inicializado
            if hasattr(self, '_scroll_precios'):
                self.cargar_precios()
            QMessageBox.information(self, "OK", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def borrar_plan_tabla(self):
        if not self.pl_id_oculto:
            QMessageBox.warning(self, "Atención", "Seleccioná un plan del selector primero."); return
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este plan de la web?") == QMessageBox.StandardButton.Yes:
            try:
                self.supabase.table('planes').delete().eq('id', self.pl_id_oculto).execute()
                self.cargar_tabla_planes()
                self.limpiar_form_plan()
                if hasattr(self, '_scroll_precios'):
                    self.cargar_precios()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv); window = AdminGym(); window.show(); sys.exit(app.exec())
