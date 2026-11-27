import base64, hashlib, hmac, json, os, re, secrets, zipfile
from datetime import datetime
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QTextEdit, QPushButton, QMessageBox, QInputDialog
)
from ahorros_datos import ruta_datos
from actualizaciones_ahorros import APP, VERSION, clave_dueno, leer_config_canal, guardar_config_canal
from updater_independiente import canon, sha256_archivo

def _pin_file() -> Path:
    p = ruta_datos() / 'Publicador' / 'propietario_auth.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def verificar_acceso_propietario(parent) -> bool:
    pf = _pin_file()
    if not pf.exists():
        p1, ok1 = QInputDialog.getText(parent, 'Configurar Propietario', 'Crea tu contraseña maestra de propietario (mínimo 6 caracteres):', QLineEdit.Password)
        if not ok1 or len(p1.strip()) < 6:
            QMessageBox.warning(parent, 'Acceso cancelado', 'Debes definir una contraseña de al menos 6 caracteres.'); return False
        p2, ok2 = QInputDialog.getText(parent, 'Confirmar Contraseña', 'Repite tu contraseña maestra:', QLineEdit.Password)
        if not ok2 or p1 != p2:
            QMessageBox.warning(parent, 'No coincide', 'Las contraseñas no coinciden.'); return False
        salt = secrets.token_hex(16)
        h = hashlib.pbkdf2_hmac('sha256', p1.encode('utf-8'), bytes.fromhex(salt), 200000).hex()
        pf.write_text(json.dumps({'salt': salt, 'hash': h}), encoding='utf-8')
        QMessageBox.information(parent, 'Propietario registrado', 'Contraseña maestra configurada con éxito en este equipo.')
        return True
    pwd, ok = QInputDialog.getText(parent, 'Control Exclusivo del Propietario', 'Ingresa tu contraseña maestra de propietario:', QLineEdit.Password)
    if not ok or not pwd: return False
    data = json.loads(pf.read_text(encoding='utf-8'))
    calc = hashlib.pbkdf2_hmac('sha256', pwd.encode('utf-8'), bytes.fromhex(data['salt']), 200000).hex()
    if not hmac.compare_digest(calc, data['hash']):
        QMessageBox.warning(parent, 'Acceso denegado', 'Contraseña de propietario incorrecta.'); return False
    return True

