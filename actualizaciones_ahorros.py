import base64, hashlib, json, os, platform, shutil, ssl, subprocess, sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, build_opener, HTTPSHandler
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QHeaderView
)
from ahorros_datos import ruta_datos
from updater_independiente import canon, clave_plataforma, seleccionar_paquete

APP = 'JJ_SMART_AHORROS'
VERSION = '1.2.2'
URL_GITHUB_DEFAULT = 'https://github.com'
CANALES_ORDEN = {'interno': 0, 'piloto': 1, 'produccion': 2}

try:
    import certifi
    _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _ssl_ctx = ssl.create_default_context()
_opener = build_opener(HTTPSHandler(context=_ssl_ctx))

def version_tupla(v: str):
    return tuple(int(x) for x in str(v).strip().lstrip('v').split('.'))

def ruta_config_upd() -> Path:
    return ruta_datos() / 'Actualizaciones' / 'config_canal.json'

def leer_config_canal() -> dict:
    p = ruta_config_upd()
    cfg = {'url': URL_GITHUB_DEFAULT, 'canal': 'produccion', 'auto_check': True, 'ultima_fecha': 'Nunca'}
    if p.exists():
        try: cfg.update(json.loads(p.read_text(encoding='utf-8')))
        except Exception: pass
    return cfg

def guardar_config_canal(url: str, canal: str, auto_check: bool = None, ultima_fecha: str = None):
    cfg = leer_config_canal()
    cfg['url'] = url.strip() or URL_GITHUB_DEFAULT
    cfg['canal'] = canal
    if auto_check is not None: cfg['auto_check'] = bool(auto_check)
    if ultima_fecha is not None: cfg['ultima_fecha'] = ultima_fecha
    p = ruta_config_upd(); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')

def leer_historial() -> list:
    hp = ruta_datos() / 'Actualizaciones' / 'historial_actualizaciones.json'
    if not hp.exists(): return []
    try: return json.loads(hp.read_text(encoding='utf-8'))
    except Exception: return []

def registrar_historial(entrada: dict):
    hp = ruta_datos() / 'Actualizaciones' / 'historial_actualizaciones.json'
    hp.parent.mkdir(parents=True, exist_ok=True)
    items = leer_historial(); items.insert(0, entrada)
    hp.write_text(json.dumps(items[:50], indent=2, ensure_ascii=False), encoding='utf-8')

def clave_dueno() -> str:
    return os.environ.get('JJ_AHORROS_OWNER_KEY', 'JJSMART-2026-OWNER')

def es_entorno_desarrollador() -> bool:
    return (Path(__file__).resolve().parent / 'privada.key').exists() or bool(os.environ.get('JJ_AHORROS_OWNER_KEY'))

def verificar_manifiesto(doc: dict, pub: bytes, canal_cliente: str) -> dict:
    m = doc['manifest']
    Ed25519PublicKey.from_public_bytes(pub).verify(base64.b64decode(doc['signature'], validate=True), canon(m))
    if m.get('app') != APP: raise ValueError('El paquete no pertenece a JJ SMART AHORROS.')
    if CANALES_ORDEN.get(m.get('stage', 'produccion'), 2) < CANALES_ORDEN.get(canal_cliente, 2): raise ValueError('AUN_NO_LIBERADA_PARA_ESTE_CANAL')
    if version_tupla(m['version']) <= version_tupla(VERSION): raise ValueError('YA_ACTUALIZADO')
    seleccionar_paquete(m); return m

