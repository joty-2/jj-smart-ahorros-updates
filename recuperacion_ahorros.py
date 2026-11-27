"""Recuperacion de acceso mediante una clave guardada por el propietario."""
import hashlib,hmac,re,secrets,time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QLineEdit,
    QPushButton,QMessageBox,QCheckBox,QDialogButtonBox,QApplication)


def preparar(datos):
    with datos.conexion() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS recuperacion_acceso (
        id INTEGER PRIMARY KEY CHECK(id=1),hash TEXT NOT NULL,
        intentos INTEGER NOT NULL DEFAULT 0,bloqueado_hasta INTEGER NOT NULL DEFAULT 0)''')


def usuario(datos):
    with datos.conexion() as db:rows=db.execute('SELECT usuario FROM administrador').fetchall()
    if len(rows)!=1:raise ValueError('No se reconoce un unico administrador.')
    return rows[0][0]


def configurada(datos):
    preparar(datos)
    with datos.conexion() as db:return bool(db.execute('SELECT 1 FROM recuperacion_acceso WHERE id=1').fetchone())


def normalizar(code):return re.sub(r'[\s-]','',code).upper()


def guardar_clave(datos,password,code):
    preparar(datos);actual=usuario(datos)
    if not datos.entrar(actual,password):raise ValueError('La contrasena actual es incorrecta. No se cambio la recuperacion.')
    code=normalizar(code)
    if not re.fullmatch('[0-9A-F]{32}',code):raise ValueError('Clave de recuperacion no valida.')
    hashed=datos.clave(code)
    backup=datos.respaldo()
    with datos.conexion() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO recuperacion_acceso(id,hash) VALUES (1,?) ON CONFLICT(id) DO UPDATE SET hash=excluded.hash,intentos=0,bloqueado_hasta=0',(hashed,))
    return backup


def restablecer(datos,code,password):
    preparar(datos)
    if len(password)<8:raise ValueError('La contrasena nueva debe tener al menos 8 caracteres.')
    now=int(time.time());error=None
    with datos.conexion() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM recuperacion_acceso WHERE id=1').fetchone()
        if row is None:raise ValueError('Primero debes configurar una clave de recuperacion despues de iniciar sesion.')
        if row['bloqueado_hasta']>now:raise ValueError('Espera 15 minutos desde el ultimo bloqueo antes de volver a intentar.')
        _,_,salt,_=row['hash'].split('$')
        valid=hmac.compare_digest(row['hash'],datos.clave(normalizar(code),salt))
        if not valid:
            attempts=row['intentos']+1 if row['bloqueado_hasta']==0 else 1
            db.execute('UPDATE recuperacion_acceso SET intentos=?,bloqueado_hasta=? WHERE id=1',(attempts,now+900 if attempts>=5 else 0))
            error='Clave de recuperacion incorrecta.' if attempts<5 else 'Demasiados intentos. Espera 15 minutos.'
        else:
            # Respaldo antes de cambiar el unico campo de acceso.
            # La transaccion aun no ha escrito, por lo que la copia no queda bloqueada.
            backup=datos.respaldo()
            updated=db.execute('UPDATE administrador SET hash=? WHERE usuario=?',(datos.clave(password),usuario_en_db(db))).rowcount
            if updated!=1:raise ValueError('No se pudo identificar al administrador.')
            db.execute('UPDATE recuperacion_acceso SET intentos=0,bloqueado_hasta=0 WHERE id=1')
    if error:raise ValueError(error)
    return backup


def usuario_en_db(db):
    rows=db.execute('SELECT usuario FROM administrador').fetchall()
    if len(rows)!=1:raise ValueError('No se reconoce un unico administrador.')
    return rows[0][0]


def seguridad(datos,parent):
    actual=usuario(datos);d=QDialog(parent);d.setWindowTitle('Seguridad y recuperacion');d.resize(570,380)
    layout=QVBoxLayout(d)
    title=QLabel('Guarda tu clave de recuperacion');title.setStyleSheet('font-size:20px;font-weight:bold;');layout.addWidget(title)
    note=QLabel('Esta clave permite crear una contrasena nueva si la olvidas. Guardala fuera de esta computadora. Si generas otra, la anterior dejara de funcionar.');note.setWordWrap(True);layout.addWidget(note)
    layout.addWidget(QLabel('Usuario: '+actual))
    code=secrets.token_hex(16).upper()
    code='-'.join(code[i:i+8] for i in range(0,len(code),8))
    field=QLineEdit(code);field.setReadOnly(True);field.setStyleSheet('font-family:monospace;font-size:16px;');layout.addWidget(field)
    copiar=QPushButton('Copiar clave de recuperación');layout.addWidget(copiar)
    aviso=QLabel('Paso 1: copia y guarda la clave. Paso 2: marca la casilla. Paso 3: escribe tu contraseña y pulsa Activar recuperación.');aviso.setWordWrap(True);layout.addWidget(aviso)
    copiar.clicked.connect(lambda:(QApplication.clipboard().setText(code),aviso.setText('Clave copiada. Guárdala en un lugar seguro y marca la casilla de abajo.')))
    check=QCheckBox('Ya guardé esta clave en un lugar seguro.');layout.addWidget(check)
    form=QFormLayout();password=QLineEdit();password.setEchoMode(QLineEdit.Password);form.addRow('Contrasena actual:',password);layout.addLayout(form)
    buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);save=buttons.button(QDialogButtonBox.Save);save.setText('Activar recuperacion');save.setEnabled(True);buttons.rejected.connect(d.reject);layout.addWidget(buttons)
    def activate():
        try:
            if not check.isChecked():
                aviso.setText('Falta marcar «Ya guardé esta clave en un lugar seguro». Copia y guarda la clave antes de activarla.');check.setFocus();return
            if not password.text():
                aviso.setText('Escribe tu contraseña actual de ingreso a JJ SMART AHORROS.');password.setFocus();return
            backup=guardar_clave(datos,password.text(),code);password.clear()
            QMessageBox.information(d,'Recuperacion activada','La clave quedo configurada. Usa «Olvide mi contrasena» en la pantalla de acceso cuando la necesites.\nSe guardo un respaldo de los datos.');d.accept()
        except Exception as e:QMessageBox.warning(d,'No se activo',str(e))
    buttons.accepted.connect(activate);password.returnPressed.connect(activate);d.exec()


def mostrar_recuperacion(datos,parent):
    try:
        actual=usuario(datos)
        if not configurada(datos):
            QMessageBox.information(parent,'Configurar recuperacion por primera vez','Tu usuario es: '+actual+'\n\nAun no hay una clave de recuperacion configurada. Si ya recuerdas tu contrasena, inicia sesion y entra en «Seguridad y acceso».\n\nSi no la recuerdas, usa por esta primera vez el archivo recuperar_acceso_jj_ahorros.py que preparamos. Despues podras configurar la recuperacion dentro de la app.');return
        d=QDialog(parent);d.setWindowTitle('Olvide mi contrasena');d.resize(530,340);layout=QVBoxLayout(d)
        note=QLabel('Usuario: '+actual+'\nIntroduce tu clave de recuperacion y una contrasena nueva. Los socios, ahorros y movimientos se conservaran.');note.setWordWrap(True);layout.addWidget(note)
        form=QFormLayout();code=QLineEdit();code.setEchoMode(QLineEdit.Password);password=QLineEdit();password.setEchoMode(QLineEdit.Password);confirm=QLineEdit();confirm.setEchoMode(QLineEdit.Password)
        form.addRow('Clave de recuperacion:',code);form.addRow('Contrasena nueva:',password);form.addRow('Repetir contrasena:',confirm);layout.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('Restablecer acceso');buttons.rejected.connect(d.reject);layout.addWidget(buttons)
        def reset():
            try:
                if password.text()!=confirm.text():raise ValueError('Las contrasenas no coinciden.')
                restablecer(datos,code.text(),password.text());code.clear();password.clear();confirm.clear()
                QMessageBox.information(d,'Acceso recuperado','Tu usuario es '+actual+'. Inicia sesion con la contrasena nueva.');d.accept()
            except Exception as e:QMessageBox.warning(d,'No se recupero el acceso',str(e))
        buttons.accepted.connect(reset);d.exec()
    except Exception as e:QMessageBox.warning(parent,'Recuperacion',str(e))


def recordar_configuracion(datos,parent):
    if not configurada(datos) and QMessageBox.question(parent,'Protege tu acceso','¿Quieres configurar ahora una clave para recuperar el acceso si olvidas la contrasena?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
        seguridad(datos,parent)
