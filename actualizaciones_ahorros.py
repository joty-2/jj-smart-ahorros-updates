import os
import base64, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
from urllib.request import Request, ProxyHandler, build_opener
_opener = build_opener(ProxyHandler({}))
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QTextEdit, QApplication
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from ahorros_datos import ruta_datos
from updater_independiente import canon

VERSION = '1.1.9'
APP = 'JJ_SMART_AHORROS'
CANALES_ORDEN = {'interno': 0, 'piloto': 1, 'produccion': 2}
URL_GITHUB_DEFAULT = 'https://github.com/joty-2/jj-smart-ahorros-updates/releases/latest/download/'

def clave_dueno() -> Path:
    return ruta_datos() / 'Publicador' / 'privada.key'

def config_canal_path() -> Path:
    c = ruta_datos() / 'config_actualizaciones.json'
    c.parent.mkdir(parents=True, exist_ok=True)
    return c

def leer_config_canal() -> dict:
    c = config_canal_path()
    if c.exists():
        try:
            d = json.loads(c.read_text(encoding='utf-8'))
            if 'joty-2' in d.get('url', ''): return d
        except Exception: pass
    return {'url': URL_GITHUB_DEFAULT, 'canal': 'produccion'}

def guardar_config_canal(url: str, canal: str):
    config_canal_path().write_text(json.dumps({'url': url.strip(), 'canal': canal}, indent=2), encoding='utf-8')

def version_tupla(v: str):
    return tuple(map(int, v.strip().split('.')))

def verificar_manifiesto(doc: dict, pub: bytes, canal_cliente: str) -> dict:
    m = doc['manifest']
    Ed25519PublicKey.from_public_bytes(pub).verify(base64.b64decode(doc['signature'], validate=True), canon(m))
    if m.get('app') != APP: raise ValueError('El paquete no pertenece a JJ SMART AHORROS.')
    if CANALES_ORDEN.get(m.get('stage', 'produccion'), 2) < CANALES_ORDEN.get(canal_cliente, 2):
        raise ValueError('AUN_NO_LIBERADA_PARA_ESTE_CANAL')
    if version_tupla(m['version']) <= version_tupla(VERSION):
        raise ValueError('YA_ACTUALIZADO')
    return m

def lanzar_updater_externo(zip_path: Path, manifest_path: Path):
    datos_dir = ruta_datos()
    upd_dir = datos_dir / 'Actualizaciones'
    upd_dir.mkdir(parents=True, exist_ok=True)
    if getattr(sys, 'frozen', False) and os.name == 'nt':
        exe_actual = Path(sys.executable).resolve()
        app_dir = exe_actual.parent
        stg = upd_dir / 'staging_win'
        bat = upd_dir / 'aplicar_update_win.bat'
        bat_code = rf'''@echo off
chcp 65001 >nul
timeout /t 2 /nobreak >nul
:esperar_cierre
tasklist /FI "IMAGENAME eq {exe_actual.name}" 2>NUL | find /I "{exe_actual.name}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto esperar_cierre
)
if not exist "{datos_dir}\Respaldos_Rollback" mkdir "{datos_dir}\Respaldos_Rollback"
if exist "{datos_dir}\ahorros.db" copy /Y "{datos_dir}\ahorros.db" "{datos_dir}\Respaldos_Rollback\ahorros_pre_update.db" >nul
if exist "{stg}" rmdir /S /Q "{stg}"
powershell -NoProfile -Command "Expand-Archive -LiteralPath '{zip_path}' -DestinationPath '{stg}' -Force"
if exist "{upd_dir}\JJ_SMART_AHORROS_new.exe" (
    :copiar_exe_directo
    move /Y "{upd_dir}\JJ_SMART_AHORROS_new.exe" "{exe_actual}" >nul 2>&1
    if errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto copiar_exe_directo
    )
) else if exist "{stg}\JJ_SMART_AHORROS.exe" (
    :copiar_exe
    copy /Y "{stg}\JJ_SMART_AHORROS.exe" "{exe_actual}" >nul 2>&1
    if errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto copiar_exe
    )
) else (
    robocopy "{stg}" "{app_dir}" /E /XF ahorros.db privada.key >nul
)
rmdir /S /Q "{stg}" >nul 2>&1
start "" "{exe_actual}"
del "%~f0"
'''
        bat.write_text(bat_code, encoding='utf-8')
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        subprocess.Popen(['cmd.exe', '/c', str(bat)], creationflags=flags, close_fds=True)
        return
    app_dir = Path(__file__).resolve().parent
    upd_copia = upd_dir / 'updater_independiente.py'
    shutil.copy2(app_dir / 'updater_independiente.py', upd_copia)
    cmd = [sys.executable, str(app_dir / 'main.py')]
    args = [sys.executable, str(upd_copia), str(app_dir), str(datos_dir), str(zip_path), str(manifest_path)] + cmd
    flags = (getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)) if os.name == 'nt' else 0
    subprocess.Popen(args, creationflags=flags, close_fds=True)

