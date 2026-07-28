import datetime
import os, sys, time
import logging
import tempfile
import traceback
from logging.handlers import TimedRotatingFileHandler

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    running_mode = 'Frozen/executable'
else:
    try:
        app_full_path = os.path.realpath(__file__)
        application_path = os.path.dirname(app_full_path)
        running_mode = "Non-interactive"
    except NameError:
        application_path = os.getcwd()
        running_mode = 'Interactive'

# Catches any exception that escapes to the top (missing config keys, DLLs
# the customer's machine lacks, permission errors, etc). Without this,
# PyInstaller's bootloader prints "Failed to execute script 'main'" to a
# console window that closes itself the instant the app was double-clicked,
# so nobody ever sees why it died. This writes the traceback to disk and
# raises a MessageBox that stays on screen regardless of how the app was
# launched.
def _handle_uncaught_exception(exc_type, exc_value, exc_tb):
    trace_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    crash_filename = f"crash_{time.strftime('%Y%m%d_%H%M%S')}.log"

    written_to = []
    for folder in (application_path, tempfile.gettempdir()):
        try:
            crash_path = os.path.join(folder, crash_filename)
            with open(crash_path, 'w', encoding='utf-8') as f:
                f.write(trace_text)
            written_to.append(crash_path)
        except Exception:
            pass

    sys.__excepthook__(exc_type, exc_value, exc_tb)

    if sys.platform == 'win32':
        try:
            import ctypes
            location_msg = "\n".join(written_to) if written_to else "(gagal menyimpan file log crash)"
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Aplikasi berhenti karena terjadi error.\n\n{exc_type.__name__}: {exc_value}\n\n"
                f"Detail lengkap disimpan di:\n{location_msg}\n\n"
                f"Mohon kirimkan file tersebut ke tim support.",
                "TRB-VIIMS - Aplikasi Berhenti (Error)",
                0x10  # MB_ICONERROR
            )
        except Exception:
            pass

sys.excepthook = _handle_uncaught_exception

logger_name = f'app.log'
logger_dir = os.path.join(application_path, "logs")
try:
    os.makedirs(logger_dir, exist_ok=True)
    _write_test_path = os.path.join(logger_dir, ".write_test")
    with open(_write_test_path, 'w') as _f:
        _f.write("")
    os.remove(_write_test_path)
except Exception:
    # application_path (e.g. Program Files) isn't writable by a
    # non-admin user; fall back to a location that always is rather
    # than crashing the whole app before it even starts.
    logger_dir = os.path.join(tempfile.gettempdir(), "TRB-VIIMS-Pandeglang", "logs")
    os.makedirs(logger_dir, exist_ok=True)

audit_logger = logging.getLogger('viims_audit')
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False
_audit_handler = TimedRotatingFileHandler(
    os.path.join(logger_dir, logger_name), when='midnight', backupCount=30, encoding='utf-8')
_audit_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
audit_logger.addHandler(_audit_handler)

def log_audit(event, detail=""):
    try:
        safe_detail = str(detail).replace("\r", " ").replace("\n", " ")
        audit_logger.info(f"{event} | {safe_detail}" if safe_detail else event)
    except Exception:
        pass

from kivy.config import Config
Config.set('kivy', 'keyboard_mode', 'system')

from kivy.logger import Logger
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.uix.screenmanager import ScreenManager
from kivymd.font_definitions import theme_font_styles
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.textfield import MDTextField
from kivy.metrics import dp
from kivymd.toast import toast
from kivymd.app import MDApp
import numpy as np
import configparser, mysql.connector
from pymodbus.client import ModbusTcpClient
from fpdf import FPDF

colors = {
    "Red"   : {"A200": "#FF2A2A","A500": "#FF8080","A700": "#FFD5D5",},
    "Gray"  : {"200": "#CCCCCC","500": "#ECECEC","700": "#F9F9F9",},
    "Blue"  : {"200": "#4471C4","500": "#5885D8","700": "#6C99EC",},
    "Green" : {"200": "#2CA02C","500": "#2DB97F", "700": "#D5FFD5",},
    "Yellow": {"200": "#ffD42A","500": "#ffE680","700": "#fff6D5",},

    "Light" : {"StatusBar": "E0E0E0","AppBar": "#202020","Background": "#EEEEEE","CardsDialogs": "#FFFFFF","FlatButtonDown": "#CCCCCC",},
    "Dark"  : {"StatusBar": "101010","AppBar": "#E0E0E0","Background": "#111111","CardsDialogs": "#222222","FlatButtonDown": "#DDDDDD",},
}

config_name = 'config.ini'
config_full_path = os.path.join(application_path, config_name)
config = configparser.ConfigParser()
config.read(config_full_path)

## App Setting
APP_TITLE = config['app']['APP_TITLE']
APP_SUBTITLE = config['app']['APP_SUBTITLE']
IMG_LOGO_PEMKAB = config['app']['IMG_LOGO_PEMKAB']
IMG_LOGO_DISHUB = config['app']['IMG_LOGO_DISHUB']
LB_PEMKAB = config['app']['LB_PEMKAB']
LB_DISHUB = config['app']['LB_DISHUB']
LB_UNIT = config['app']['LB_UNIT']
LB_UNIT_ADDRESS = config['app']['LB_UNIT_ADDRESS']

# SQL setting
DB_HOST = "187.77.112.162"
DB_USER = "IntegrasiPnd@"
DB_PASSWORD = "@PndIntegrated26"

DB_NAME = "pkbpandeglang"
TB_DATA = "tb_cekident"
TB_USER = "users"
TB_MERK = "merk"
TB_BAHAN_BAKAR = "bahanbakar"
TB_WARNA = "warna"
TB_DATA_MASTER = "identkendaraan"

FTP_HOST = "187.117.112.162"
FTP_USER = "root"
FTP_PASS = "@SorongNew2026"

## System Setting
TIME_OUT = int(config['setting']['TIME_OUT'])
COUNT_STARTING_SPEED = int(config['setting']['COUNT_STARTING_SPEED'])
COUNT_ACQUISITION_SPEED = int(config['setting']['COUNT_ACQUISITION_SPEED'])
COUNT_STARTING_SIDESLIP = int(config['setting']['COUNT_STARTING_SIDESLIP'])
COUNT_ACQUISITION_SIDESLIP = int(config['setting']['COUNT_ACQUISITION_SIDESLIP'])
UPDATE_CAROUSEL_INTERVAL = float(config['setting']['UPDATE_CAROUSEL_INTERVAL'])
UPDATE_CONNECTION_INTERVAL = float(config['setting']['UPDATE_CONNECTION_INTERVAL'])
GET_DATA_INTERVAL = float(config['setting']['GET_DATA_INTERVAL'])

PRINTER_THERM_COM = str(config['setting']['PRINTER_THERM_COM'])
PRINTER_THERM_BAUD = int(config['setting']['PRINTER_THERM_BAUD'])
PRINTER_THERM_BYTESIZE = int(config['setting']['PRINTER_THERM_BYTESIZE'])
PRINTER_THERM_PARITY = str(config['setting']['PRINTER_THERM_PARITY'])
PRINTER_THERM_STOPBITS = int(config['setting']['PRINTER_THERM_STOPBITS'])
PRINTER_THERM_TIMEOUT = float(config['setting']['PRINTER_THERM_TIMEOUT'])
PRINTER_THERM_DSRDTR = bool(config['setting']['PRINTER_THERM_DSRDTR'])

MODBUS_IP_PLC = config['setting']['MODBUS_IP_PLC']
MODBUS_CLIENT = ModbusTcpClient(MODBUS_IP_PLC)
REGISTER_DATA_SPEED = int(config['setting']['REGISTER_DATA_SPEED']) # 1512 = V1000
REGISTER_DATA_SIDE_SLIP = int(config['setting']['REGISTER_DATA_SIDE_SLIP']) # 1612 = V1100

SIMULATION_MODE = bool(int(config['setting']['SIMULATION_MODE']))

## sensor setting
SENSOR_ENCODER_PPR = float(config['setting']['SENSOR_ENCODER_PPR']) # in mm
SENSOR_LENGTH = float(config['setting']['SENSOR_LENGTH']) # in mm

## system standard
STANDARD_MIN_SPEED = float(config['standard']['STANDARD_MIN_SPEED']) # in rpm
STANDARD_MAX_SPEED = float(config['standard']['STANDARD_MAX_SPEED']) # in rpm
STANDARD_MAX_SIDESLIP = float(config['standard']['STANDARD_MAX_SIDESLIP']) # in mm

mydb = None

def ensure_db_connected():
    global mydb
    try:
        if mydb is None or not mydb.is_connected():
            mydb.reconnect(attempts=3, delay=1)
    except Exception:
        mydb = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, connection_timeout=5)
        log_audit("DB_RECONNECTED", f"host={DB_HOST} db={DB_NAME}")

class ScreenHome(MDScreen):
    def __init__(self, **kwargs):
        super(ScreenHome, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, 1)
    
    def delayed_init(self, dt):
        self.ids.lb_title.text = APP_TITLE
        self.ids.lb_subtitle.text = APP_SUBTITLE        
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS

    def on_enter(self):
        Clock.schedule_interval(self.regular_update_carousel, 3)

    def on_leave(self):
        Clock.unschedule(self.regular_update_carousel)

    def regular_update_carousel(self, dt):
        try:
            self.ids.carousel.index += 1
            
        except Exception as e:
            toast_msg = f'Gagal Memperbaharui Tampilan Carousel'
            toast_msg = f'Error Update Carousel: {e}'
            toast(toast_msg)                

    def exec_navigate_home(self):
        try:
            self.screen_manager.current = 'screen_home'

        except Exception as e:
            toast_msg = f'Error Navigate to Home Screen: {e}'
            toast(toast_msg)        

    def exec_navigate_login(self):
        global dt_user
        try:
            if (dt_user == ""):
                self.screen_manager.current = 'screen_login'
            else:
                toast(f"Anda sudah login sebagai {dt_user}")

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat berpindah ke halaman Login'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_navigate_main(self):
        try:
            self.screen_manager.current = 'screen_main'

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat berpindah ke halaman Utama'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

class ScreenLogin(MDScreen):
    def __init__(self, **kwargs):
        super(ScreenLogin, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, 1)
    
    def delayed_init(self, dt):
        self.ids.lb_title.text = APP_TITLE
        self.ids.lb_subtitle.text = APP_SUBTITLE  
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS

    def exec_cancel(self):
        try:
            self.ids.tx_username.text = ""
            self.ids.tx_password.text = ""    

        except Exception as e:
            toast_msg = f'error Login: {e}'

    def exec_login(self):
        global mydb, dt_id_user, dt_user, dt_foto_user
        import bcrypt
        screen_main = self.screen_manager.get_screen('screen_main')

        try:
            screen_main.exec_reload_database()
            input_email = self.ids.tx_username.text  # Digunakan sebagai input Email
            input_password = self.ids.tx_password.text

            if mydb is None:
                toast("Gagal masuk: tidak dapat terhubung ke database")
                log_audit("LOGIN_FAILED", f"email={input_email} reason=db_not_connected")
                return

            mycursor = mydb.cursor()
            # Query disamakan dengan aplikasi lainnya
            query = "SELECT id_sumber, name, email, password FROM web_users WHERE email = %s AND tipe_user = '5'"

            mycursor.execute(query, (input_email,))
            myresult = mycursor.fetchone()

            if myresult:
                db_id_sumber, db_name, db_email, db_hashed_password = myresult

                if bcrypt.checkpw(input_password.encode('utf-8'), db_hashed_password.encode('utf-8')):
                    toast(f"Berhasil Masuk, Selamat Datang {db_name}")
                    dt_id_user = db_id_sumber
                    dt_user = db_name
                    dt_foto_user = "" # web_users tidak memiliki kolom foto

                    self.ids.tx_username.text = ""
                    self.ids.tx_password.text = ""
                    self.screen_manager.current = 'screen_main'
                    log_audit("LOGIN_SUCCESS", f"user={db_name} id_user={dt_id_user} email={input_email}")
                else:
                    toast("Maaf username dan password tidak sesuai")
                    log_audit("LOGIN_FAILED", f"email={input_email} reason=wrong_password")
            else:
                toast("Maaf username dan password tidak sesuai")
                log_audit("LOGIN_FAILED", f"email={input_email} reason=not_found")

        except Exception as e:
            Logger.error(f"Login Error: {e}")
            toast(f"Gagal masuk: {e}")
            log_audit("LOGIN_ERROR", f"email={input_email} error={e}")

    def exec_navigate_home(self):
        try:
            self.screen_manager.current = 'screen_home'

        except Exception as e:
            toast_msg = f'Gagal Berpindah ke Halaman Awal'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")

    def exec_navigate_login(self):
        global dt_user
        try:
            if (dt_user == ""):
                self.screen_manager.current = 'screen_login'
            else:
                toast_msg = f"Anda sudah login sebagai {dt_user}"
                toast(toast_msg)
                Logger.info(f"{self.name}: {toast_msg}")  

        except Exception as e:
            toast_msg = f'Gagal Berpindah ke Halaman Login'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_navigate_main(self):
        try:
            self.screen_manager.current = 'screen_main'

        except Exception as e:
            toast_msg = f'Gagal Berpindah ke Halaman Utama'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}") 

