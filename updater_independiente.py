import time
import base64, hashlib, json, os, platform, shutil, sqlite3, subprocess, sys, time, zipfile
from datetime import datetime
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open('rb') as f:
        for chunk in iter(lambda: f.read(262144), b''):
            h.update(chunk)
    return h.hexdigest()

def canon(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')

def verificar_integridad_db(db_path: Path) -> bool:
    if not db_path.exists():
        return True
    try:
        con = sqlite3.connect(str(db_path))
        res = con.execute('PRAGMA integrity_check').fetchone()
        con.close()
        return bool(res and str(res[0]).lower() == 'ok')
    except Exception:
        return False

def clave_plataforma() -> str:
    so = 'windows' if sys.platform == 'win32' else ('macos' if sys.platform == 'darwin' else sys.platform)
    arq = platform.machine().lower()
    arq = 'x86_64' if arq in ('amd64', 'x86_64') else ('arm64' if arq in ('arm64', 'aarch64') else arq)
    return f'{so}-{arq}'

def seleccionar_paquete(m: dict) -> dict:
    paquetes = m.get('packages') or {}
    kp = clave_plataforma()
    if kp in paquetes:
        return paquetes[kp]
    if sys.platform == 'darwin' and 'macos-universal2' in paquetes:
        return paquetes['macos-universal2']
    if sys.platform == 'win32' and 'windows-x86_64' in paquetes:
        return paquetes['windows-x86_64']
    if m.get('file') and m.get('sha256') and m.get('size'):
        return {'file': m['file'], 'sha256': m['sha256'], 'size': m['size']}
    raise ValueError(f'No existe paquete compatible para {kp}.')

def verificar_paquete_firmado(zip_path: Path, manifest_path: Path, pub_path: Path) -> dict:
    doc = json.loads(manifest_path.read_text(encoding='utf-8'))
    m = doc['manifest']
    sig = base64.b64decode(doc['signature'], validate=True)
    Ed25519PublicKey.from_public_bytes(pub_path.read_bytes()).verify(sig, canon(m))
    if m.get('app') != 'JJ_SMART_AHORROS':
        raise ValueError('El paquete no corresponde a JJ SMART AHORROS.')
    pkg = seleccionar_paquete(m)
    if not zip_path.exists() or zip_path.stat().st_size != int(pkg['size']):
        raise ValueError('Tamano del paquete no coincide con el manifiesto firmado.')
    if sha256_archivo(zip_path) != pkg['sha256']:
        raise ValueError('Integridad SHA-256 fallida: archivo alterado o incompleto.')
    return m

def registrar_historial(datos_dir: Path, entrada: dict):
    hp = datos_dir / 'Actualizaciones' / 'historial_actualizaciones.json'
    hp.parent.mkdir(parents=True, exist_ok=True)
    try:
        items = json.loads(hp.read_text(encoding='utf-8')) if hp.exists() else []
    except Exception:
        items = []
    items.insert(0, entrada)
    hp.write_text(json.dumps(items[:50], indent=2, ensure_ascii=False), encoding='utf-8')

def ejecutar_actualizacion(destino_app: Path, datos_dir: Path, zip_path: Path, manifest_path: Path, pub_path: Path, cmd_relanzar: list):
    upd_dir = datos_dir / 'Actualizaciones'
    upd_dir.mkdir(parents=True, exist_ok=True)
    log_path = upd_dir / 'ultimo_update.log'
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    rb_dir = datos_dir / 'Respaldos_Rollback' / f'rollback_{ts}'
    rb_app, rb_db = rb_dir / 'app_anterior', rb_dir / 'ahorros.db.bak'
    time.sleep(1.5)
    version_obj, notas_obj = '?', ''
    try:
        m = verificar_paquete_firmado(zip_path, manifest_path, pub_path)
        version_obj, notas_obj = str(m['version']), str(m.get('notes', ''))
        rb_app.mkdir(parents=True, exist_ok=True)
        db_actual = datos_dir / 'ahorros.db'
        if db_actual.exists():
            if not verificar_integridad_db(db_actual):
                raise RuntimeError('La base de datos actual no paso la verificacion de integridad.')
            shutil.copy2(db_actual, rb_db)
            if sha256_archivo(db_actual) != sha256_archivo(rb_db):
                raise RuntimeError('Fallo la verificacion SHA-256 del respaldo de ahorros.db.')

        es_bundle_mac = sys.platform == 'darwin' and str(destino_app).endswith('.app')
        if es_bundle_mac:
            shutil.copytree(destino_app, rb_app / destino_app.name, symlinks=True)
        else:
            for item in destino_app.iterdir():
                if item.name in ('__pycache__', '.venv', '.venv_bak', 'build', 'dist'):
                    continue
                dst = rb_app / item.name
                shutil.copytree(item, dst, dirs_exist_ok=True) if item.is_dir() else shutil.copy2(item, dst)

        stg = upd_dir / f'staging_{ts}'
        if stg.exists():
            shutil.rmtree(stg)
        with zipfile.ZipFile(zip_path, 'r') as z:
            for info in z.infolist():
                if info.filename.startswith('/') or '..' in info.filename or 'ahorros.db' in info.filename.lower():
                    raise ValueError(f'Ruta bloqueada: {info.filename}')
            z.extractall(stg)

        apps_extraidas = list(stg.glob('*.app'))
        if es_bundle_mac and apps_extraidas:
            tmp_destino = destino_app.parent / f'{destino_app.name}.new_{ts}'
            if tmp_destino.exists():
                shutil.rmtree(tmp_destino)
            shutil.copytree(apps_extraidas[0], tmp_destino, symlinks=True)
            subprocess.run(['xattr', '-cr', str(tmp_destino)], check=False)
            macos_bin = tmp_destino / 'Contents' / 'MacOS'
            if macos_bin.is_dir():
                for fbin in macos_bin.iterdir():
                    if fbin.is_file():
                        fbin.chmod(0o755)
            shutil.rmtree(destino_app)
            tmp_destino.rename(destino_app)
        else:
            origen = stg / 'app' if (stg / 'app').is_dir() else stg
            for item in origen.iterdir():
                if item.name in ('ahorros.db', 'privada.key'):
                    continue
                dst = destino_app / item.name
                if item.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(item, dst)
                else:
                    for _intento in range(25):
                        try:
                            if os.name == 'nt' and dst.exists() and dst.suffix.lower() == '.exe':
                                viejo = dst.with_name(dst.name + '.old')
                                try:
                                    if viejo.exists(): viejo.unlink()
                                    dst.rename(viejo)
                                except Exception:
                                    pass
                            shutil.copy2(item, dst)
                            break
                        except PermissionError:
                            time.sleep(0.4)
                    else:
                        shutil.copy2(item, dst)

        shutil.rmtree(stg, ignore_errors=True)
        if db_actual.exists() and not verificar_integridad_db(db_actual):
            raise RuntimeError('Integridad de ahorros.db comprometida tras instalar.')

        (upd_dir / 'pendiente_confirmacion.json').write_text(json.dumps({
            'version': version_obj, 'notes': notas_obj, 'fecha': datetime.now().isoformat()
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        log_path.write_text(f'[{ts}] OK -> Instalada v{version_obj}\n', encoding='utf-8')
    except Exception as err:
        try:
            if sys.platform == 'darwin' and str(destino_app).endswith('.app') and (rb_app / destino_app.name).exists():
                if destino_app.exists():
                    shutil.rmtree(destino_app)
                shutil.copytree(rb_app / destino_app.name, destino_app, symlinks=True)
            elif rb_app.exists():
                for item in rb_app.iterdir():
                    dst = destino_app / item.name
                    if item.is_dir():
                        if dst.exists():
                            shutil.rmtree(dst)
                        shutil.copytree(item, dst)
                    else:
                        shutil.copy2(item, dst)
            if rb_db.exists():
                shutil.copy2(rb_db, datos_dir / 'ahorros.db')
        except Exception:
            pass
        registrar_historial(datos_dir, {'version': version_obj, 'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'estado': 'Error (Rollback restaurado)', 'notas': str(err)})
        log_path.write_text(f'[{ts}] ROLLBACK EJECUTADO: {err}\n', encoding='utf-8')
    finally:
        if cmd_relanzar:
            env = os.environ.copy()
            env.pop('_MEIPASS2', None)
            env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
            subprocess.Popen(cmd_relanzar, env=env, close_fds=True, start_new_session=True)

if __name__ == '__main__':
    if len(sys.argv) >= 6:
        ejecutar_actualizacion(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]), sys.argv[6:])