class HiloVerificar(QThread):
    disponible = Signal(dict, str); sin_cambios = Signal(str); error = Signal(str)
    def __init__(self, url: str, canal: str, pub: bytes):
        super().__init__(); self.url = url.rstrip('/') + '/'; self.canal = canal; self.pub = pub
    def run(self):
        try:
            req = Request(self.url + 'manifest.json', headers={'User-Agent': 'JJSmartAhorros/1.0'})
            with _opener.open(req, timeout=15) as r: raw = r.read(65537).decode('utf-8')
            m = verificar_manifiesto(json.loads(raw), self.pub, self.canal)
            self.disponible.emit(m, raw)
        except ValueError as ve:
            if str(ve) in ('YA_ACTUALIZADO', 'AUN_NO_LIBERADA_PARA_ESTE_CANAL'):
                self.sin_cambios.emit('Tienes la versión más reciente autorizada para tu canal.')
            else: self.error.emit(str(ve))
        except Exception as e: self.error.emit(str(e))

class HiloDescargar(QThread):
    progreso = Signal(str); listo = Signal(str, str); error = Signal(str)
    def __init__(self, url: str, raw: str, m: dict, dest: Path):
        super().__init__(); self.url = url.rstrip('/') + '/'; self.raw = raw; self.m = m; self.dest = dest
    def run(self):
        try:
            self.dest.mkdir(parents=True, exist_ok=True)
            zp = self.dest / self.m['file']; mp = self.dest / 'manifest_verificado.json'
            h = hashlib.sha256(); tot = 0; esp = int(self.m['size'])
            req = Request(self.url + self.m['file'], headers={'User-Agent': 'JJSmartAhorros/1.0'})
            with _opener.open(req, timeout=45) as r, zp.open('wb') as out:
                while True:
                    ch = r.read(262144)
                    if not ch: break
                    tot += len(ch)
                    if tot > esp: raise ValueError('Descarga supera tamaño firmado.')
                    out.write(ch); h.update(ch); self.progreso.emit(f"Descargando v{self.m['version']}: {tot * 100 // esp}%")
            if tot != esp or h.hexdigest() != self.m['sha256']:
                zp.unlink(missing_ok=True); raise ValueError('Integridad SHA-256 fallida.')
            mp.write_text(self.raw, encoding='utf-8')
            if getattr(sys, 'frozen', False) and os.name == 'nt':
                exe_new = self.dest / 'JJ_SMART_AHORROS_new.exe'
                self.progreso.emit(f"Descargando ejecutable Windows v{self.m['version']}...")
                req_exe = Request(self.url + 'JJ_SMART_AHORROS.exe', headers={'User-Agent': 'JJSmartAhorros/1.0'})
                with _opener.open(req_exe, timeout=90) as rexe, exe_new.open('wb') as oexe:
                    shutil.copyfileobj(rexe, oexe, 262144)
                if exe_new.stat().st_size < 10_000_000:
                    exe_new.unlink(missing_ok=True)
                    raise ValueError('Ejecutable Windows incompleto en el servidor.')
            self.listo.emit(str(zp), str(mp))
        except Exception as e: self.error.emit(str(e))