class ScreenMain(MDScreen):   
    def __init__(self, **kwargs):
        super(ScreenMain, self).__init__(**kwargs)
        global flag_conn_stat, flag_play, flag_cylinder
        global count_starting, count_get_data
        global dt_user, dt_foto_user, dt_no_antri, dt_no_pol, dt_no_uji, dt_sts_uji, dt_nama
        global dt_merk, dt_type, dt_jns_kend, dt_jbb, dt_brt_ksg, dt_bhn_bkr, dt_warna, dt_chasis, dt_no_mesin
        global dt_id_user
        global dt_speed_flag, dt_speed_value
        global dt_sideslip_flag, dt_sideslip_value
        global dt_dash_pendaftaran, dt_dash_belum_uji, dt_dash_sudah_uji
        global flag_conn_stat_prev

        count_starting = COUNT_STARTING_SPEED
        count_get_data = COUNT_ACQUISITION_SPEED

        flag_conn_stat = flag_play = flag_cylinder = False
        flag_conn_stat_prev = None
        dt_user = dt_foto_user = dt_no_antri = dt_no_pol = dt_no_uji = dt_sts_uji = dt_nama = ""
        dt_merk = dt_type = dt_jns_kend = dt_jbb = dt_brt_ksg = dt_bhn_bkr = dt_warna = dt_chasis = dt_no_mesin = ""
        dt_id_user = 1
        dt_dash_pendaftaran = dt_dash_belum_uji = dt_dash_sudah_uji = 0
        dt_speed_value = dt_speed_flag = 0
        dt_sideslip_value = dt_sideslip_flag = 0

        Clock.schedule_once(self.delayed_init, 1)            

    def delayed_init(self, dt):   
        self.ids.lb_title.text = APP_TITLE
        self.ids.lb_subtitle.text = APP_SUBTITLE              
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS
        
        Clock.schedule_interval(self.regular_update_display, 1)
        Clock.schedule_interval(self.regular_update_connection, UPDATE_CONNECTION_INTERVAL)

    def on_enter(self):
        self.exec_reload_database()
        self.exec_reload_table()

    def regular_update_display(self, dt):
        global flag_conn_stat
        global count_starting, count_get_data
        global dt_speed_flag, dt_speed_value
        global dt_sideslip_flag, dt_sideslip_value
        
        try:
            screen_home = self.screen_manager.get_screen('screen_home')
            screen_login = self.screen_manager.get_screen('screen_login')
            screen_menu = self.screen_manager.get_screen('screen_menu')
            screen_calibration = self.screen_manager.get_screen('screen_calibration')

            screen_speed_meter = self.screen_manager.get_screen('screen_speed_meter')
            screen_sideslip_meter = self.screen_manager.get_screen('screen_sideslip_meter')
            
            self.ids.lb_time.text = str(time.strftime("%H:%M:%S", time.localtime()))
            self.ids.lb_date.text = str(time.strftime("%d/%m/%Y", time.localtime()))
            screen_home.ids.lb_time.text = str(time.strftime("%H:%M:%S", time.localtime()))
            screen_home.ids.lb_date.text = str(time.strftime("%d/%m/%Y", time.localtime()))
            screen_login.ids.lb_time.text = str(time.strftime("%H:%M:%S", time.localtime()))
            screen_login.ids.lb_date.text = str(time.strftime("%d/%m/%Y", time.localtime()))
            screen_menu.ids.lb_time.text = str(time.strftime("%H:%M:%S", time.localtime()))
            screen_menu.ids.lb_date.text = str(time.strftime("%d/%m/%Y", time.localtime()))
            screen_calibration.ids.lb_time.text = str(time.strftime("%H:%M:%S", time.localtime()))
            screen_calibration.ids.lb_date.text = str(time.strftime("%d/%m/%Y", time.localtime()))

            screen_speed_meter.ids.lb_time.text = str(time.strftime("%H:%M:%S", time.localtime()))
            screen_speed_meter.ids.lb_date.text = str(time.strftime("%d/%m/%Y", time.localtime()))
            screen_sideslip_meter.ids.lb_time.text = str(time.strftime("%H:%M:%S", time.localtime()))
            screen_sideslip_meter.ids.lb_date.text = str(time.strftime("%d/%m/%Y", time.localtime()))

            self.ids.lb_dash_pendaftaran.text = str(dt_dash_pendaftaran)
            self.ids.lb_dash_belum_uji.text = str(dt_dash_belum_uji)
            self.ids.lb_dash_sudah_uji.text = str(dt_dash_sudah_uji)

            screen_speed_meter.ids.lb_speed_val.text = str(dt_speed_value)
            screen_sideslip_meter.ids.lb_sideslip_val.text = str(dt_sideslip_value)

            if(not flag_play):
                screen_speed_meter.ids.bt_save.md_bg_color = colors['Green']['200']
                screen_speed_meter.ids.bt_save.disabled = False
                screen_speed_meter.ids.bt_reload.md_bg_color = colors['Red']['A200']
                screen_speed_meter.ids.bt_reload.disabled = False
                screen_sideslip_meter.ids.bt_save.md_bg_color = colors['Green']['200']
                screen_sideslip_meter.ids.bt_save.disabled = False
                screen_sideslip_meter.ids.bt_reload.md_bg_color = colors['Red']['A200']
                screen_sideslip_meter.ids.bt_reload.disabled = False
            else:
                screen_speed_meter.ids.bt_reload.disabled = True
                screen_speed_meter.ids.bt_save.disabled = True
                screen_sideslip_meter.ids.bt_reload.disabled = True
                screen_sideslip_meter.ids.bt_save.disabled = True

            if(not flag_conn_stat):
                self.ids.lb_comm.color = colors['Red']['A200']
                self.ids.lb_comm.text = 'PLC Tidak Terhubung'
                screen_home.ids.lb_comm.color = colors['Red']['A200']
                screen_home.ids.lb_comm.text = 'PLC Tidak Terhubung'
                screen_login.ids.lb_comm.color = colors['Red']['A200']
                screen_login.ids.lb_comm.text = 'PLC Tidak Terhubung'
                screen_menu.ids.lb_comm.color = colors['Red']['A200']
                screen_menu.ids.lb_comm.text = 'PLC Tidak Terhubung'
                screen_calibration.ids.lb_comm.color = colors['Red']['A200']
                screen_calibration.ids.lb_comm.text = 'PLC Tidak Terhubung'

                screen_speed_meter.ids.lb_comm.color = colors['Red']['A200']
                screen_speed_meter.ids.lb_comm.text = 'PLC Tidak Terhubung'
                screen_sideslip_meter.ids.lb_comm.color = colors['Red']['A200']
                screen_sideslip_meter.ids.lb_comm.text = 'PLC Tidak Terhubung'

            else:
                self.ids.lb_comm.color = colors['Blue']['200']
                self.ids.lb_comm.text = 'PLC Terhubung'
                screen_home.ids.lb_comm.color = colors['Blue']['200']
                screen_home.ids.lb_comm.text = 'PLC Terhubung'
                screen_login.ids.lb_comm.color = colors['Blue']['200']
                screen_login.ids.lb_comm.text = 'PLC Terhubung'
                screen_menu.ids.lb_comm.color = colors['Blue']['200']
                screen_menu.ids.lb_comm.text = 'PLC Terhubung'
                screen_calibration.ids.lb_comm.color = colors['Blue']['200']
                screen_calibration.ids.lb_comm.text = 'PLC Terhubung'

                screen_speed_meter.ids.lb_comm.color = colors['Blue']['200']
                screen_speed_meter.ids.lb_comm.text = 'PLC Terhubung'
                screen_sideslip_meter.ids.lb_comm.color = colors['Blue']['200']
                screen_sideslip_meter.ids.lb_comm.text = 'PLC Terhubung'

            if(count_starting <= 0):
                screen_speed_meter.ids.lb_test_subtitle.text = "HASIL PENGUKURAN"
                screen_speed_meter.ids.lb_speed_val.text = str(dt_speed_value)
                screen_sideslip_meter.ids.lb_test_subtitle.text = "HASIL PENGUKURAN"
                screen_sideslip_meter.ids.lb_sideslip_val.text = str(dt_sideslip_value)

                if((dt_speed_value >= STANDARD_MIN_SPEED) and (dt_speed_value <= STANDARD_MAX_SPEED)):
                    screen_speed_meter.ids.lb_info.text = f"Ambang Batas Kecepatan yang diperbolehkan adalah {STANDARD_MIN_SPEED} hingga {STANDARD_MAX_SPEED} rpm.\nDeviasi Kecepatan Kendaraan Anda Didalam Ambang Batas"
                else:
                    screen_speed_meter.ids.lb_info.text = f"Ambang Batas Kecepatan yang diperbolehkan adalah {STANDARD_MIN_SPEED} hingga {STANDARD_MAX_SPEED} rpm.\nDeviasi Kecepatan Kendaraan Anda Diluar Ambang Batas"

                if((dt_sideslip_value <= STANDARD_MAX_SIDESLIP) and (dt_sideslip_value >= -STANDARD_MAX_SIDESLIP)):
                    screen_sideslip_meter.ids.lb_info.text = f"Ambang Batas Bergesernya Roda Kendaraan adalah {STANDARD_MAX_SIDESLIP} mm,\nPergeseran Roda Kendaraan Anda Dalam Range Ambang Batas"
                else:
                    screen_sideslip_meter.ids.lb_info.text = f"Ambang Batas Bergesernya Roda Kendaraan adalah {STANDARD_MAX_SIDESLIP} mm,\nPergeseran Roda Kendaraan Anda Diluar Ambang Batas"

            elif(count_starting > 0):
                if(flag_play):
                    screen_speed_meter.ids.lb_test_subtitle.text = "MEMULAI PENGUKURAN"
                    screen_speed_meter.ids.lb_speed_val.text = str(count_starting)
                    screen_speed_meter.ids.lb_info.text = "Silahkan Injak Pedal Gas Sesuai Arahan"

                    screen_sideslip_meter.ids.lb_test_subtitle.text = "MEMULAI PENGUKURAN"
                    screen_sideslip_meter.ids.lb_sideslip_val.text = str(count_starting)
                    screen_sideslip_meter.ids.lb_info.text = "Silahkan Gerakkan Kendaraan Anda Tanpa Memegang Kemudi"

            if(count_get_data <= 0):
                if(not flag_play):
                    if((dt_speed_value >= STANDARD_MIN_SPEED) and (dt_speed_value <= STANDARD_MAX_SPEED)):
                        screen_speed_meter.ids.lb_test_result.md_bg_color = colors['Green']['200']
                        screen_speed_meter.ids.lb_test_result.text = "LULUS"
                        dt_speed_flag = 1
                        screen_speed_meter.ids.lb_test_result.text_color = colors['Green']['700']
                    else:
                        screen_speed_meter.ids.lb_test_result.md_bg_color = colors['Red']['A200']
                        screen_speed_meter.ids.lb_test_result.text = "TIDAK LULUS"
                        dt_speed_flag = 0
                        screen_speed_meter.ids.lb_test_result.text_color = colors['Red']['A700']

                    if((dt_sideslip_value <= STANDARD_MAX_SIDESLIP) and (dt_sideslip_value >= -STANDARD_MAX_SIDESLIP)):
                        screen_sideslip_meter.ids.lb_test_result.md_bg_color = colors['Green']['200']
                        screen_sideslip_meter.ids.lb_test_result.text = "LULUS"
                        dt_sideslip_flag = 1
                        screen_sideslip_meter.ids.lb_test_result.text_color = colors['Green']['700']
                    else:
                        screen_sideslip_meter.ids.lb_test_result.md_bg_color = colors['Red']['A200']
                        screen_sideslip_meter.ids.lb_test_result.text = "TIDAK LULUS"
                        dt_sideslip_flag = 0
                        screen_sideslip_meter.ids.lb_test_result.text_color = colors['Red']['A700']

            elif(count_get_data > 0):
                screen_speed_meter.ids.lb_test_result.md_bg_color = "#EEEEEE"
                screen_speed_meter.ids.lb_test_result.text = ""
                screen_sideslip_meter.ids.lb_test_result.md_bg_color = "#EEEEEE"
                screen_sideslip_meter.ids.lb_test_result.text = ""

            if(self.screen_manager.current == 'screen_calibration'):
                if SIMULATION_MODE:
                    dt_speed_value = np.round(np.random.uniform(STANDARD_MIN_SPEED - 5, STANDARD_MAX_SPEED + 5), 2)
                    dt_sideslip_value = np.round(np.random.uniform(-STANDARD_MAX_SIDESLIP - 3, STANDARD_MAX_SIDESLIP + 3), 2)
                else:
                    MODBUS_CLIENT.connect()
                    speed_registers = MODBUS_CLIENT.read_holding_registers(REGISTER_DATA_SPEED, count=1, slave=1)
                    sideslip_registers = MODBUS_CLIENT.read_holding_registers(REGISTER_DATA_SIDE_SLIP, count=1, slave=1)
                    MODBUS_CLIENT.close()

                    dt_speed_value = np.round(self.unsigned_to_signed(speed_registers.registers[0]) / 10, 2) #dc
                    dt_sideslip_value = np.round(self.unsigned_to_signed(sideslip_registers.registers[0]) / 10, 2) #dc

                screen_calibration.ids.lb_speed_val.text = str(dt_speed_value)
                screen_calibration.ids.lb_sideslip_val.text = str(dt_sideslip_value)

            self.ids.bt_calibrate.disabled = False if dt_user != '' else True
            # self.ids.bt_add_data.disabled = False if dt_user != '' else True
            # self.ids.bt_add_queue.disabled = False if dt_user != '' else True
            self.ids.bt_logout.disabled = False if dt_user != '' else True

            self.ids.lb_operator.text = f'Login Sebagai: \n{dt_user}' if dt_user != '' else 'Silahkan Login'
            screen_home.ids.lb_operator.text = f'Login Sebagai: \n{dt_user}' if dt_user != '' else 'Silahkan Login'
            screen_login.ids.lb_operator.text = f'Login Sebagai: \n{dt_user}' if dt_user != '' else 'Silahkan Login'
            screen_menu.ids.lb_operator.text = f'Login Sebagai: \n{dt_user}' if dt_user != '' else 'Silahkan Login'
            screen_calibration.ids.lb_operator.text = f'Login Sebagai: \n{dt_user}' if dt_user != '' else 'Silahkan Login'

            screen_speed_meter.ids.lb_operator.text = f'Login Sebagai: \n{dt_user}' if dt_user != '' else 'Silahkan Login'
            screen_sideslip_meter.ids.lb_operator.text = f'Login Sebagai: \n{dt_user}' if dt_user != '' else 'Silahkan Login'

            if dt_user != '':
                self.ids.img_user.source = f'https://{FTP_HOST}/ujikir/foto_user/{dt_foto_user}'
                screen_home.ids.img_user.source = f'https://{FTP_HOST}/ujikir/foto_user/{dt_foto_user}'
                screen_login.ids.img_user.source = f'https://{FTP_HOST}/ujikir/foto_user/{dt_foto_user}'
            else:
                self.ids.img_user.source = 'assets/images/icon-login.png'
                screen_home.ids.img_user.source = 'assets/images/icon-login.png'
                screen_login.ids.img_user.source = 'assets/images/icon-login.png'

        except Exception as e:
            toast_msg = f'Gagal Memperbaharui Tampilan'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")

    def regular_update_connection(self, dt):
        global flag_conn_stat, flag_conn_stat_prev

        if SIMULATION_MODE:
            flag_conn_stat = True
        else:
            try:
                MODBUS_CLIENT.connect()
                flag_conn_stat = MODBUS_CLIENT.connected
                MODBUS_CLIENT.close()

            except Exception as e:
                toast_msg = f'Gagal Memperbaharui Koneksi'
                toast(toast_msg)
                Logger.error(f"{self.name}: {toast_msg}, {e}")
                flag_conn_stat = False

        if flag_conn_stat != flag_conn_stat_prev:
            log_audit("PLC_CONNECTED" if flag_conn_stat else "PLC_DISCONNECTED",
                      f"simulation={SIMULATION_MODE} ip={MODBUS_IP_PLC}")
            flag_conn_stat_prev = flag_conn_stat

    def unsigned_to_signed(self, val):
        if val >= 32768:
            return val - 65536
        return val

    def regular_get_data(self, dt):
        global count_starting, count_get_data
        global dt_speed_value, dt_sideslip_value
        global flag_play
        try:
            if(count_starting > 0):
                count_starting -= 1              

            if(count_get_data > 0):
                count_get_data -= 1
                
            elif(count_get_data <= 0):
                flag_play = False
                Clock.unschedule(self.regular_get_data)

            if SIMULATION_MODE:
                dt_speed_value = np.round(np.random.uniform(STANDARD_MIN_SPEED - 5, STANDARD_MAX_SPEED + 5), 2)
                dt_sideslip_value = np.round(abs(np.random.uniform(-STANDARD_MAX_SIDESLIP - 3, STANDARD_MAX_SIDESLIP + 3)), 2)
            elif flag_conn_stat:
                MODBUS_CLIENT.connect()
                speed_registers = MODBUS_CLIENT.read_holding_registers(REGISTER_DATA_SPEED, count=1, slave=1)
                sideslip_registers = MODBUS_CLIENT.read_holding_registers(REGISTER_DATA_SIDE_SLIP, count=1, slave=1)
                MODBUS_CLIENT.close()

                dt_speed_value = np.round(self.unsigned_to_signed(speed_registers.registers[0]) / 10, 2)
                dt_sideslip_value = abs(np.round(self.unsigned_to_signed(sideslip_registers.registers[0]) / 10, 2))
        except Exception as e:
            toast_msg = f'Gagal Mengambil Data dari PLC'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")

    def exec_reload_database(self):
        global mydb
        try:
            mydb = mysql.connector.connect(host = DB_HOST,user = DB_USER,password = DB_PASSWORD, database = DB_NAME, connection_timeout=5)
            log_audit("DB_CONNECTED", f"host={DB_HOST} db={DB_NAME}")
        except Exception as e:
            toast_msg = f'Gagal Menginisiasi Database'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")
            log_audit("DB_CONNECTION_FAILED", f"host={DB_HOST} error={e}") 

    def exec_reload_table(self):
        global mydb, db_antrian
        global db_merk, db_bahan_bakar, db_warna
        global dt_dash_antri, dt_dash_pendaftaran, dt_dash_belum_uji, dt_dash_sudah_uji
        global window_size_x, window_size_y

        try:
            ensure_db_connected()
            cursor = mydb.cursor()
            today = str(time.strftime("%Y-%m-%d", time.localtime()))
            delete_query = f"DELETE FROM {TB_DATA} WHERE DATE(tgl_daftar) != %s"
            cursor.execute(delete_query, (today,))
            mydb.commit()
            toast_msg = f'Berhasil menghapus data kemarin'
        except Exception as e:
            toast_msg = f'Gagal menghapus data kemarin'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")

        try:
            ensure_db_connected()
            cursor = mydb.cursor()
            cursor.execute(f"SELECT ID, DESCRIPTION FROM {TB_MERK}")
            result_tb_merk = cursor.fetchall()
            db_merk = np.array(result_tb_merk)

            cursor.execute(f"SELECT ID, DESCRIPTION FROM {TB_BAHAN_BAKAR}")
            result_tb_bahan_bakar = cursor.fetchall()
            db_bahan_bakar = np.array(result_tb_bahan_bakar)

            cursor.execute(f"SELECT id_warna, nama FROM {TB_WARNA}")
            result_tb_warna = cursor.fetchall()
            db_warna = np.array(result_tb_warna)

            cursor.execute(f"SELECT COUNT(*) FROM {TB_DATA}")
            result = cursor.fetchone()  # Returns tuple like (123,)

            if result is None:
                dt_dash_antri = 0
                toast('Data Tabel cekident kosong')
            else:
                dt_dash_antri = result[0]

                cursor.execute(f"SELECT noantrian, nopol, nouji, statusuji, merk, type, idjeniskendaraan, jbb, berat_kosong, bahan_bakar, warna, speed_flag, sideslip_flag FROM {TB_DATA} WHERE speed_flag = 2 OR sideslip_flag = 2")
                result_tb_antrian = cursor.fetchall()

                if result_tb_antrian:
                    db_antrian = np.array(result_tb_antrian).T
                    db_pendaftaran_array = np.array(result_tb_antrian)
                    dt_dash_belum_uji = db_pendaftaran_array[:,0].size
                else:
                    db_antrian = np.empty((13, 0))
                    dt_dash_belum_uji = 0
                
                dt_dash_pendaftaran = dt_dash_antri
                dt_dash_sudah_uji = dt_dash_pendaftaran - dt_dash_belum_uji
            
            cursor.close()

        except Exception as e:
            toast_msg = f'Gagal mengambil data antrian harian'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  
        
        try:
            layout_list = self.ids.layout_list
            layout_list.clear_widgets(children=None)
        except Exception as e:
            toast_msg = f'Gagal menghapus widget tabel'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")   
        
        try:
            layout_list = self.ids.layout_list
            for i in range(db_antrian[0,:].size):
                layout_list.add_widget(
                    MDCard(
                        MDLabel(text=f"{db_antrian[0, i]}", size_hint_x= 0.05),
                        MDLabel(text=f"{db_antrian[1, i]}", size_hint_x= 0.07),
                        MDLabel(text=f"{db_antrian[2, i]}", size_hint_x= 0.08),
                        MDLabel(text='Berkala' if db_antrian[3, i] == 'B' else 'Uji Ulang' if (db_antrian[3, i]) == 'U' else 'Baru' if (db_antrian[3, i]) == 'BR' else 'Numpang Uji' if (db_antrian[3, i]) == 'NB' else 'Mutasi', size_hint_x= 0.07),
                        MDLabel(text='-' if db_antrian[4, i] == None else f"{db_merk[np.where(db_merk == db_antrian[4, i])[0][0],1]}" , size_hint_x= 0.08),
                        MDLabel(text=f"{db_antrian[5, i]}", size_hint_x= 0.07),
                        MDLabel(text=f"{db_antrian[6, i]}", size_hint_x= 0.15),
                        MDLabel(text=f"{db_antrian[7, i]}", size_hint_x= 0.05),
                        MDLabel(text=f"{db_antrian[8, i]}", size_hint_x= 0.05),
                        MDLabel(text='-' if db_antrian[9, i] == None else f"{db_bahan_bakar[np.where(db_bahan_bakar == db_antrian[9, i])[0][0],1]}" , size_hint_x= 0.08),
                        MDLabel(text='-' if db_antrian[10, i] == None else f"{db_warna[np.where(db_warna == db_antrian[10, i])[0][0],1]}" , size_hint_x= 0.11),
                        MDLabel(text='Lulus' if (int(db_antrian[11, i]) == 1) else 'Tidak Lulus' if (int(db_antrian[11, i]) == 0) else 'Belum Uji', size_hint_x= 0.07),
                        MDLabel(text='Lulus' if (int(db_antrian[12, i]) == 1) else 'Tidak Lulus' if (int(db_antrian[12, i]) == 0) else 'Belum Uji', size_hint_x= 0.07),

                        ripple_behavior = True,
                        on_press = self.on_antrian_row_press,
                        padding = 20,
                        id=f"card_antrian{i}",
                        size_hint_y=None,
                        height=dp(int(60 * 800 / window_size_y)),
                        )
                    )
        except Exception as e:
            toast_msg = f'Gagal reload tabel'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def on_antrian_row_press(self, instance):
        global mydb, db_antrian, db_merk, db_bahan_bakar, db_warna
        global dt_no_antri, dt_no_pol, dt_no_uji, dt_sts_uji
        global dt_merk, dt_type, dt_jns_kend, dt_jbb, dt_brt_ksg, dt_bhn_bkr, dt_warna, dt_speed_flag, dt_sideslip_flag
        global dt_id_user, dt_foto_user

        try:
            row = int(str(instance.id).replace("card_antrian",""))
            dt_no_antri             = db_antrian[0, row]
            dt_no_pol               = db_antrian[1, row]
            dt_no_uji               = db_antrian[2, row]
            dt_sts_uji              = db_antrian[3, row]
            dt_merk                 = db_antrian[4, row]
            dt_type                 = db_antrian[5, row]
            dt_jns_kend             = db_antrian[6, row]
            dt_jbb                  = db_antrian[7, row]
            dt_brt_ksg              = db_antrian[8, row]
            dt_bhn_bkr              = db_antrian[9, row]
            dt_warna                = db_antrian[10, row]
            dt_speed_flag           = db_antrian[11, row]
            dt_sideslip_flag        = db_antrian[12, row]

            self.exec_navigate_menu()

        except Exception as e:
            toast_msg = f'Gagal mengeksekusi perintah dari baris tabel'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")          

    def exec_logout(self):
        global dt_user

        log_audit("LOGOUT", f"user={dt_user}")
        dt_user = ""
        self.screen_manager.current = 'screen_login'

    def exec_navigate_home(self):
        try:
            self.screen_manager.current = 'screen_home'

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat berpindah ke halaman Beranda'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")   

    def exec_navigate_login(self):
        global dt_user
        try:
            if (dt_user == ""):
                self.screen_manager.current = 'screen_login'
            else:
                toast_msg = f"Anda sudah login sebagai {dt_user}"
                toast(toast_msg)
                Logger.info(f"{self.name}: {toast_msg}")

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat berpindah ke halaman Login'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")      

    def exec_navigate_menu(self):
        global dt_speed_flag, dt_sideslip_flag, dt_no_antri, dt_user

        if (dt_user != ''):
            if (int(dt_speed_flag) == 2 or int(dt_sideslip_flag) == 2):
                self.screen_manager.current = 'screen_menu'
            else:
                toast_msg = f'No. Antrian {dt_no_antri} Sudah Tes'
                toast(toast_msg)
                Logger.info(f"{self.name}: {toast_msg}")
        else:
            toast_msg = f'Silahkan Login Untuk Melakukan Pengujian'
            toast(toast_msg)
            Logger.info(f"{self.name}: {toast_msg}")    

    def exec_navigate_calibration(self):
        global dt_user
        try:
            self.screen_manager.current = 'screen_calibration'

        except Exception as e:
            toast_msg = f'Error Navigate to Calibration Screen: {e}'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_navigate_add_data(self):
        global dt_user
        try:
            self.screen_manager.current = 'screen_add_data'

        except Exception as e:
            toast_msg = f'Error Navigate to Add Data Screen: {e}'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_navigate_add_queue(self):
        global dt_user
        try:
            self.screen_manager.current = 'screen_add_queue'

        except Exception as e:
            toast_msg = f'Error Navigate to Add Queue Screen: {e}'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_navigate_main(self):
        try:
            self.screen_manager.current = 'screen_main'

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat berpindah ke halaman Utama'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")    

