import base64, hashlib, json, os, re, shutil, subprocess, time
from datetime import datetime
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout
)
import actualizaciones_ahorros as _upd
from actualizaciones_ahorros import APP, clave_dueno, leer_config_canal

REPO_BUILD_DIR = Path('/tmp/jj_ahorros_repo_build')
REPO_SLUG = 'joty-2/jj-smart-ahorros-updates'

def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open('rb') as f:
        for ch in iter(lambda: f.read(262144), b''): h.update(ch)
    return h.hexdigest()

def canon(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')

def asegurar_llaves_firma(app_dir: Path) -> Ed25519PrivateKey:
    priv_p = app_dir / 'privada.key'; pub_p = app_dir / 'assets' / 'actualizaciones.pub'
    pub_p.parent.mkdir(parents=True, exist_ok=True)
    if priv_p.exists():
        sk = Ed25519PrivateKey.from_private_bytes(priv_p.read_bytes())
        if not pub_p.exists():
            pub_p.write_bytes(sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        return sk
    sk = Ed25519PrivateKey.generate()
    priv_p.write_bytes(sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
    pub_p.write_bytes(sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    return sk

class HiloPublicarMultiplataforma(QThread):
    progreso = Signal(int, str); finalizado = Signal(str); error = Signal(str)
    def __init__(self, app_dir: Path, version: str, etapa: str, notas: str):
        super().__init__(); self.app_dir = app_dir; self.version = version; self.etapa = etapa; self.notas = notas
    def _run(self, cmd, cwd=None):
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
        if p.returncode != 0: raise RuntimeError(p.stderr.strip() or p.stdout.strip() or f'Error: {" ".join(cmd)}')
        return p.stdout.strip()
    def run(self):
        try:
            gh = shutil.which('gh') or '/opt/homebrew/bin/gh'
            if not Path(gh).exists(): raise RuntimeError('GitHub CLI (gh) no instalado.')
            if not REPO_BUILD_DIR.exists(): raise RuntimeError(f'No existe {REPO_BUILD_DIR}.')
            self.progreso.emit(10, f'Preparando código fuente para v{self.version}...')
            p_act = self.app_dir / 'actualizaciones_ahorros.py'
            p_act.write_text(re.sub(r"VERSION\s*=\s*['\"][0-9.]+['\"]", f"VERSION = '{self.version}'", p_act.read_text(encoding='utf-8')), encoding='utf-8')
            p_ref = self.app_dir / 'panel_referencia.py'
            p_ref.write_text(re.sub(r"JJ SMART AHORROS [0-9.]+", f"JJ SMART AHORROS {self.version}", p_ref.read_text(encoding='utf-8')), encoding='utf-8')
            self.progreso.emit(20, 'Subiendo código a GitHub y lanzando compilaciones Windows + macOS...')
            for pyf in self.app_dir.glob('*.py'):
                if not pyf.name.startswith('test_'): shutil.copy2(pyf, REPO_BUILD_DIR / pyf.name)
            shutil.copytree(self.app_dir / 'assets', REPO_BUILD_DIR / 'assets', dirs_exist_ok=True)
            self._run(['git', 'add', '.'], cwd=REPO_BUILD_DIR)
            subprocess.run(['git', 'commit', '-m', f'Publicar v{self.version}'], cwd=str(REPO_BUILD_DIR), capture_output=True)
            self._run(['git', 'push', 'origin', 'main'], cwd=REPO_BUILD_DIR)
            tag = f'v{self.version}'
            subprocess.run(['git', 'tag', '-d', tag], cwd=str(REPO_BUILD_DIR), capture_output=True)
            subprocess.run(['git', 'push', 'origin', f':refs/tags/{tag}'], cwd=str(REPO_BUILD_DIR), capture_output=True)
            self._run(['git', 'tag', tag], cwd=REPO_BUILD_DIR); self._run(['git', 'push', 'origin', tag], cwd=REPO_BUILD_DIR)
            self.progreso.emit(35, 'Esperando compilación en GitHub Actions (Windows + macOS)...'); time.sleep(8)
            run_id = ''
            for _ in range(12):
                runs = json.loads(self._run([gh, 'run', 'list', '--repo', REPO_SLUG, '--limit', '1', '--json', 'databaseId,headBranch']))
                if runs and runs[0].get('headBranch') == tag: run_id = str(runs[0]['databaseId']); break
                time.sleep(4)
            if not run_id: raise RuntimeError('No se detectó el workflow en GitHub Actions.')
            for intento in range(90):
                st = json.loads(self._run([gh, 'run', 'view', run_id, '--repo', REPO_SLUG, '--json', 'status,conclusion']))
                if st.get('status') == 'completed':
                    if st.get('conclusion') != 'success': raise RuntimeError(f'Compilación falló ({st.get("conclusion")}).')
                    break
                self.progreso.emit(min(75, 35 + intento), f'Compilando binarios Windows y macOS... ({intento*5}s)'); time.sleep(5)
            else: raise RuntimeError('Tiempo agotado esperando GitHub Actions.')
            self.progreso.emit(80, 'Descargando binarios compilados y firmando Ed25519...')
            out_dir = Path.home() / 'Documents' / 'JJ SMART AHORROS' / 'Publicaciones' / f'v{self.version}_{self.etapa}'
            if out_dir.exists(): shutil.rmtree(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            self._run([gh, 'run', 'download', run_id, '--repo', REPO_SLUG, '--dir', str(out_dir)])
            win_zip = out_dir / 'paquete-windows' / 'JJ_SMART_AHORROS_win.zip'
            win_exe = out_dir / 'paquete-windows' / 'JJ_SMART_AHORROS.exe'
            mac_zip = out_dir / 'paquete-macos' / 'JJ_SMART_AHORROS_mac.zip'
            if not win_zip.exists() or not mac_zip.exists(): raise RuntimeError('Faltan paquetes compilados.')
            final_win = out_dir / 'JJ_SMART_AHORROS_win.zip'; final_mac = out_dir / 'JJ_SMART_AHORROS_mac.zip'
            shutil.move(str(win_zip), str(final_win)); shutil.move(str(mac_zip), str(final_mac))
            assets_subir = [str(final_win), str(final_mac)]
            if win_exe.exists():
                final_exe = out_dir / 'JJ_SMART_AHORROS.exe'; shutil.move(str(win_exe), str(final_exe)); assets_subir.append(str(final_exe))
            sk = asegurar_llaves_firma(self.app_dir)
            m = {'app': APP, 'version': self.version, 'stage': self.etapa, 'notes': self.notas, 'created': datetime.now().isoformat(), 'packages': {
                'windows-x86_64': {'file': final_win.name, 'size': final_win.stat().st_size, 'sha256': sha256_archivo(final_win), 'arch': 'x86_64'},
                'macos-universal2': {'file': final_mac.name, 'size': final_mac.stat().st_size, 'sha256': sha256_archivo(final_mac), 'arch': 'arm64/x86_64'}
            }}
            signed = {'manifest': m, 'signature': base64.b64encode(sk.sign(canon(m))).decode('ascii')}
            upd_json = out_dir / 'update.json'; man_json = out_dir / 'manifest.json'
            c_json = json.dumps(signed, indent=2, ensure_ascii=False); upd_json.write_text(c_json, encoding='utf-8'); man_json.write_text(c_json, encoding='utf-8')
            self.progreso.emit(90, 'Subiendo paquetes verificados a GitHub Releases...')
            subprocess.run([gh, 'release', 'delete', tag, '--repo', REPO_SLUG, '--yes'], capture_output=True)
            self._run([gh, 'release', 'create', tag] + assets_subir + ['--repo', REPO_SLUG, '--title', f'JJ SMART AHORROS {tag}', '--notes', self.notas])
            self._run([gh, 'release', 'upload', tag, str(upd_json), str(man_json), '--repo', REPO_SLUG, '--clobber'])
            rel_info = json.loads(self._run([gh, 'release', 'view', tag, '--repo', REPO_SLUG, '--json', 'assets']))
            nombres_pub = {a['name'] for a in rel_info.get('assets', [])}
            if not {'JJ_SMART_AHORROS_win.zip', 'JJ_SMART_AHORROS_mac.zip', 'update.json', 'manifest.json'}.issubset(nombres_pub):
                raise RuntimeError('Verificación incompleta en Release.')
            self.progreso.emit(100, f'✅ Versión v{self.version} publicada y verificada.')
            self.finalizado.emit(f'✅ PUBLICACIÓN VERIFICADA (v{self.version})\n\n• Windows: {final_win.name}\n• macOS: {final_mac.name}\n• Manifiestos firmados activos en GitHub Releases.')
        except Exception as e: self.error.emit(str(e))

def verificar_acceso_propietario(parent):
    if not (Path(__file__).resolve().parent / 'privada.key').exists() and not os.environ.get('JJ_AHORROS_OWNER_KEY'):
        QMessageBox.warning(parent, 'Acceso restringido', 'Herramienta exclusiva del desarrollador.'); return False
    clave, ok = QInputDialog.getText(parent, 'Autorización Propietario', 'Clave maestra de publicación:', QLineEdit.Password)
    if not ok or clave != clave_dueno():
        if ok: QMessageBox.warning(parent, 'Acceso denegado', 'Clave de propietario incorrecta.')
        return False
    return True

class ControlPropietario(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.app_dir = Path(__file__).resolve().parent
        self.setWindowTitle('Publicar actualización (Desarrollador) · JJ SMART AHORROS'); self.resize(700, 520)
        self.setStyleSheet('QDialog{background:#00162c;color:white;} QLabel{color:#e6f4ff;} QPushButton{background:#0b4f82;color:white;font-weight:bold;padding:10px 18px;border:1px solid #3ea6e8;border-radius:8px;} QTextEdit,QLineEdit,QComboBox{background:#001122;color:white;border:1px solid #1b527c;border-radius:6px;padding:6px;} QProgressBar{background:#001122;border:1px solid #1b527c;border-radius:6px;text-align:center;color:white;height:22px;} QProgressBar::chunk{background:#2ea043;border-radius:5px;}')
        cfg = leer_config_canal(); box = QVBoxLayout(self)
        box.addWidget(QLabel(f'<b>Publicador Multiplataforma (Windows + macOS)</b> · Versión actual: v{_upd.VERSION}'))
        r1 = QHBoxLayout(); p = _upd.VERSION.split('.')
        self.inp_ver = QLineEdit(f'{p[0]}.{p[1]}.{int(p[2])+1}' if len(p)==3 and p[2].isdigit() else '1.2.1')
        self.cmb_etapa = QComboBox(); self.cmb_etapa.addItems(['produccion', 'piloto', 'interno']); self.cmb_etapa.setCurrentText(cfg.get('canal', 'produccion'))
        r1.addWidget(QLabel('Nueva versión:')); r1.addWidget(self.inp_ver); r1.addWidget(QLabel('Canal:')); r1.addWidget(self.cmb_etapa); box.addLayout(r1)
        box.addWidget(QLabel('<b>Novedades de esta versión:</b>'))
        self.txt_notas = QTextEdit(); self.txt_notas.setPlainText('- Mejoras de rendimiento y estabilidad.\n- Correcciones generales.'); box.addWidget(self.txt_notas, 1)
        self.barra = QProgressBar(); self.barra.setRange(0, 100); self.barra.setValue(0)
        self.lbl_res = QLabel('Listo para compilar, firmar y publicar.'); self.lbl_res.setWordWrap(True); box.addWidget(self.barra); box.addWidget(self.lbl_res)
        bh = QHBoxLayout(); self.btn_pub = QPushButton('🚀 Compilar, Firmar y Publicar Actualización'); btn_c = QPushButton('Cerrar')
        bh.addWidget(self.btn_pub); bh.addWidget(btn_c); box.addLayout(bh)
        self.btn_pub.clicked.connect(self._iniciar); btn_c.clicked.connect(self.accept)

    def _iniciar(self):
        ver = self.inp_ver.text().strip()
        if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', ver): QMessageBox.warning(self, 'Versión inválida', 'Usa formato 1.2.1'); return
        notas = self.txt_notas.toPlainText().strip()
        if not notas: QMessageBox.warning(self, 'Faltan novedades', 'Escribe las novedades.'); return
        if QMessageBox.question(self, 'Confirmar', f'¿Compilar v{ver} para Windows y macOS, firmar y publicar?') != QMessageBox.Yes: return
        self.btn_pub.setEnabled(False)
        self.hp = HiloPublicarMultiplataforma(self.app_dir, ver, self.cmb_etapa.currentText(), notas)
        self.hp.progreso.connect(lambda p, t: (self.barra.setValue(p), self.lbl_res.setText(t)))
        self.hp.finalizado.connect(lambda m: (self.btn_pub.setEnabled(True), self.lbl_res.setText(m), QMessageBox.information(self, 'Éxito', m)))
        self.hp.error.connect(lambda e: (self.btn_pub.setEnabled(True), self.lbl_res.setText(f'⚠️ {e}'), QMessageBox.critical(self, 'Error', e))); self.hp.start()

PanelPropietario = ControlPropietario