def asegurar_llaves_firma(app_dir: Path) -> Ed25519PrivateKey:
    priv_p = clave_dueno()
    pub_p = app_dir / 'assets' / 'actualizaciones.pub'
    priv_p.parent.mkdir(parents=True, exist_ok=True)
    if not priv_p.exists():
        sk = Ed25519PrivateKey.generate()
        priv_p.write_bytes(sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
        if os.name != 'nt': priv_p.chmod(0o600)
        pub_p.write_bytes(sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        return sk
    sk = Ed25519PrivateKey.from_private_bytes(priv_p.read_bytes())
    pub_bytes = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if not pub_p.exists() or pub_p.read_bytes() != pub_bytes:
        pub_p.write_bytes(pub_bytes)
    return sk

class PanelPropietario(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Panel Exclusivo del Propietario · Control de Versiones')
        self.resize(680, 480)
        self.app_dir = Path(__file__).resolve().parent
        cfg = leer_config_canal()
        box = QVBoxLayout(self)
        box.addWidget(QLabel('<b>🔐 Control Maestro de Publicaciones (Firma Ed25519 + Etapas)</b>'))
        frm = QFormLayout()
        self.inp_repo = QLineEdit(cfg.get('url', ''))
        self.inp_ver = QLineEdit('1.1.0')
        self.cmb_etapa = QComboBox(); self.cmb_etapa.addItems(['interno', 'piloto', 'produccion'])
        self.txt_notas = QTextEdit(); self.txt_notas.setPlainText('- Registro continuo de ahorros con lista permanente de socios.\n- Historial y reimpresión de recibos por socio.\n- Sistema de actualizaciones seguras por internet y USB.')
        frm.addRow('URL GitHub Releases HTTPS:', self.inp_repo)
        frm.addRow('Nueva versión (ej. 1.1.0):', self.inp_ver)
        frm.addRow('Etapa de liberación:', self.cmb_etapa)
        frm.addRow('Mejoras para notificar:', self.txt_notas)
        box.addLayout(frm)
        self.lbl_res = QLabel('Listo para firmar y empacar localmente. No se publica en internet hasta que tú lo subas.'); self.lbl_res.setWordWrap(True)
        box.addWidget(self.lbl_res)
        btns = QHBoxLayout()
        btn_generar = QPushButton('✍️ 1. Firmar y Generar Paquete Local')
        btn_generar.setStyleSheet('background:#0f766e;color:white;font-weight:bold;padding:10px;')
        btn_pub = QPushButton('🚀 2. Publicar en GitHub Releases (Nube)')
        btn_pub.setStyleSheet('background:#1d4ed8;color:white;font-weight:bold;padding:10px;')
        btns.addWidget(btn_generar); btns.addWidget(btn_pub); box.addLayout(btns)
        btn_generar.clicked.connect(self._firmar_paquete)
        btn_pub.clicked.connect(self._publicar_github)
        self._ultimo_paquete = None

    def _firmar_paquete(self):
        ver = self.inp_ver.text().strip()
        if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', ver):
            QMessageBox.warning(self, 'Versión inválida', 'Usa formato numérico como 1.1.0'); return
        guardar_config_canal(self.inp_repo.text(), self.cmb_etapa.currentText())
        sk = asegurar_llaves_firma(self.app_dir)
        out_dir = Path.home() / 'Documents' / 'JJ SMART AHORROS' / 'Publicaciones' / f'v{ver}_{self.cmb_etapa.currentText()}'
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_name = f'JJ_AHORROS_UPDATE_{ver}.zip'; zip_path = out_dir / zip_name
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for item in self.app_dir.iterdir():
                if item.name in ('__pycache__', '.venv', 'build', 'dist') or item.name.endswith('.bak_continuo') or item.name.endswith('.bak_v109'): continue
                if item.is_file(): z.write(item, f'app/{item.name}')
                elif item.is_dir():
                    for sub in item.rglob('*'):
                        if sub.is_file() and '__pycache__' not in sub.parts:
                            z.write(sub, f'app/{sub.relative_to(self.app_dir)}')
        m = {'app': APP, 'version': ver, 'stage': self.cmb_etapa.currentText(), 'file': zip_name, 'size': zip_path.stat().st_size, 'sha256': sha256_archivo(zip_path), 'notes': self.txt_notas.toPlainText().strip(), 'created': datetime.now().isoformat()}
        signed = {'manifest': m, 'signature': base64.b64encode(sk.sign(canon(m))).decode('ascii')}
        (out_dir / 'manifest.json').write_text(json.dumps(signed, indent=2, ensure_ascii=False), encoding='utf-8')
        self._ultimo_paquete = (ver, out_dir, zip_path, out_dir / 'manifest.json', self.txt_notas.toPlainText().strip())
        self.lbl_res.setText(f"✅ Paquete firmado en:\n{out_dir}\n\n1. Pruébalo con 'Instalar desde Memoria USB' o canal '{m['stage']}'.\n2. Cuando esté verificado, sube ambos archivos ({zip_name} y manifest.json) a GitHub Releases.")

    def _publicar_github(self):
        if not self._ultimo_paquete:
            QMessageBox.information(self, 'Primero firma el paquete', 'Pulsa primero "1. Firmar y Generar Paquete Local" y pruébalo antes de publicar.'); return
        ver, out_dir, zp, mp, notas = self._ultimo_paquete
        if QMessageBox.question(self, 'Autorizar publicación en la nube', f'¿Confirmas publicar la versión v{ver} para todos los clientes autorizados en GitHub Releases?') != QMessageBox.Yes:
            return
        import subprocess, shutil
        gh_bin = shutil.which('gh') or '/opt/homebrew/bin/gh'
        res = subprocess.run([gh_bin, 'release', 'create', f'v{ver}', str(zp), str(mp), '--repo', 'joty-2/jj-smart-ahorros-updates', '--title', f'JJ SMART AHORROS v{ver}', '--notes', notas], capture_output=True, text=True)
        if res.returncode == 0:
            self.lbl_res.setText(f"🚀 ¡PUBLICADO EN LA NUBE CON ÉXITO!\n{res.stdout.strip()}\nTodos tus clientes en cualquier provincia recibirán la notificación automáticamente.")
        else:
            QMessageBox.warning(self, 'Aviso de publicación', res.stderr or res.stdout)