class ScreenCalibration(MDScreen):
    def __init__(self, **kwargs):
        super(ScreenCalibration, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, 1)
    
    def delayed_init(self, dt):
        self.ids.lb_title.text = APP_TITLE
        self.ids.lb_subtitle.text = APP_SUBTITLE
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS

    def on_enter(self):
        pass

    def on_leave(self):
        pass

    def exec_calibrate_default_ppr_speed(self):
        global flag_conn_stat
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3077, True, slave=1) #M5
                MODBUS_CLIENT.close()
        except Exception as e:
            toast_msg = f"error send exec_calibrate_default_ppr_speed data to PLC Slave"
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def rel_calibrate_default_ppr_speed(self):
        global flag_conn_stat
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3077, False, slave=1) #M5
                MODBUS_CLIENT.close()
        except Exception as e:
            toast_msg = f"error send rel_calibrate_default_ppr_speed data to PLC Slave"
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_calibrate_ppr_speed(self):
        global flag_conn_stat
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_register(1522, int(self.ids.tx_calibrate_ppr_speed.text), slave=1) #V1010
                MODBUS_CLIENT.close()
        except Exception as e:
            toast_msg = f"error send exec_calibrate_ppr_speed data to PLC Slave"
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_calibrate_default_ppr_sideslip(self):
        global flag_conn_stat
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3067, True, slave=1) #M15
                MODBUS_CLIENT.close()
        except Exception as e:
            toast_msg = f"error send exec_calibrate_default_ppr_sideslip data to PLC Slave"
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def rel_calibrate_default_ppr_sideslip(self):
        global flag_conn_stat
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3067, False, slave=1) #M15
                MODBUS_CLIENT.close()
        except Exception as e:
            toast_msg = f"error send rel_calibrate_default_ppr_sideslip data to PLC Slave"
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_calibrate_ppr_sideslip(self):
        global flag_conn_stat
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_register(1622, int(self.ids.tx_calibrate_ppr_sideslip.text), slave=1) #V1110
                MODBUS_CLIENT.close()
        except Exception as e:
            toast_msg = f"error send exec_calibrate_ppr_sideslip data to PLC Slave"
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_cylinder_up(self):
        global flag_conn_stat, flag_cylinder

        if(not flag_cylinder):
            flag_cylinder = True
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3073, flag_cylinder, slave=1) #M1
                MODBUS_CLIENT.close()
        except:
            toast("error send exec_cylinder_up data to PLC Slave") 

    def exec_cylinder_down(self):
        global flag_conn_stat, flag_cylinder

        if(flag_cylinder):
            flag_cylinder = False
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3074, not flag_cylinder, slave=1) #M2
                MODBUS_CLIENT.close()
        except:
            toast("error send exec_cylinder_down data to PLC Slave") 

    def exec_cylinder_stop(self):
        global flag_conn_stat

        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3073, False, slave=1) #M1
                MODBUS_CLIENT.write_coil(3074, False, slave=1) #M3
                MODBUS_CLIENT.close()
        except:
            toast("error send exec_cylinder_stop data to PLC Slave")   

    def exec_navigate_main(self):
        try:
            self.screen_manager.current = 'screen_main'

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat berpindah ke halaman Utama'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