class Actualizaciones(QDialog):
    def __init__(self, parent, manifest_auto=None, raw_auto=None):
        super().__init__(parent); self.setWindowTitle('Actualizaciones Seguras · JJ SMART AHORROS'); self.resize(680, 440)
        self.pub = (Path(__file__).resolve().parent / 'assets' / 'actualizaciones.pub').read_bytes()
        cfg = leer_config_canal(); box = QVBoxLayout(self)
        box.addWidget(QLabel(f"<b>Versión instalada:</b> {VERSION} · <i>Base de datos ahorros.db aislada y protegida</i>"))
        ru = QHBoxLayout(); self.inp_url = QLineEdit(cfg.get('url', URL_GITHUB_DEFAULT))
        ru.addWidget(QLabel('Servidor HTTPS:')); ru.addWidget(self.inp_url); box.addLayout(ru)
        rc = QHBoxLayout(); self.cmb_canal = QComboBox(); self.cmb_canal.addItems(['produccion', 'piloto', 'interno'])
        self.cmb_canal.setCurrentText(cfg.get('canal', 'produccion'))
        rc.addWidget(QLabel('Canal:')); rc.addWidget(self.cmb_canal); rc.addStretch(); box.addLayout(rc)
        self.txt_notas = QTextEdit(); self.txt_notas.setReadOnly(True)
        self.txt_notas.setPlainText('Pulsa "Buscar por Internet" o "Instalar desde Memoria USB".')
        box.addWidget(self.txt_notas, 1); self.lbl_estado = QLabel(''); self.lbl_estado.setWordWrap(True); box.addWidget(self.lbl_estado)
        bs = QHBoxLayout(); self.btn_buscar = QPushButton('🌐 Buscar por Internet'); self.btn_instalar = QPushButton('⬇️ Descargar e Instalar Ahora')
        self.btn_usb = QPushButton('💾 Instalar desde Memoria USB'); self.btn_instalar.setEnabled(False)
        bs.addWidget(self.btn_buscar); bs.addWidget(self.btn_instalar); bs.addWidget(self.btn_usb); box.addLayout(bs)
        self.pendiente = None
        if manifest_auto and raw_auto: self._mostrar(manifest_auto, raw_auto)
        self.btn_buscar.clicked.connect(self._buscar); self.btn_instalar.clicked.connect(self._descargar); self.btn_usb.clicked.connect(self._usb)

    def _mostrar(self, m, raw):
        self.pendiente = (m, raw); self.btn_instalar.setEnabled(True)
        self.txt_notas.setPlainText(f"Nueva versión v{m['version']} (Canal: {m.get('stage','produccion')})\n\nMejoras:\n{m.get('notes','')}")
        self.lbl_estado.setText('✅ Firma Ed25519 verificada. Listo para instalar.')

    def _buscar(self):
        guardar_config_canal(self.inp_url.text(), self.cmb_canal.currentText()); self.btn_buscar.setEnabled(False)
        self.hv = HiloVerificar(self.inp_url.text(), self.cmb_canal.currentText(), self.pub)
        self.hv.disponible.connect(self._mostrar); self.hv.sin_cambios.connect(lambda s: self.lbl_estado.setText('ℹ️ ' + s))
        self.hv.error.connect(lambda e: self.lbl_estado.setText('⚠️ ' + e)); self.hv.finished.connect(lambda: self.btn_buscar.setEnabled(True)); self.hv.start()

    def _descargar(self):
        if not self.pendiente: return
        m, raw = self.pendiente; self.btn_instalar.setEnabled(False)
        self.hd = HiloDescargar(self.inp_url.text(), raw, m, ruta_datos() / 'Actualizaciones')
        self.hd.progreso.connect(self.lbl_estado.setText); self.hd.listo.connect(self._lanzar)
        self.hd.error.connect(lambda e: (self.lbl_estado.setText('⚠️ ' + e), self.btn_instalar.setEnabled(True))); self.hd.start()

    def _usb(self):
        mf, _ = QFileDialog.getOpenFileName(self, 'Selecciona manifest.json en USB', '', 'Manifiesto (*.json)')
        if not mf: return
        try:
            mp = Path(mf); raw = mp.read_text(encoding='utf-8'); m = verificar_manifiesto(json.loads(raw), self.pub, self.cmb_canal.currentText())
            zp = mp.parent / m['file']
            if not zp.exists(): raise ValueError(f"Falta {m['file']} en la USB.")
            self._lanzar(str(zp), str(mp))
        except Exception as e: QMessageBox.warning(self, 'USB inválida', str(e))

    def _lanzar(self, zp, mp):
        if QMessageBox.question(self, 'Instalar actualización', 'Se respaldará ahorros.db y el programa, se cerrará la app y se instalará la mejora.\n\n¿Continuar?') == QMessageBox.Yes:
            lanzar_updater_externo(Path(zp), Path(mp)); os._exit(0)

def verificar_notificacion_inicio(ventana):
    try:
        pub = (Path(__file__).resolve().parent / 'assets' / 'actualizaciones.pub').read_bytes()
        cfg = leer_config_canal(); hv = HiloVerificar(cfg.get('url', URL_GITHUB_DEFAULT), cfg.get('canal', 'produccion'), pub)
        def _notificar(m, raw):
            if QMessageBox.question(ventana, f"🔔 Mejora disponible v{m['version']}", f"JJ SMART AHORROS tiene una nueva actualización:\n\n{m.get('notes','')}\n\n¿Deseas instalarla ahora?") == QMessageBox.Yes:
                Actualizaciones(ventana, manifest_auto=m, raw_auto=raw).exec()
        hv.disponible.connect(_notificar); hv.finished.connect(hv.deleteLater); ventana._hilo_upd_inicio = hv; hv.start()
    except Exception: pass