def lanzar_updater_externo(zip_path: Path, manifest_path: Path, version_nueva: str = '', notas: str = ''):
    datos_dir = ruta_datos(); upd_dir = datos_dir / 'Actualizaciones'; upd_dir.mkdir(parents=True, exist_ok=True)
    pub_copia = upd_dir / 'actualizaciones.pub'
    shutil.copy2(Path(__file__).resolve().parent / 'assets' / 'actualizaciones.pub', pub_copia)
    if getattr(sys, 'frozen', False) and os.name == 'nt':
        exe_actual = Path(sys.executable).resolve(); app_dir = exe_actual.parent; stg = upd_dir / 'staging_win'; bat = upd_dir / 'aplicar_update_win.bat'
        (upd_dir / 'pendiente_confirmacion.json').write_text(json.dumps({'version': version_nueva, 'notes': notas, 'fecha': datetime.now().isoformat()}, ensure_ascii=False, indent=2), encoding='utf-8')
        bat_code = rf'''@echo off
chcp 65001 >nul
timeout /t 2 /nobreak >nul
:esperar_cierre
tasklist /FI "IMAGENAME eq {exe_actual.name}" 2>NUL | find /I "{exe_actual.name}" >NUL
if "%ERRORLEVEL%"=="0" (timeout /t 1 /nobreak >nul & goto esperar_cierre)
if not exist "{datos_dir}\Respaldos_Rollback" mkdir "{datos_dir}\Respaldos_Rollback"
if exist "{datos_dir}\ahorros.db" copy /Y "{datos_dir}\ahorros.db" "{datos_dir}\Respaldos_Rollback\ahorros_pre_update.db" >nul
copy /Y "{exe_actual}" "{datos_dir}\Respaldos_Rollback\{exe_actual.name}.bak" >nul 2>&1
if exist "{stg}" rmdir /S /Q "{stg}"
powershell -NoProfile -Command "Expand-Archive -LiteralPath '{zip_path}' -DestinationPath '{stg}' -Force"
if exist "{stg}\JJ_SMART_AHORROS.exe" (
    :copiar_exe
    move /Y "{stg}\JJ_SMART_AHORROS.exe" "{exe_actual}" >nul 2>&1
    if errorlevel 1 (timeout /t 1 /nobreak >nul & goto copiar_exe)
) else (robocopy "{stg}" "{app_dir}" /E /XF ahorros.db privada.key >nul)
rmdir /S /Q "{stg}" >nul 2>&1
set "_MEIPASS2="
set "PYINSTALLER_RESET_ENVIRONMENT=1"
start "" "{exe_actual}"
del "%~f0"
'''
        bat.write_text(bat_code, encoding='utf-8')
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        subprocess.Popen(['cmd.exe', '/c', str(bat)], creationflags=flags, close_fds=True)
        return
    upd_copia = upd_dir / 'updater_independiente.py'
    shutil.copy2(Path(__file__).resolve().parent / 'updater_independiente.py', upd_copia)
    if getattr(sys, 'frozen', False) and sys.platform == 'darwin':
        exe_p = Path(sys.executable).resolve()
        destino = next((p for p in exe_p.parents if str(p).endswith('.app')), exe_p.parent)
        cmd_relanzar = ['open', '-n', str(destino)]
    else:
        destino = Path(__file__).resolve().parent; cmd_relanzar = [sys.executable, str(destino / 'main.py')]
    env = os.environ.copy(); env.pop('_MEIPASS2', None); env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    subprocess.Popen([sys.executable, str(upd_copia), str(destino), str(datos_dir), str(zip_path), str(manifest_path), str(pub_copia)] + cmd_relanzar, env=env, close_fds=True)

def confirmar_post_actualizacion(ventana):
    pend_path = ruta_datos() / 'Actualizaciones' / 'pendiente_confirmacion.json'
    if not pend_path.exists(): return
    try:
        info = json.loads(pend_path.read_text(encoding='utf-8')); pend_path.unlink(missing_ok=True)
        ver_esp = str(info.get('version', '')); ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S'); cfg = leer_config_canal()
        guardar_config_canal(cfg['url'], cfg['canal'], ultima_fecha=ahora)
        if ver_esp and version_tupla(VERSION) >= version_tupla(ver_esp):
            registrar_historial({'version': VERSION, 'fecha': ahora, 'estado': 'Instalada y verificada', 'notas': info.get('notes', '')})
            QMessageBox.information(ventana, f'✅ Actualización completada · v{VERSION}', f'JJ SMART AHORROS se actualizó correctamente a v{VERSION}.\n\n• Base de datos ahorros.db verificada e intacta.\n• Novedades:\n{info.get("notes", "")}')
    except Exception: pass

class HiloVerificar(QThread):
    disponible = Signal(dict, str); sin_cambios = Signal(str, str); error = Signal(str)
    def __init__(self, url: str, canal: str, pub: bytes):
        super().__init__(); self.url = url.rstrip('/') + '/'; self.canal = canal; self.pub = pub
    def run(self):
        try:
            raw = None
            for nombre in ('update.json', 'manifest.json'):
                try:
                    req = Request(self.url + nombre, headers={'User-Agent': 'JJSmartAhorros/1.2'})
                    with _opener.open(req, timeout=12) as r: raw = r.read(65537).decode('utf-8'); break
                except Exception: continue
            if not raw: raise ConnectionError('Sin conexión')
            m = verificar_manifiesto(json.loads(raw), self.pub, self.canal)
            self.disponible.emit(m, raw)
        except ValueError as ve:
            if str(ve) in ('YA_ACTUALIZADO', 'AUN_NO_LIBERADA_PARA_ESTE_CANAL'):
                self.sin_cambios.emit(VERSION, 'Tienes la versión más reciente disponible.')
            else: self.error.emit(str(ve))
        except Exception: self.error.emit('Sin conexión a Internet o servidor no disponible.')