class ScreenAddData(MDScreen):
    def __init__(self, **kwargs):
        super(ScreenAddData, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, 1)
    
    def delayed_init(self, dt):
        self.ids.lb_title.text = APP_TITLE
        self.ids.lb_subtitle.text = APP_SUBTITLE
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS

    def on_enter(self):
        pass

    def on_leave(self):
        pass

    def exec_cancel(self):
        try:
            self.screen_manager.current = 'screen_main'

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat berpindah ke halaman Utama'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_register(self):
        global mydb, db_users, db_merk, db_bahan_bakar, db_warna
        global dt_id_user, dt_user, dt_foto_user
        global dt_dash_pendaftaran
        global dt_temp_no_uji, dt_temp_no_uji_new, dt_temp_no_wilayah, dt_temp_no_kendaraan, dt_temp_no_plat, dt_temp_no_pol
        global dt_temp_nama, dt_temp_no_hp, dt_temp_alamat, dt_temp_id_izin, dt_temp_wilayah, dt_temp_provinsi, dt_temp_kabupaten_kota, dt_temp_kecamatan
        global dt_temp_id_merk, dt_temp_id_subjenis, dt_temp_type, dt_temp_tahun_buat, dt_temp_silinder, dt_temp_warna, dt_temp_chasis, dt_temp_mesin, dt_temp_warna_plat
        global dt_temp_bhn_bkr, dt_temp_jbb, dt_temp_brt_ksg, dt_temp_daya_motor, dt_temp_tgl_uji_terakhir, dt_temp_tgl_uji_habis, dt_temp_status_uji, dt_temp_status_penerbitan, dt_temp_jenis_kendaraan, dt_temp_kode_jenis_kendaraan, dt_temp_kode_wilayah

        dt_tgl_baru_uji = str(time.strftime("%Y/%m/%d %H:%M:%S", time.localtime()))

        try:
            ensure_db_connected()
            mycursor = mydb.cursor()
            sql = f"INSERT INTO {TB_DATA_MASTER} (NOUJI, NEW_NOUJI, NOPOL, MERK_ID, TYPE, idjeniskendaraan, kd_jnskendaraan, WLY, SUBJENIS_ID, JBB, BERATKOSONG, BHN_BAKAR, WARNA_KEND, STATUSUJI, statuspenerbitan, PLAT, NOKDR, NOWIL, TGL_UJI_TERAKHIR) VALUES ('{dt_temp_no_uji}','{dt_temp_no_uji_new}','{dt_temp_no_pol}','{dt_temp_id_merk}','{dt_temp_type}','{dt_temp_jenis_kendaraan}','{dt_temp_kode_jenis_kendaraan}','{dt_temp_kode_wilayah}','{dt_temp_id_subjenis}','{dt_temp_jbb}','{dt_temp_brt_ksg}','{dt_temp_bhn_bkr}','{dt_temp_warna}','{dt_temp_status_uji}','{dt_temp_status_penerbitan}','{dt_temp_no_wilayah}','{dt_temp_no_kendaraan}','{dt_temp_no_plat}','{dt_tgl_baru_uji}')"
            mycursor.execute(sql)
            mydb.commit()

            toast("Data berhasil didaftarkan")
            self.screen_manager.current = 'screen_main'

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat mendaftar'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}") 

