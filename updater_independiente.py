import base64, hashlib, json, os, shutil, subprocess, sys, time, zipfile
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

def verificar_paquete_firmado(zip_path: Path, manifest_path: Path, pub_path: Path) -> dict:
    doc = json.loads(manifest_path.read_text(encoding='utf-8'))
    m = doc['manifest']
    sig = base64.b64decode(doc['signature'], validate=True)
    Ed25519PublicKey.from_public_bytes(pub_path.read_bytes()).verify(sig, canon(m))
    if m.get('app') != 'JJ_SMART_AHORROS':
        raise ValueError('El paquete no corresponde a JJ SMART AHORROS.')
    if not zip_path.exists() or zip_path.stat().st_size != int(m['size']):
        raise ValueError('Tamano del paquete no coincide con el manifiesto firmado.')
    if sha256_archivo(zip_path) != m['sha256']:
        raise ValueError('Integridad SHA-256 fallida: archivo alterado o incompleto.')
    return m

def ejecutar_actualizacion(app_dir: Path, datos_dir: Path, zip_path: Path, manifest_path: Path, cmd_relanzar: list):
    log_path = datos_dir / 'Actualizaciones' / 'ultimo_update.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    rb_dir = datos_dir / 'Respaldos_Rollback' / f'rollback_{ts}'
    rb_app, rb_db = rb_dir / 'app_anterior', rb_dir / 'ahorros.db.bak'
    time.sleep(1.5)
    try:
        m = verificar_paquete_firmado(zip_path, manifest_path, app_dir / 'assets' / 'actualizaciones.pub')
        rb_app.mkdir(parents=True, exist_ok=True)
        db_actual = datos_dir / 'ahorros.db'
        if db_actual.exists():
            shutil.copy2(db_actual, rb_db)
            if sha256_archivo(db_actual) != sha256_archivo(rb_db):
                raise RuntimeError('Fallo la verificacion del respaldo de ahorros.db.')
        for item in app_dir.iterdir():
            if item.name in ('__pycache__', '.venv'): continue
            dst = rb_app / item.name
            shutil.copytree(item, dst, dirs_exist_ok=True) if item.is_dir() else shutil.copy2(item, dst)
        stg = datos_dir / 'Actualizaciones' / f'staging_{ts}'
        if stg.exists(): shutil.rmtree(stg)
        with zipfile.ZipFile(zip_path, 'r') as z:
            for info in z.infolist():
                if info.filename.startswith('/') or '..' in info.filename or 'ahorros.db' in info.filename.lower():
                    raise ValueError(f'Ruta bloqueada: {info.filename}')
            z.extractall(stg)
        origen = stg / 'app' if (stg / 'app').is_dir() else stg
        for item in origen.iterdir():
            if item.name in ('ahorros.db', 'privada.key'): continue
            dst = app_dir / item.name
            if item.is_dir():
                if dst.exists(): shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else: shutil.copy2(item, dst)
        shutil.rmtree(stg, ignore_errors=True)
        log_path.write_text(f"[{ts}] OK -> Actualizado a v{m['version']}\n", encoding='utf-8')
    except Exception as err:
        if rb_app.exists():
            for item in rb_app.iterdir():
                dst = app_dir / item.name
                if item.is_dir():
                    if dst.exists(): shutil.rmtree(dst)
                    shutil.copytree(item, dst)
                else: shutil.copy2(item, dst)
        if rb_db.exists(): shutil.copy2(rb_db, datos_dir / 'ahorros.db')
        log_path.write_text(f"[{ts}] ROLLBACK EJECUTADO: {err}\n", encoding='utf-8')
    finally:
        if cmd_relanzar: subprocess.Popen(cmd_relanzar, cwd=str(app_dir))

if __name__ == '__main__':
    if len(sys.argv) >= 5:
        ejecutar_actualizacion(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5:])