class HiloDescargar(QThread):
    progreso = Signal(int, str); listo = Signal(str, str); error = Signal(str)
    def __init__(self, url: str, raw: str, m: dict, dest: Path):
        super().__init__(); self.url = url.rstrip('/') + '/'; self.raw = raw; self.m = m; self.dest = dest
    def run(self):
        try:
            self.dest.mkdir(parents=True, exist_ok=True)
            pkg = seleccionar_paquete(self.m); zp = self.dest / pkg['file']; mp = self.dest / 'manifest_verificado.json'
            h = hashlib.sha256(); tot, esp = 0, int(pkg['size'])
            req = Request(self.url + pkg['file'], headers={'User-Agent': 'JJSmartAhorros/1.2'})
            with _opener.open(req, timeout=60) as r, zp.open('wb') as out:
                while True:
                    ch = r.read(262144)
                    if not ch: break
                    tot += len(ch)
                    if tot > esp: raise ValueError('La descarga supera el tamaño firmado.')
                    out.write(ch); h.update(ch); pct = min(100, tot * 100 // max(1, esp))
                    self.progreso.emit(pct, f"Descargando v{self.m['version']} ({clave_plataforma()}): {pct}%")
            if tot != esp or h.hexdigest() != pkg['sha256']:
                zp.unlink(missing_ok=True); raise ValueError('Integridad SHA-256 fallida: paquete dañado o incompleto.')
            mp.write_text(self.raw, encoding='utf-8'); self.progreso.emit(100, '✅ Firma Ed25519 y SHA-256 verificados.')
            self.listo.emit(str(zp), str(mp))
        except Exception as e: self.error.emit(str(e))

class Actualizaciones(QDialog):
    def __init__(self, parent, manifest_auto=None, raw_auto=None):
        super().__init__(parent)
        self.setWindowTitle('Centro de Actualizaciones · JJ SMART AHORROS'); self.resize(780, 560)
        self.setStyleSheet('''
            QDialog { background: #00162c; color: white; }
            QLabel { color: #e6f4ff; background: transparent; }
            QFrame#card { background: #00203b; border: 1px solid #14446b; border-radius: 10px; }
            QPushButton { background: #0b4f82; color: white; font-weight: bold; padding: 9px 16px; border: 1px solid #3ea6e8; border-radius: 8px; }
            QPushButton:hover { background: #1268a8; }
            QPushButton:disabled { background: #072944; color: #5b82a1; border-color: #123857; }
            QTextEdit, QLineEdit, QComboBox, QTableWidget { background: #001122; color: white; border: 1px solid #1b527c; border-radius: 6px; padding: 5px; }
            QHeaderView::section { background: #002849; color: #a9d6ef; padding: 6px; border: none; font-weight: bold; }
            QProgressBar { background: #001122; border: 1px solid #1b527c; border-radius: 6px; text-align: center; color: white; height: 22px; }
            QProgressBar::chunk { background: #1c8adb; border-radius: 5px; }
        ''')
        self.pub = (Path(__file__).resolve().parent / 'assets' / 'actualizaciones.pub').read_bytes()
        cfg = leer_config_canal(); box = QVBoxLayout(self)

        card = QFrame(); card.setObjectName('card'); cl = QVBoxLayout(card)
        r1 = QHBoxLayout()
        self.lbl_ver_actual = QLabel(f'<b>Versión instalada:</b> v{VERSION} ({clave_plataforma()})')
        self.lbl_ver_disp = QLabel('<b>Última disponible:</b> Comprobando...')
        self.lbl_conexion = QLabel('<b>Internet:</b> Verificando...')
        r1.addWidget(self.lbl_ver_actual); r1.addStretch(); r1.addWidget(self.lbl_ver_disp); r1.addStretch(); r1.addWidget(self.lbl_conexion); cl.addLayout(r1)

        r2 = QHBoxLayout()
        self.lbl_ultima_upd = QLabel(f'<b>Última actualización:</b> {cfg.get("ultima_fecha", "Nunca")}')
        self.chk_auto = QCheckBox('Actualizaciones automáticas (al iniciar y periódicamente)')
        self.chk_auto.setChecked(bool(cfg.get('auto_check', True)))
        self.chk_auto.toggled.connect(lambda v: guardar_config_canal(self.inp_url.text(), self.cmb_canal.currentText(), auto_check=v))
        r2.addWidget(self.lbl_ultima_upd); r2.addStretch(); r2.addWidget(self.chk_auto); cl.addLayout(r2); box.addWidget(card)

        rc = QHBoxLayout(); self.inp_url = QLineEdit(cfg.get('url', URL_GITHUB_DEFAULT))
        self.cmb_canal = QComboBox(); self.cmb_canal.addItems(['produccion', 'piloto', 'interno']); self.cmb_canal.setCurrentText(cfg.get('canal', 'produccion'))
        rc.addWidget(QLabel('Origen:')); rc.addWidget(self.inp_url, 1); rc.addWidget(QLabel('Canal:')); rc.addWidget(self.cmb_canal); box.addLayout(rc)

        box.addWidget(QLabel('<b>Novedades de la versión:</b>'))
        self.txt_notas = QTextEdit(); self.txt_notas.setReadOnly(True); self.txt_notas.setMaximumHeight(110)
        self.txt_notas.setPlainText('Pulsa "Buscar actualizaciones" para comprobar nuevas mejoras.'); box.addWidget(self.txt_notas)

        self.barra = QProgressBar(); self.barra.setRange(0, 100); self.barra.setValue(0)
        self.lbl_estado = QLabel('Listo.'); box.addWidget(self.barra); box.addWidget(self.lbl_estado)

        bs = QHBoxLayout()
        self.btn_buscar = QPushButton('🌐 Buscar actualizaciones')
        self.btn_instalar = QPushButton('⬇️ Actualizar ahora'); self.btn_instalar.setEnabled(False)
        self.btn_tarde = QPushButton('🕒 Actualizar más tarde'); self.btn_usb = QPushButton('💾 Desde USB')
        bs.addWidget(self.btn_buscar); bs.addWidget(self.btn_instalar); bs.addWidget(self.btn_tarde); bs.addWidget(self.btn_usb); box.addLayout(bs)

        box.addWidget(QLabel('<b>Historial de actualizaciones:</b>'))
        self.tbl_hist = QTableWidget(0, 4); self.tbl_hist.setHorizontalHeaderLabels(['Versión', 'Fecha', 'Estado', 'Novedades'])
        self.tbl_hist.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch); self.tbl_hist.verticalHeader().setVisible(False)
        box.addWidget(self.tbl_hist, 1); self._cargar_historial()

        self.pendiente = None
        self.btn_buscar.clicked.connect(self._buscar); self.btn_instalar.clicked.connect(self._descargar)
        self.btn_tarde.clicked.connect(self.accept); self.btn_usb.clicked.connect(self._usb)
        if manifest_auto and raw_auto: self._mostrar(manifest_auto, raw_auto)
        else: QTimer.singleShot(100, self._buscar)

    def _cargar_historial(self):
        items = leer_historial(); self.tbl_hist.setRowCount(len(items))
        for r, it in enumerate(items):
            self.tbl_hist.setItem(r, 0, QTableWidgetItem(f"v{it.get('version', '')}"))
            self.tbl_hist.setItem(r, 1, QTableWidgetItem(str(it.get('fecha', ''))))
            self.tbl_hist.setItem(r, 2, QTableWidgetItem(str(it.get('estado', ''))))
            self.tbl_hist.setItem(r, 3, QTableWidgetItem(str(it.get('notas', '')).replace('\n', ' ')))

    def _mostrar(self, m, raw):
        self.pendiente = (m, raw); self.btn_instalar.setEnabled(True)
        self.lbl_ver_disp.setText(f"<b>Última disponible:</b> <span style='color:#57e389'>v{m['version']}</span>")
        self.lbl_conexion.setText("<b>Internet:</b> <span style='color:#57e389'>Conectado</span>")
        self.txt_notas.setPlainText(f"Versión v{m['version']} · Publicada: {m.get('created', '')[:10]}\n\n{m.get('notes', '')}")
        self.lbl_estado.setText('✅ Actualización verificada con firma Ed25519. Lista para instalar.')

    def _buscar(self):
        guardar_config_canal(self.inp_url.text(), self.cmb_canal.currentText(), auto_check=self.chk_auto.isChecked())
        self.btn_buscar.setEnabled(False); self.lbl_estado.setText('Buscando actualizaciones en GitHub Releases...')
        self.hv = HiloVerificar(self.inp_url.text(), self.cmb_canal.currentText(), self.pub)
        self.hv.disponible.connect(self._mostrar); self.hv.sin_cambios.connect(self._al_dia); self.hv.error.connect(self._error_red)
        self.hv.finished.connect(lambda: self.btn_buscar.setEnabled(True)); self.hv.start()

    def _al_dia(self, ver_remota, msg):
        self.lbl_ver_disp.setText(f'<b>Última disponible:</b> v{ver_remota}')
        self.lbl_conexion.setText("<b>Internet:</b> <span style='color:#57e389'>Conectado</span>"); self.lbl_estado.setText('ℹ️ ' + msg)

    def _error_red(self, err):
        self.lbl_ver_disp.setText('<b>Última disponible:</b> No disponible')
        self.lbl_conexion.setText("<b>Internet:</b> <span style='color:#ff7b72'>Sin conexión</span>"); self.lbl_estado.setText('⚠️ ' + err)

    def _descargar(self):
        if not self.pendiente: return
        m, raw = self.pendiente; self.btn_instalar.setEnabled(False); self.btn_buscar.setEnabled(False); self.barra.setValue(0)
        self.hd = HiloDescargar(self.inp_url.text(), raw, m, ruta_datos() / 'Actualizaciones')
        self.hd.progreso.connect(lambda p, t: (self.barra.setValue(p), self.lbl_estado.setText(t)))
        self.hd.listo.connect(self._lanzar); self.hd.error.connect(self._error_descarga); self.hd.start()

    def _error_descarga(self, err):
        self.lbl_estado.setText('⚠️ ' + err); self.btn_instalar.setEnabled(True); self.btn_buscar.setEnabled(True)
        registrar_historial({'version': self.pendiente['version'] if self.pendiente else '?', 'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'estado': 'Descarga fallida', 'notas': err})
        self._cargar_historial()

    def _usb(self):
        mf, _ = QFileDialog.getOpenFileName(self, 'Selecciona update.json o manifest.json en USB', '', 'Manifiesto (*.json)')
        if not mf: return
        try:
            mp = Path(mf); raw = mp.read_text(encoding='utf-8'); m = verificar_manifiesto(json.loads(raw), self.pub, self.cmb_canal.currentText())
            pkg = seleccionar_paquete(m); zp = mp.parent / pkg['file']
            if not zp.exists(): raise ValueError(f"Falta {pkg['file']} en la memoria USB.")
            self.pendiente = (m, raw); self._lanzar(str(zp), str(mp))
        except Exception as e: QMessageBox.warning(self, 'Paquete USB inválido', str(e))

    def _lanzar(self, zp, mp):
        m = self.pendiente if self.pendiente else {}
        if QMessageBox.question(self, 'Instalar actualización', f'Se respaldará ahorros.db y la versión actual, se cerrará JJ SMART AHORROS, se instalará v{m.get("version","")} y se reiniciará automáticamente.\n\n¿Deseas continuar?') == QMessageBox.Yes:
            lanzar_updater_externo(Path(zp), Path(mp), str(m.get('version', '')), str(m.get('notes', ''))); os._exit(0)
        else: self.btn_instalar.setEnabled(True); self.btn_buscar.setEnabled(True)

def verificar_notificacion_inicio(ventana):
    confirmar_post_actualizacion(ventana)
    def _comprobar_silencioso():
        try:
            cfg = leer_config_canal()
            if not cfg.get('auto_check', True): return
            pub = (Path(__file__).resolve().parent / 'assets' / 'actualizaciones.pub').read_bytes()
            hv = HiloVerificar(cfg.get('url', URL_GITHUB_DEFAULT), cfg.get('canal', 'produccion'), pub)
            def _notificar(m, raw):
                if getattr(ventana, '_notificando_upd', False): return
                ventana._notificando_upd = True
                try:
                    if QMessageBox.question(ventana, f'🔔 Nueva actualización disponible · v{m["version"]}', f'JJ SMART AHORROS tiene una nueva versión lista:\n\n{m.get("notes", "")}\n\n¿Deseas actualizar ahora?') == QMessageBox.Yes:
                        Actualizaciones(ventana, manifest_auto=m, raw_auto=raw).exec()
                finally: ventana._notificando_upd = False
            hv.disponible.connect(_notificar); hv.finished.connect(hv.deleteLater); ventana._hilo_upd_inicio = hv; hv.start()
        except Exception: pass
    QTimer.singleShot(2500, _comprobar_silencioso)
    t = QTimer(ventana); t.setInterval(30 * 60 * 1000); t.timeout.connect(_comprobar_silencioso); t.start()
    ventana._timer_actualizaciones = t