class ScreenAddQueue(MDScreen):
    def __init__(self, **kwargs):
        super(ScreenAddQueue, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, 1)
    
    def delayed_init(self, dt):
        self.ids.lb_title.text = APP_TITLE
        self.ids.lb_subtitle.text = APP_SUBTITLE
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS

    def on_enter(self):
        pass

    def on_leave(self):
        pass

    def exec_cancel(self):
        global dt_temp_no_uji, dt_temp_no_uji_new, dt_temp_no_wilayah, dt_temp_no_kendaraan, dt_temp_no_plat, dt_temp_no_pol
        global dt_temp_nama, dt_temp_no_hp, dt_temp_alamat, dt_temp_id_izin, dt_temp_wilayah, dt_temp_provinsi, dt_temp_kabupaten_kota, dt_temp_kecamatan
        global dt_temp_id_merk, dt_temp_id_subjenis, dt_temp_type, dt_temp_tahun_buat, dt_temp_silinder, dt_temp_warna, dt_temp_chasis, dt_temp_mesin, dt_temp_warna_plat
        global dt_temp_bhn_bkr, dt_temp_jbb, dt_temp_daya_motor, dt_temp_tgl_uji_terakhir, dt_temp_tgl_uji_habis, dt_temp_status_uji, dt_temp_status_penerbitan, dt_temp_jenis_kendaraan, dt_temp_kode_jenis_kendaraan, dt_temp_kode_wilayah

        try:
            dt_temp_no_uji = dt_temp_no_uji_new = dt_temp_no_wilayah = dt_temp_no_kendaraan = dt_temp_no_plat = dt_temp_no_pol = ""
            dt_temp_nama = dt_temp_no_hp = dt_temp_alamat = dt_temp_id_izin = dt_temp_wilayah = dt_temp_provinsi = dt_temp_kabupaten_kota = dt_temp_kecamatan = ""
            dt_temp_id_merk = dt_temp_id_subjenis = dt_temp_type = dt_temp_tahun_buat = dt_temp_silinder = dt_temp_warna = dt_temp_chasis = dt_temp_mesin = dt_temp_warna_plat = ""
            dt_temp_bhn_bkr = dt_temp_jbb = dt_temp_daya_motor = dt_temp_tgl_uji_terakhir = dt_temp_tgl_uji_habis = dt_temp_status_uji = dt_temp_status_penerbitan = dt_temp_jenis_kendaraan = dt_temp_kode_jenis_kendaraan = dt_temp_kode_wilayah = ""

            self.ids.tx_nopol.text = "" 
            self.ids.tx_nouji.text = "" 
            self.ids.lb_temp_nama.text = self.ids.lb_temp_alamat.text = ""
            self.ids.lb_temp_no_uji.text = self.ids.lb_temp_no_pol.text = self.ids.lb_temp_status_uji.text = self.ids.lb_temp_tgl_uji_terakhir.text = self.ids.lb_temp_tgl_uji_habis.text = ""
            self.ids.lb_temp_merk.text = self.ids.lb_temp_type.text = self.ids.lb_temp_jenis_kendaraan.text = self.ids.lb_temp_warna.text = ""
            self.ids.lb_temp_chasis.text = self.ids.lb_temp_mesin.text = self.ids.lb_temp_bahan_bakar.text = self.ids.lb_temp_jbb.text = ""
            self.ids.bt_register.disabled = True

            self.exec_navigate_main()
            
        except Exception as e:
            toast_msg = f'Gagal Memuat Data'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}") 

    def exec_find(self):
        global mydb, db_users, db_merk, db_bahan_bakar, db_warna
        global dt_id_user, dt_user, dt_foto_user
        global dt_temp_no_uji, dt_temp_no_uji_new, dt_temp_no_wilayah, dt_temp_no_kendaraan, dt_temp_no_plat, dt_temp_no_pol
        global dt_temp_nama, dt_temp_no_hp, dt_temp_alamat, dt_temp_id_izin, dt_temp_wilayah, dt_temp_provinsi, dt_temp_kabupaten_kota, dt_temp_kecamatan
        global dt_temp_id_merk, dt_temp_id_subjenis, dt_temp_type, dt_temp_tahun_buat, dt_temp_silinder, dt_temp_warna, dt_temp_chasis, dt_temp_mesin, dt_temp_warna_plat
        global dt_temp_bhn_bkr, dt_temp_jbb, dt_temp_daya_motor, dt_temp_tgl_uji_terakhir, dt_temp_tgl_uji_habis, dt_temp_status_uji, dt_temp_status_penerbitan, dt_temp_jenis_kendaraan, dt_temp_kode_jenis_kendaraan, dt_temp_kode_wilayah

        try:
            dt_find_no_pol = self.ids.tx_nopol.text
            dt_find_no_uji = self.ids.tx_nouji.text
            self.exec_fetch_master_data(dt_find_no_pol, dt_find_no_uji)

            self.ids.lb_temp_nama.text = f'{dt_temp_nama}'
            self.ids.lb_temp_alamat.text = f'{dt_temp_alamat}'
            self.ids.lb_temp_no_uji.text = f'{dt_temp_no_uji}'
            self.ids.lb_temp_no_pol.text = f'{dt_temp_no_pol}'
            self.ids.lb_temp_status_uji.text = 'Berkala' if dt_temp_status_uji == 'B' else 'Uji Ulang' if dt_temp_status_uji == 'U' else 'Baru' if dt_temp_status_uji == 'BR' else 'Numpang Uji' if dt_temp_status_uji == 'NB' else 'Mutasi'
            self.ids.lb_temp_tgl_uji_terakhir.text = f'{dt_temp_tgl_uji_terakhir}'
            self.ids.lb_temp_tgl_uji_habis.text = f'{dt_temp_tgl_uji_habis}'
            self.ids.lb_temp_merk.text = '-' if dt_temp_id_merk == None else f"{db_merk[np.where(db_merk == dt_temp_id_merk)[0][0],1]}"
            self.ids.lb_temp_type.text = f'{dt_temp_type}'
            self.ids.lb_temp_jenis_kendaraan.text = f'{dt_temp_jenis_kendaraan}'
            self.ids.lb_temp_warna.text = '-' if dt_temp_warna == None else f"{db_warna[np.where(db_warna == dt_temp_warna)[0][0],1]}"
            self.ids.lb_temp_chasis.text = f'{dt_temp_chasis}'
            self.ids.lb_temp_mesin.text = f'{dt_temp_mesin}'
            self.ids.lb_temp_bahan_bakar.text = '-' if dt_temp_bhn_bkr == None else f"{db_bahan_bakar[np.where(db_bahan_bakar == dt_temp_bhn_bkr)[0][0],1]}"
            self.ids.lb_temp_jbb.text = f'{dt_temp_jbb}'
            self.ids.lb_temp_berat_kosong.text = f'{dt_temp_brt_ksg}'
            self.ids.bt_register.disabled = False
            
        except Exception as e:
            toast_msg = f'Gagal Menemukan Data, Silahkan Isi Nomor Uji atau Nomor Polisi dengan Benar'
            toast(toast_msg)
            print(toast_msg, e)

    def exec_fetch_master_data(self, dt_find_no_pol, dt_find_no_uji):
        global mydb, db_users, db_merk, db_bahan_bakar, db_warna
        global dt_id_user, dt_user, dt_foto_user
        global dt_temp_no_uji, dt_temp_no_uji_new, dt_temp_no_wilayah, dt_temp_no_kendaraan, dt_temp_no_plat, dt_temp_no_pol
        global dt_temp_nama, dt_temp_no_hp, dt_temp_alamat, dt_temp_id_izin, dt_temp_wilayah, dt_temp_provinsi, dt_temp_kabupaten_kota, dt_temp_kecamatan
        global dt_temp_id_merk, dt_temp_id_subjenis, dt_temp_type, dt_temp_tahun_buat, dt_temp_silinder, dt_temp_warna, dt_temp_chasis, dt_temp_mesin, dt_temp_warna_plat
        global dt_temp_bhn_bkr, dt_temp_jbb, dt_temp_brt_ksg, dt_temp_daya_motor, dt_temp_tgl_uji_terakhir, dt_temp_tgl_uji_habis, dt_temp_status_uji, dt_temp_status_penerbitan, dt_temp_jenis_kendaraan, dt_temp_kode_jenis_kendaraan, dt_temp_kode_wilayah

        try:
            ensure_db_connected()
            mycursor = mydb.cursor()
            if dt_find_no_pol != "" and dt_find_no_uji == "":
                mycursor.execute(f"SELECT NOUJI, NEW_NOUJI, NOWIL, NOKDR, PLAT, NOPOL, NAMA, NOHP, ALAMAT, ID_IZIN, WLY, PROP, KABKOT, KEC, MERK_ID, SUBJENIS_ID, TYPE, TH_BUAT, SILINDER, WARNA_KEND, CHASIS, MESIN, WARNA_PLAT, BHN_BAKAR, JBB, BERATKOSONG, DAYAMOTOR, TGL_UJI_TERAKHIR, STATUSUJI, statuspenerbitan, idjeniskendaraan, kd_jnskendaraan, kodewilayah FROM {TB_DATA_MASTER} WHERE NOPOL = '{dt_find_no_pol}' ")
            elif dt_find_no_uji != "":
                mycursor.execute(f"SELECT NOUJI, NEW_NOUJI, NOWIL, NOKDR, PLAT, NOPOL, NAMA, NOHP, ALAMAT, ID_IZIN, WLY, PROP, KABKOT, KEC, MERK_ID, SUBJENIS_ID, TYPE, TH_BUAT, SILINDER, WARNA_KEND, CHASIS, MESIN, WARNA_PLAT, BHN_BAKAR, JBB, BERATKOSONG, DAYAMOTOR, TGL_UJI_TERAKHIR, STATUSUJI, statuspenerbitan, idjeniskendaraan, kd_jnskendaraan, kodewilayah FROM {TB_DATA_MASTER} WHERE NOUJI = '{dt_find_no_uji}' ")
            elif dt_find_no_uji == "" and dt_find_no_pol == "":
                toast("Silahkan Isi Nomor Uji atau Nomor Polisi dengan Benar")
            myresult = mycursor.fetchone()
            mydb.commit()
            db_master_data = np.array(myresult).T

            if myresult is None:
                toast('Data Tidak Ditemukan di Database, Silahkan Ajukan Pengujian Baru')
                self.exec_cancel()
            else:
                dt_temp_no_uji = db_master_data[0]
                dt_temp_no_uji_new = db_master_data[1]
                dt_temp_no_wilayah = db_master_data[2]
                dt_temp_no_kendaraan = db_master_data[3]
                dt_temp_no_plat = db_master_data[4]
                dt_temp_no_pol = db_master_data[5]
                dt_temp_nama = db_master_data[6]
                dt_temp_no_hp = db_master_data[7]
                dt_temp_alamat = db_master_data[8]
                dt_temp_id_izin = db_master_data[9]
                dt_temp_wilayah = db_master_data[10]
                dt_temp_provinsi = db_master_data[11]
                dt_temp_kabupaten_kota = db_master_data[12]
                dt_temp_kecamatan = db_master_data[13]
                dt_temp_id_merk = db_master_data[14]
                dt_temp_id_subjenis = db_master_data[15]
                dt_temp_type = db_master_data[16]
                dt_temp_tahun_buat = db_master_data[17]
                dt_temp_silinder = db_master_data[18]
                dt_temp_warna = db_master_data[19]
                dt_temp_chasis = db_master_data[20]
                dt_temp_mesin = db_master_data[21]
                dt_temp_warna_plat = db_master_data[22]
                dt_temp_bhn_bkr = db_master_data[23]
                dt_temp_jbb = db_master_data[24]
                dt_temp_brt_ksg = db_master_data[25]
                dt_temp_daya_motor = db_master_data[26]
                
                dt_temp_status_uji = db_master_data[28]
                dt_temp_status_penerbitan = db_master_data[29]
                dt_temp_jenis_kendaraan = db_master_data[30]
                dt_temp_kode_jenis_kendaraan = db_master_data[31]
                dt_temp_kode_wilayah = db_master_data[32]

                if(db_master_data[26] is not None):
                    last_uji_date = db_master_data[27]
                else:
                    last_uji_date = datetime.datetime(1900, 1, 1)

                if(last_uji_date.month <= 6):
                    year_replaced = last_uji_date.year
                    month_replaced = last_uji_date.month + 6
                    day_replaced = last_uji_date.day
                else:
                    year_replaced = last_uji_date.year + 1
                    month_replaced = last_uji_date.month - 6
                    day_replaced = last_uji_date.day
                
                if(last_uji_date.day > 29):
                    if month_replaced == 2:
                        day_replaced = 29
                    if month_replaced == 4 or month_replaced == 6 or month_replaced == 9 or month_replaced == 11:
                        day_replaced = 30
                    
                dt_temp_tgl_uji_terakhir = str(last_uji_date.strftime('%d-%m-%Y'))
                dt_temp_tgl_uji_habis = str(last_uji_date.replace(month=month_replaced, year=year_replaced, day=day_replaced).strftime('%d-%m-%Y'))
                
        except Exception as e:
            toast_msg = f'Gagal Menemukan Data dari Database Master'
            toast(toast_msg)
            print(toast_msg, e)

    def exec_register(self):
        global mydb, db_users, db_merk, db_bahan_bakar, db_warna
        global dt_id_user, dt_user, dt_foto_user
        global dt_dash_pendaftaran
        global dt_temp_no_uji, dt_temp_no_uji_new, dt_temp_no_wilayah, dt_temp_no_kendaraan, dt_temp_no_plat, dt_temp_no_pol
        global dt_temp_nama, dt_temp_no_hp, dt_temp_alamat, dt_temp_id_izin, dt_temp_wilayah, dt_temp_provinsi, dt_temp_kabupaten_kota, dt_temp_kecamatan
        global dt_temp_id_merk, dt_temp_id_subjenis, dt_temp_type, dt_temp_tahun_buat, dt_temp_silinder, dt_temp_warna, dt_temp_chasis, dt_temp_mesin, dt_temp_warna_plat
        global dt_temp_bhn_bkr, dt_temp_jbb, dt_temp_brt_ksg, dt_temp_daya_motor, dt_temp_tgl_uji_terakhir, dt_temp_tgl_uji_habis, dt_temp_status_uji, dt_temp_status_penerbitan, dt_temp_jenis_kendaraan, dt_temp_kode_jenis_kendaraan, dt_temp_kode_wilayah

        try:
            ensure_db_connected()
            mycursor = mydb.cursor()
            mycursor.execute(f"SELECT MAX(noantrian) FROM {TB_DATA}")
            result = mycursor.fetchone()
            last_noantrian = int(result[0]) if result[0] is not None else 0
            noantrian = f"{last_noantrian + 1:04d}"

            nopol = self.ids.tx_nopol.text
            nouji = self.ids.tx_nouji.text
            merk = self.ids.tx_merk.text
            tipe = self.ids.tx_type.text
            idjeniskendaraan = self.ids.tx_idjeniskendaraan.text
            jbb = self.ids.tx_jbb.text
            berat_kosong = self.ids.tx_berat_kosong.text
            warna = self.ids.tx_warna.text

            mycursor = mydb.cursor()
            sql = f"INSERT INTO {TB_DATA} (noantrian, nopol, nouji, NEW_NOUJI, merk, type, idjeniskendaraan, jbb, berat_kosong, warna) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            values = (noantrian, nopol, nouji, nouji, merk, tipe, idjeniskendaraan, jbb, berat_kosong, warna)
            mycursor.execute(sql, values)
            mydb.commit()

        except Exception as e:
            toast_msg = f'Gagal menambah data antrian baru'
            toast(toast_msg)
            print(toast_msg, e)

        self.exec_cancel()

    def exec_navigate_home(self):
        try:
            self.screen_manager.current = 'screen_home'

        except Exception as e:
            toast_msg = f'Gagal Berpindah ke Halaman Awal'
            toast(toast_msg)
            print(toast_msg, e)

    def exec_navigate_login(self):
        global dt_user
        try:
            if (dt_user == ""):
                self.screen_manager.current = 'screen_login'
            else:
                toast(f"Anda sudah login sebagai {dt_user}")

        except Exception as e:
            toast_msg = f'Gagal Berpindah ke Halaman Login'
            toast(toast_msg)
            print(toast_msg, e)

    def exec_navigate_main(self):
        try:
            self.screen_manager.current = 'screen_main'

        except Exception as e:
            toast_msg = f'Gagal Berpindah ke Halaman Utama'
            toast(toast_msg)
            print(toast_msg, e)

class ScreenMenu(MDScreen):        
    def __init__(self, **kwargs):
        super(ScreenMenu, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, 1)        

    def delayed_init(self, dt):
        self.ids.lb_title.text = APP_TITLE
        self.ids.lb_subtitle.text = APP_SUBTITLE        
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS

    def on_enter(self):
        global db_merk, db_bahan_bakar, db_warna
        global dt_no_antri, dt_no_pol, dt_no_uji, dt_sts_uji
        global dt_merk, dt_type, dt_jns_kend, dt_jbb, dt_brt_ksg, dt_bhn_bkr, dt_warna, dt_speed_flag

        self.ids.lb_no_antri.text = str(dt_no_antri)
        self.ids.lb_no_pol.text = str(dt_no_pol)
        self.ids.lb_no_uji.text = str(dt_no_uji)
        self.ids.lb_sts_uji.text = 'Berkala' if dt_sts_uji == 'B' else 'Uji Ulang' if dt_sts_uji == 'U' else 'Baru' if dt_sts_uji == 'BR' else 'Numpang Uji' if dt_sts_uji == 'NB' else 'Mutasi'
        self.ids.lb_merk.text = '-' if dt_merk == None else f"{db_merk[np.where(db_merk == dt_merk)[0][0],1]}"
        self.ids.lb_type.text = str(dt_type)
        self.ids.lb_jns_kend.text = str(dt_jns_kend)
        self.ids.lb_jbb.text = str(dt_jbb)
        self.ids.lb_brt_ksg.text = str(dt_brt_ksg)
        self.ids.lb_bhn_bkr.text = '-' if dt_bhn_bkr == None else f"{db_bahan_bakar[np.where(db_bahan_bakar == dt_bhn_bkr)[0][0],1]}"
        self.ids.lb_warna.text = '-' if dt_warna == None else f"{db_warna[np.where(db_warna == dt_warna)[0][0],1]}"

    def exec_start_speed(self):
        global flag_play
        global count_starting, count_get_data

        screen_main = self.screen_manager.get_screen('screen_main')

        count_starting = COUNT_STARTING_SPEED
        count_get_data = COUNT_ACQUISITION_SPEED

        if(not flag_play):
            Clock.schedule_interval(screen_main.regular_get_data, GET_DATA_INTERVAL)
            self.open_screen_speed_meter()
            flag_play = True
            log_audit("TEST_START_SPEED", f"antrian={dt_no_antri} nopol={dt_no_pol} user={dt_user} simulation={SIMULATION_MODE}")

    def exec_start_sideslip(self):
        global flag_play
        global count_starting, count_get_data

        screen_main = self.screen_manager.get_screen('screen_main')

        count_starting = COUNT_STARTING_SIDESLIP
        count_get_data = COUNT_ACQUISITION_SIDESLIP

        if(not flag_play):
            Clock.schedule_interval(screen_main.regular_get_data, GET_DATA_INTERVAL)
            self.open_screen_sideslip_meter()
            flag_play = True
            log_audit("TEST_START_SIDESLIP", f"antrian={dt_no_antri} nopol={dt_no_pol} user={dt_user} simulation={SIMULATION_MODE}")

    def exec_navigate_main(self):
        try:
            self.screen_manager.current = 'screen_main'

        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat berpindah ke halaman Utama'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def open_screen_speed_meter(self):
        self.screen_manager.current = 'screen_speed_meter'

    def open_screen_sideslip_meter(self):
        self.screen_manager.current = 'screen_sideslip_meter'

class ScreenSpeedMeter(MDScreen):        
    def __init__(self, **kwargs):
        super(ScreenSpeedMeter, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, 1)
    
    def delayed_init(self, dt):
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS

    def on_enter(self):
        global db_merk, db_bahan_bakar, db_warna
        global dt_no_antri, dt_no_pol, dt_no_uji, dt_sts_uji
        global dt_merk, dt_type, dt_jns_kend, dt_jbb, dt_brt_ksg, dt_bhn_bkr, dt_warna, dt_speed_flag

        self.ids.lb_no_antri.text = str(dt_no_antri)
        self.ids.lb_no_pol.text = str(dt_no_pol)
        self.ids.lb_no_uji.text = str(dt_no_uji)
        self.ids.lb_sts_uji.text = 'Berkala' if dt_sts_uji == 'B' else 'Uji Ulang' if dt_sts_uji == 'U' else 'Baru' if dt_sts_uji == 'BR' else 'Numpang Uji' if dt_sts_uji == 'NB' else 'Mutasi'
        self.ids.lb_merk.text = '-' if dt_merk == None else f"{db_merk[np.where(db_merk == dt_merk)[0][0],1]}"
        self.ids.lb_type.text = str(dt_type)
        self.ids.lb_jns_kend.text = str(dt_jns_kend)
        self.ids.lb_jbb.text = str(dt_jbb)
        self.ids.lb_brt_ksg.text = str(dt_brt_ksg)
        self.ids.lb_bhn_bkr.text = '-' if dt_bhn_bkr == None else f"{db_bahan_bakar[np.where(db_bahan_bakar == dt_bhn_bkr)[0][0],1]}"
        self.ids.lb_warna.text = '-' if dt_warna == None else f"{db_warna[np.where(db_warna == dt_warna)[0][0],1]}"
        
        self.exec_start_speed()
        
    def exec_cylinder_up(self):
        global flag_conn_stat, flag_cylinder

        if(not flag_cylinder):
            flag_cylinder = True
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3073, flag_cylinder, slave=1) #M1
                MODBUS_CLIENT.close()
        except:
            toast("error send exec_cylinder_up data to PLC Slave") 

    def exec_cylinder_down(self):
        global flag_conn_stat, flag_cylinder

        if(flag_cylinder):
            flag_cylinder = False
        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3074, not flag_cylinder, slave=1) #M2
                MODBUS_CLIENT.close()
        except:
            toast("error send exec_cylinder_down data to PLC Slave") 

    def exec_cylinder_stop(self):
        global flag_conn_stat

        try:
            if flag_conn_stat and not SIMULATION_MODE:
                MODBUS_CLIENT.connect()
                MODBUS_CLIENT.write_coil(3073, False, slave=1) #M1
                MODBUS_CLIENT.write_coil(3074, False, slave=1) #M3
                MODBUS_CLIENT.close()
        except:
            toast("error send exec_cylinder_stop data to PLC Slave")    

    def exec_start_speed(self):
        global flag_play
        global count_starting, count_get_data
        try:
            screen_main = self.screen_manager.get_screen('screen_main')
            count_starting = COUNT_STARTING_SPEED
            count_get_data = COUNT_ACQUISITION_SPEED

            if(not flag_play):
                Clock.schedule_interval(screen_main.regular_get_data, GET_DATA_INTERVAL)
                flag_play = True
        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat memulai pengujian Speedo Meter'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_reload(self):
        global flag_play
        global count_starting, count_get_data, dt_speed_value
        try:
            screen_main = self.screen_manager.get_screen('screen_main')
            count_starting = COUNT_STARTING_SPEED
            count_get_data = COUNT_ACQUISITION_SPEED
            dt_speed_value = 0
            self.ids.bt_reload.disabled = True
            self.ids.lb_speed_val.text = "..."

            if(not flag_play):
                Clock.schedule_interval(screen_main.regular_get_data, GET_DATA_INTERVAL)
                flag_play = True
        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat memulai ulang pengujian Speedo Meter'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_save(self):
        global mydb, db_antrian
        global dt_no_antri, dt_no_pol, dt_no_uji, dt_nama
        global dt_speed_flag, dt_speed_value, dt_id_user

        self.ids.bt_save.disabled = True
        try:
            ensure_db_connected()
            tb_speed_data = mydb.cursor()
            sql = f"UPDATE {TB_DATA} SET speed_flag = %s, speed_value = %s, speed_user = %s, speed_post = %s WHERE noantrian = %s"
            sql_speed_flag = dt_speed_flag
            now = str(time.strftime("%Y/%m/%d %H:%M:%S", time.localtime()))
            sql_val = (sql_speed_flag, dt_speed_value, dt_id_user, now, dt_no_antri)
            tb_speed_data.execute(sql, sql_val)
            mydb.commit()
            toast("Data Speedometer Berhasil Disimpan")
            log_audit("SAVE_SPEED", f"antrian={dt_no_antri} nopol={dt_no_pol} value={dt_speed_value} flag={dt_speed_flag} user={dt_id_user} simulation={SIMULATION_MODE}")
            self.exec_print_pdf()
            self.open_screen_main()

            self.ids.bt_save.disabled = True

        except Exception as e:
            toast_msg = f'Gagal Menyimpan data'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")
            log_audit("SAVE_SPEED_FAILED", f"antrian={dt_no_antri} error={e}")

    def exec_print(self):
        try:
            global dt_speed_flag
            ensure_db_connected()
            tb_status = mydb.cursor()
            tb_status.execute(f"SELECT speed_flag FROM {TB_DATA} WHERE noantrian = '{dt_no_antri}'")
            result_tb_status = tb_status.fetchone()
            mydb.commit()
            db_status = np.array(result_tb_status).T
            dt_speed_flag = int(db_status[0])

            self.exec_print_pdf()

            self.ids.bt_print.disabled = True

        except Exception as e:
            toast_msg = f'Gagal Mencetak Hasil Uji'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_print_pdf(self):
        global flag_play
        global count_starting, count_get_data
        global mydb, db_antrian
        global dt_no_antri, dt_no_pol, dt_no_uji, dt_nama, dt_jns_kend
        global dt_speed_flag

        try:
            print_datetime = str(time.strftime("%Y/%m/%d %H:%M:%S", time.localtime()))
            pdf = FPDF()
            pdf.add_page()
            page_w = pdf.w
            margin = pdf.l_margin
            content_w = page_w - 2 * margin

            # --- Header ---
            logo_left = pdf.image(f"assets/images/{IMG_LOGO_DISHUB}", x=margin, y=10, w=26.0)
            logo_right = pdf.image(f"assets/images/{IMG_LOGO_PEMKAB}", x=page_w - margin - 26.0, y=10, w=26.0)
            pdf.set_y(10)
            pdf.set_font('Arial', 'B', 18)
            pdf.cell(0, 8, text="DINAS PERHUBUNGAN", align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Arial', 'B', 13)
            pdf.cell(0, 7, text="UPTD PKB KAB. PANDEGLANG", align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Arial', '', 11)
            pdf.cell(0, 6, text="HASIL UJI SPEEDO METER", align='C', new_x="LMARGIN", new_y="NEXT")
            logo_bottom = 10 + max(logo_left.rendered_height, logo_right.rendered_height)
            pdf.set_y(max(pdf.get_y(), logo_bottom) + 3)
            pdf.set_draw_color(120, 120, 120)
            pdf.set_line_width(0.4)
            pdf.line(margin, pdf.get_y(), page_w - margin, pdf.get_y())
            pdf.ln(6)

            # --- Identitas kendaraan (2 kolom) ---
            pdf.set_font('Arial', '', 11)
            col_w = content_w / 2
            pdf.cell(col_w, 7, text=f"Tanggal          : {print_datetime}")
            pdf.cell(col_w, 7, text=f"No Reg Kendaraan : {dt_no_pol}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(col_w, 7, text=f"No Antrian       : {dt_no_antri}")
            pdf.cell(col_w, 7, text=f"No Uji           : {dt_no_uji}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(col_w, 7, text=f"Nama             : {dt_nama}")
            pdf.cell(col_w, 7, text=f"JBB              : {dt_jbb} kg", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(col_w, 7, text=f"Berat Kosong     : {float(dt_brt_ksg)} kg", new_x="LMARGIN", new_y="NEXT")
            # baris lentur - kalau jenis kendaraan panjang, teks turun ke baris berikutnya
            pdf.multi_cell(content_w, 7, text=f"Jenis Kendaraan  : {dt_jns_kend}", align='L', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
            pdf.set_draw_color(120, 120, 120)
            pdf.line(margin, pdf.get_y(), page_w - margin, pdf.get_y())
            pdf.ln(8)

            # --- Hasil pengujian ---
            pdf.set_font('Arial', 'B', 15)
            pdf.cell(0, 8, text="SPEEDO METER", align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 7, text=f"Nilai Pengujian : {float(dt_speed_value)} rpm", align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

            if int(dt_speed_flag) == 1:
                status_text, fill_rgb, text_rgb = "LULUS", (211, 240, 216), (30, 120, 40)
            elif int(dt_speed_flag) == 0:
                status_text, fill_rgb, text_rgb = "TIDAK LULUS", (248, 210, 210), (170, 30, 30)
            else:
                status_text, fill_rgb, text_rgb = "BELUM DIUJI", (230, 230, 230), (90, 90, 90)

            box_w = 90.0
            pdf.set_x((page_w - box_w) / 2)
            pdf.set_draw_color(*text_rgb)
            pdf.set_fill_color(*fill_rgb)
            pdf.set_text_color(*text_rgb)
            pdf.set_font('Arial', 'B', 22)
            pdf.cell(box_w, 16, text=status_text, align='C', border=1, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(24)

            pdf.set_font('Arial', 'I', 8)
            pdf.set_text_color(130, 130, 130)
            pdf.cell(0, 5, text="Dicetak otomatis oleh sistem VIIMS", align='C')
            pdf.set_text_color(0, 0, 0)

            documents_dir = os.path.join(os.environ["USERPROFILE"], "Documents")

            folder_name = f"Hasil_Uji_VIIS_Speedo_Meter_{time.strftime('%Y-%m-%d', time.localtime())}"
            date_folder_path = os.path.join(documents_dir, folder_name)

            if not os.path.exists(date_folder_path):
                os.makedirs(date_folder_path)
                toast(f"Folder created: {date_folder_path}")
            else:
                toast(f"Folder already exists: {date_folder_path}")

            pdf_filename = f"Hasil_Uji_No_{dt_no_antri}.pdf"
            pdf_path = os.path.join(date_folder_path, pdf_filename)

            pdf.output(pdf_path, 'F')
            toast(f"PDF saved to: {pdf_path}")
            os.startfile(pdf_path)
            log_audit("PRINT_PDF_SPEED", f"antrian={dt_no_antri} nopol={dt_no_pol} path={pdf_path}")

        except Exception as e:
            toast_msg = f'Gagal menyimpan ke pdf'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")
            log_audit("PRINT_PDF_SPEED_FAILED", f"antrian={dt_no_antri} error={e}")

    # def exec_print_thermal(self):
    #     global flag_play
    #     global count_starting, count_get_data
    #     global mydb, db_antrian
    #     global dt_no_antri, dt_no_pol, dt_no_uji, dt_nama, dt_jns_kend
    #     global dt_speed_flag

    #     try:
    #         """ 9600 Baud, 8N1, Flow Control Enabled """
    #         printer = Serial(devfile=PRINTER_THERM_COM,
    #                 baudrate=PRINTER_THERM_BAUD,
    #                 bytesize=PRINTER_THERM_BYTESIZE,
    #                 parity=PRINTER_THERM_PARITY,
    #                 stopbits=PRINTER_THERM_STOPBITS,
    #                 timeout=PRINTER_THERM_TIMEOUT,
    #                 dsrdtr=PRINTER_THERM_DSRDTR,)
    #         print_datetime = str(time.strftime("%d %B %Y %H:%M:%S", time.localtime()))
            
    #         printer.image("assets/images/logo-dishub.png")
    #         printer.image("assets/images/logo-pandeglang.png")
    #         printer.textln(" \n ")
    #         printer.textln("VEHICLE INSPECTION INTEGRATION SYSTEM")
    #         printer.textln("SPEEDO METER")
    #         printer.textln("================================================================")
    #         printer.text(f"No Antrian: {dt_no_antri}\t")
    #         printer.text(f"No Reg: {dt_no_pol}\t")
    #         printer.textln(f"No Uji: {dt_no_uji}")
    #         printer.textln("  ")
    #         printer.text(f"Nama: {dt_nama}\t")
    #         printer.textln(f"Jenis Kendaraan: {dt_jns_kend}")
    #         printer.textln("  ")
    #         printer.textln(f"Tanggal: {print_datetime}")
    #         printer.textln("  ")
    #         printer.textln(f"SPEEDO METER")
    #         printer.textln(f"Nilai Pengujian : {float(dt_speed_value)} rpm")
    #         printer.textln(f"Status Pengujian : {'Lulus' if int(dt_speed_flag) == 1 else 'Tidak Lulus' if int(dt_speed_flag) == 0 else 'Belum Diuji'}")
    #         printer.textln("  ")
    #         printer.textln("================================================================")
    #         printer.cut()

    #     except Exception as e:
    #         toast_msg = f'Gagal mencetak menggunakan Thermal Printer'
    #         toast(toast_msg)
    #         Logger.error(f"{self.name}: {toast_msg}, {e}")  
            
    def open_screen_main(self):
        global flag_play        
        global count_starting, count_get_data

        try:
            count_starting = COUNT_STARTING_SPEED
            count_get_data = COUNT_ACQUISITION_SPEED
            flag_play = False
            self.screen_manager.current = 'screen_menu'
        except Exception as e:
            toast_msg = f'Gagal Berpindah halaman ke Menu'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

class ScreenSideSlipMeter(MDScreen):        
    def __init__(self, **kwargs):
        super(ScreenSideSlipMeter, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, 1)
    
    def delayed_init(self, dt):
        self.ids.img_pemkab.source = f'assets/images/{IMG_LOGO_PEMKAB}'
        self.ids.img_dishub.source = f'assets/images/{IMG_LOGO_DISHUB}'
        self.ids.lb_pemkab.text = LB_PEMKAB
        self.ids.lb_dishub.text = LB_DISHUB
        self.ids.lb_unit.text = LB_UNIT
        self.ids.lb_unit_address.text = LB_UNIT_ADDRESS

    def on_enter(self):
        global db_merk, db_bahan_bakar, db_warna
        global dt_no_antri, dt_no_pol, dt_no_uji, dt_sts_uji
        global dt_merk, dt_type, dt_jns_kend, dt_jbb, dt_brt_ksg, dt_bhn_bkr, dt_warna, dt_speed_flag

        self.ids.lb_no_antri.text = str(dt_no_antri)
        self.ids.lb_no_pol.text = str(dt_no_pol)
        self.ids.lb_no_uji.text = str(dt_no_uji)
        self.ids.lb_sts_uji.text = 'Berkala' if dt_sts_uji == 'B' else 'Uji Ulang' if dt_sts_uji == 'U' else 'Baru' if dt_sts_uji == 'BR' else 'Numpang Uji' if dt_sts_uji == 'NB' else 'Mutasi'
        self.ids.lb_merk.text = '-' if dt_merk == None else f"{db_merk[np.where(db_merk == dt_merk)[0][0],1]}"
        self.ids.lb_type.text = str(dt_type)
        self.ids.lb_jns_kend.text = str(dt_jns_kend)
        self.ids.lb_jbb.text = str(dt_jbb)
        self.ids.lb_brt_ksg.text = str(dt_brt_ksg)
        self.ids.lb_bhn_bkr.text = '-' if dt_bhn_bkr == None else f"{db_bahan_bakar[np.where(db_bahan_bakar == dt_bhn_bkr)[0][0],1]}"
        self.ids.lb_warna.text = '-' if dt_warna == None else f"{db_warna[np.where(db_warna == dt_warna)[0][0],1]}"
        
        self.exec_start_sideslip()

    def exec_start_sideslip(self):
        global flag_play
        global count_starting, count_get_data
        try:
            screen_main = self.screen_manager.get_screen('screen_main')

            count_starting = COUNT_STARTING_SIDESLIP
            count_get_data = COUNT_ACQUISITION_SIDESLIP

            if(not flag_play):
                Clock.schedule_interval(screen_main.regular_get_data, GET_DATA_INTERVAL)
                flag_play = True            
        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat memulai pengujian Sideslip'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  


    def exec_reload(self):
        global flag_play
        global count_starting, count_get_data, dt_sideslip_value
        try:
            screen_main = self.screen_manager.get_screen('screen_main')
            count_starting = COUNT_STARTING_SIDESLIP
            count_get_data = COUNT_ACQUISITION_SIDESLIP
            dt_sideslip_value = 0
            self.ids.bt_reload.disabled = True
            self.ids.lb_sideslip_val.text = "..."

            if(not flag_play):
                Clock.schedule_interval(screen_main.regular_get_data, GET_DATA_INTERVAL)
                flag_play = True          
        except Exception as e:
            toast_msg = f'Terjadi kesalahan saat memulai ulang pengujian Sideslip'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_save(self):
        global mydb, db_antrian
        global dt_no_antri, dt_no_pol, dt_no_uji, dt_nama
        global dt_sideslip_flag, dt_sideslip_value, dt_id_user

        self.ids.bt_save.disabled = True
        try:
            ensure_db_connected()
            tb_sideslip_data = mydb.cursor()
            sql = f"UPDATE {TB_DATA} SET sideslip_flag = %s, sideslip_value = %s, sideslip_user = %s, sideslip_post = %s WHERE noantrian = %s"
            sql_sideslip_flag = dt_sideslip_flag
            now = str(time.strftime("%Y/%m/%d %H:%M:%S", time.localtime()))
            sql_val = (sql_sideslip_flag, dt_sideslip_value, dt_id_user, now, dt_no_antri)
            tb_sideslip_data.execute(sql, sql_val)
            mydb.commit()
            toast("Data sideslipmeter Berhasil Disimpan")
            log_audit("SAVE_SIDESLIP", f"antrian={dt_no_antri} nopol={dt_no_pol} value={dt_sideslip_value} flag={dt_sideslip_flag} user={dt_id_user} simulation={SIMULATION_MODE}")
            self.exec_print_pdf()
            self.open_screen_main()
            self.ids.bt_save.disabled = True

        except Exception as e:
            toast_msg = f'Gagal menyimpan data'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")
            log_audit("SAVE_SIDESLIP_FAILED", f"antrian={dt_no_antri} error={e}")

    def exec_print(self):
        try:
            global dt_sideslip_flag
            ensure_db_connected()
            tb_status = mydb.cursor()
            tb_status.execute(f"SELECT sideslip_flag FROM {TB_DATA} WHERE noantrian = '{dt_no_antri}'")
            result_tb_status = tb_status.fetchone()
            mydb.commit()
            db_status = np.array(result_tb_status).T
            dt_sideslip_flag = int(db_status[0])

            self.exec_print_pdf()

            self.ids.bt_print.disabled = True

        except Exception as e:
            toast_msg = f'Gagal Mencetak Hasil Uji'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def exec_print_pdf(self):
        global flag_play
        global count_starting, count_get_data
        global mydb, db_antrian
        global dt_no_antri, dt_no_pol, dt_no_uji, dt_nama, dt_jns_kend
        global dt_speed_flag

        try:
            print_datetime = str(time.strftime("%Y/%m/%d %H:%M:%S", time.localtime()))
            pdf = FPDF()
            pdf.add_page()
            page_w = pdf.w
            margin = pdf.l_margin
            content_w = page_w - 2 * margin

            # --- Header ---
            logo_left = pdf.image(f"assets/images/{IMG_LOGO_DISHUB}", x=margin, y=10, w=26.0)
            logo_right = pdf.image(f"assets/images/{IMG_LOGO_PEMKAB}", x=page_w - margin - 26.0, y=10, w=26.0)
            pdf.set_y(10)
            pdf.set_font('Arial', 'B', 18)
            pdf.cell(0, 8, text="DINAS PERHUBUNGAN", align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Arial', 'B', 13)
            pdf.cell(0, 7, text="UPTD PKB KAB. PANDEGLANG", align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Arial', '', 11)
            pdf.cell(0, 6, text="HASIL UJI SIDESLIP METER", align='C', new_x="LMARGIN", new_y="NEXT")
            logo_bottom = 10 + max(logo_left.rendered_height, logo_right.rendered_height)
            pdf.set_y(max(pdf.get_y(), logo_bottom) + 3)
            pdf.set_draw_color(120, 120, 120)
            pdf.set_line_width(0.4)
            pdf.line(margin, pdf.get_y(), page_w - margin, pdf.get_y())
            pdf.ln(6)

            # --- Identitas kendaraan (2 kolom) ---
            pdf.set_font('Arial', '', 11)
            col_w = content_w / 2
            pdf.cell(col_w, 7, text=f"Tanggal          : {print_datetime}")
            pdf.cell(col_w, 7, text=f"No Reg Kendaraan : {dt_no_pol}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(col_w, 7, text=f"No Antrian       : {dt_no_antri}")
            pdf.cell(col_w, 7, text=f"No Uji           : {dt_no_uji}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(col_w, 7, text=f"Nama             : {dt_nama}")
            pdf.cell(col_w, 7, text=f"JBB              : {dt_jbb} kg", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(col_w, 7, text=f"Berat Kosong     : {float(dt_brt_ksg)} kg", new_x="LMARGIN", new_y="NEXT")
            # baris lentur - kalau jenis kendaraan panjang, teks turun ke baris berikutnya
            pdf.multi_cell(content_w, 7, text=f"Jenis Kendaraan  : {dt_jns_kend}", align='L', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
            pdf.set_draw_color(120, 120, 120)
            pdf.line(margin, pdf.get_y(), page_w - margin, pdf.get_y())
            pdf.ln(8)

            # --- Hasil pengujian ---
            pdf.set_font('Arial', 'B', 15)
            pdf.cell(0, 8, text="SIDESLIP METER", align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 7, text=f"Nilai Pengujian : {float(dt_sideslip_value)} mm", align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

            if int(dt_sideslip_flag) == 1:
                status_text, fill_rgb, text_rgb = "LULUS", (211, 240, 216), (30, 120, 40)
            elif int(dt_sideslip_flag) == 0:
                status_text, fill_rgb, text_rgb = "TIDAK LULUS", (248, 210, 210), (170, 30, 30)
            else:
                status_text, fill_rgb, text_rgb = "BELUM DIUJI", (230, 230, 230), (90, 90, 90)

            box_w = 90.0
            pdf.set_x((page_w - box_w) / 2)
            pdf.set_draw_color(*text_rgb)
            pdf.set_fill_color(*fill_rgb)
            pdf.set_text_color(*text_rgb)
            pdf.set_font('Arial', 'B', 22)
            pdf.cell(box_w, 16, text=status_text, align='C', border=1, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(24)

            pdf.set_font('Arial', 'I', 8)
            pdf.set_text_color(130, 130, 130)
            pdf.cell(0, 5, text="Dicetak otomatis oleh sistem VIIMS", align='C')
            pdf.set_text_color(0, 0, 0)

            documents_dir = os.path.join(os.environ["USERPROFILE"], "Documents")

            folder_name = f"Hasil_Uji_VIIS_Sideslip_Tester_{time.strftime('%Y-%m-%d', time.localtime())}"
            date_folder_path = os.path.join(documents_dir, folder_name)
            
            if not os.path.exists(date_folder_path):
                os.makedirs(date_folder_path)
                toast(f"Folder created: {date_folder_path}")
            else:
                toast(f"Folder already exists: {date_folder_path}")

            pdf_filename = f"Hasil_Uji_No_{dt_no_antri}.pdf"
            pdf_path = os.path.join(date_folder_path, pdf_filename)

            pdf.output(pdf_path, 'F')
            toast(f"PDF saved to: {pdf_path}")
            os.startfile(pdf_path)
            log_audit("PRINT_PDF_SIDESLIP", f"antrian={dt_no_antri} nopol={dt_no_pol} path={pdf_path}")

        except Exception as e:
            toast_msg = f'Gagal menyimpan ke pdf'
            toast(toast_msg)
            Logger.error(f"{self.name}: {toast_msg}, {e}")
            log_audit("PRINT_PDF_SIDESLIP_FAILED", f"antrian={dt_no_antri} error={e}")

    # def exec_print_thermal(self):
    #     global flag_play
    #     global count_starting, count_get_data
    #     global mydb, db_antrian
    #     global dt_no_antri, dt_no_pol, dt_no_uji, dt_nama, dt_jns_kend
    #     global dt_speed_flag

    #     try:
    #         """ 9600 Baud, 8N1, Flow Control Enabled """
    #         printer = Serial(devfile=PRINTER_THERM_COM,
    #                 baudrate=PRINTER_THERM_BAUD,
    #                 bytesize=PRINTER_THERM_BYTESIZE,
    #                 parity=PRINTER_THERM_PARITY,
    #                 stopbits=PRINTER_THERM_STOPBITS,
    #                 timeout=PRINTER_THERM_TIMEOUT,
    #                 dsrdtr=PRINTER_THERM_DSRDTR,)
    #         print_datetime = str(time.strftime("%d %B %Y %H:%M:%S", time.localtime()))
            
    #         printer.image("assets/images/logo-dishub.png")
    #         printer.image("assets/images/logo-pandeglang.png")
    #         printer.textln(" \n ")
    #         printer.textln("VEHICLE INSPECTION INTEGRATION SYSTEM")
    #         printer.textln("SIDESLIP TESTER")
    #         printer.textln("================================================================")
    #         printer.text(f"No Antrian: {dt_no_antri}\t")
    #         printer.text(f"No Reg: {dt_no_pol}\t")
    #         printer.textln(f"No Uji: {dt_no_uji}")
    #         printer.textln("  ")
    #         printer.text(f"Nama: {dt_nama}\t")
    #         printer.textln(f"Jenis Kendaraan: {dt_jns_kend}")
    #         printer.textln("  ")
    #         printer.textln(f"Tanggal: {print_datetime}")
    #         printer.textln("  ")
    #         printer.textln(f"SIDESLIP TESTER")
    #         printer.textln(f"Nilai Pengujian : {float(dt_sideslip_value)} mm")
    #         printer.textln(f"Status Pengujian : {'Lulus' if int(dt_sideslip_flag) == 1 else 'Tidak Lulus' if int(dt_sideslip_flag) == 0 else 'Belum Diuji'}")
    #         printer.textln("  ")
    #         printer.textln("================================================================")
    #         printer.cut()

    #     except Exception as e:
    #         toast_msg = f'Gagal mencetak menggunakan Thermal Printer'
    #         toast(toast_msg)
    #         Logger.error(f"{self.name}: {toast_msg}, {e}")  

    def open_screen_main(self):
        global flag_play        
        global count_starting, count_get_data

        try:
            screen_main = self.screen_manager.get_screen('screen_main')
            count_starting = COUNT_STARTING_SPEED
            count_get_data = COUNT_ACQUISITION_SPEED
            flag_play = False
            self.screen_manager.current = 'screen_menu'
        except Exception as e:
            toast_msg = f'Gagal Berpindah halaman ke Menu: {e}'
            toast(toast_msg)

class RootScreen(ScreenManager):
    pass             

class SpeedMeterApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_resize=self.on_window_resize)

    def build(self):
        global window_size_x, window_size_y
        log_audit("APP_START", f"mode={running_mode} simulation={SIMULATION_MODE}")
        self.theme_cls.colors = colors
        self.theme_cls.primary_palette = "Gray"
        self.theme_cls.accent_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        self.icon = 'assets/images/logo-load-app.png'
        window_size_y = Window.size[0]
        window_size_x = Window.size[1]
        self.set_dynamic_fonts(Window.size)

        LabelBase.register(
            name="Orbitron-Regular",
            fn_regular="assets/fonts/Orbitron-Regular.ttf")
        
        LabelBase.register(
            name="Draco",
            fn_regular="assets/fonts/Draco.otf")        

        LabelBase.register(
            name="Recharge",
            fn_regular="assets/fonts/Recharge.otf") 
        
        theme_font_styles.append('H1')
        self.theme_cls.font_styles["H1"] = [
            "Orbitron-Regular", 64, False, 0.15]       

        theme_font_styles.append('H2')
        self.theme_cls.font_styles["H2"] = [
            "Orbitron-Regular", 32, False, 0.15] 
        
        theme_font_styles.append('H4')
        self.theme_cls.font_styles["H4"] = [
            "Recharge", 30, False, 0.15] 

        theme_font_styles.append('H5')
        self.theme_cls.font_styles["H5"] = [
            "Recharge", 20, False, 0.15] 

        theme_font_styles.append('H6')
        self.theme_cls.font_styles["H6"] = [
            "Recharge", 16, False, 0.15] 

        theme_font_styles.append('Subtitle1')
        self.theme_cls.font_styles["Subtitle1"] = [
            "Recharge", 11, False, 0.15] 

        theme_font_styles.append('Body1')
        self.theme_cls.font_styles["Body1"] = [
            "Recharge", 10, False, 0.15] 
        
        theme_font_styles.append('Button')
        self.theme_cls.font_styles["Button"] = [
            "Recharge", 9, False, 0.15] 

        theme_font_styles.append('Caption')
        self.theme_cls.font_styles["Caption"] = [
            "Recharge", 8, False, 0.15]       
        
        Window.fullscreen = 'auto'
        Builder.load_file('main.kv')
        return RootScreen()

    def on_window_resize(self, window, width, height):
        Logger.info(f"Window size: {width}x{height}")
        self.set_dynamic_fonts((width, height))
        self.refresh_all_fonts()

    def refresh_all_fonts(self):
        # Refresh fonts for all screens in the ScreenManager
        if hasattr(self, 'root') and hasattr(self.root, 'screens'):
            for screen in self.root.screens:
                self.refresh_fonts(screen)

    def refresh_fonts(self, widget):
        from kivymd.uix.label import MDLabel
        if isinstance(widget, MDLabel):
            original_style = widget.font_style
            temp_style = "Body1" if original_style != "Body1" else "H6"
            widget.font_style = temp_style
            widget.font_style = original_style
        if hasattr(widget, 'children'):
            for child in widget.children:
                self.refresh_fonts(child)

    def set_dynamic_fonts(self, size):
        try:
            screen_size_x = Window.system_size[0]
            screen_size_y = Window.system_size[1]
        except AttributeError:
            screen_size_x = Window._get_system_size()[0]
            screen_size_y = Window._get_system_size()[1]
        font_size_l = np.array([64, 32, 30, 20, 16, 11, 10, 9, 8])
        scale = min(screen_size_x / 1920, screen_size_y / 1080)
        font_size = np.round(font_size_l * scale, 0)
        Logger.info(f"Font resized: {font_size_l} to {font_size}")
        self.theme_cls.font_styles["H1"] = [
            "Orbitron-Regular", font_size[0], False, 0.15]
        self.theme_cls.font_styles["H2"] = [
            "Orbitron-Regular", font_size[1], False, 0.15]
        self.theme_cls.font_styles["H4"] = [
            "Recharge", font_size[2], False, 0.15]
        self.theme_cls.font_styles["H5"] = [
            "Recharge", font_size[3], False, 0.15]
        self.theme_cls.font_styles["H6"] = [
            "Recharge", font_size[4], False, 0.15]
        self.theme_cls.font_styles["Subtitle1"] = [
            "Recharge", font_size[5], False, 0.15]
        self.theme_cls.font_styles["Body1"] = [
            "Recharge", font_size[6], False, 0.15]
        self.theme_cls.font_styles["Button"] = [
            "Recharge", font_size[7], False, 0.15]
        self.theme_cls.font_styles["Caption"] = [
            "Recharge", font_size[8], False, 0.15]       

        if hasattr(self, 'root'):
            self.refresh_fonts(self.root)

    def on_stop(self):
        log_audit("APP_STOP")

if __name__ == '__main__':
    SpeedMeterApp().run()
