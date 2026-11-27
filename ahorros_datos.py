"""Contabilidad local de JJ SMART AHORROS. Todos los importes se guardan en centavos."""
from contextlib import contextmanager
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import hashlib,hmac,os,re,secrets,sqlite3,sys
from pathlib import Path

ACCION=10000

def ruta_datos():
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/JJ SMART AHORROS'
    if sys.platform=='win32':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'JJ SMART AHORROS'
    return Path.home()/'.local/share/JJ SMART AHORROS'


def centavos(texto):
    texto=str(texto).strip().replace('RD$','').strip()
    if not re.fullmatch(r'\d+(?:[.,]\d{1,2})?',texto):raise ValueError('Escribe el monto sin separadores de miles. Ejemplo: 200000 o 125.50.')
    try:n=int(Decimal(texto.replace(',','.'))*100)
    except (InvalidOperation,ValueError):raise ValueError('Monto no valido.')
    if n>9223372036854775807:raise ValueError('El monto supera la capacidad tecnica del archivo contable.')
    return n


def dinero(n):return 'RD$ {:,.2f}'.format(Decimal(n)/100)


class Datos:
    def __init__(self,path=None):
        self.path=Path(path) if path else ruta_datos()/'ahorros.db'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.conexion() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS administrador(usuario TEXT PRIMARY KEY,hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS socios(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,telefono TEXT NOT NULL DEFAULT '',creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS aportes(id TEXT PRIMARY KEY,socio_id INTEGER NOT NULL REFERENCES socios(id),fecha TEXT NOT NULL,centavos INTEGER NOT NULL CHECK(centavos>0 AND centavos%10000=0),nota TEXT NOT NULL DEFAULT '',creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS prestamos(id TEXT PRIMARY KEY,socio_id INTEGER NOT NULL REFERENCES socios(id),fecha TEXT NOT NULL,capital INTEGER NOT NULL CHECK(capital>0),interes INTEGER NOT NULL CHECK(interes>=0),nota TEXT NOT NULL DEFAULT '',creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS abonos(id TEXT PRIMARY KEY,prestamo_id TEXT NOT NULL REFERENCES prestamos(id),fecha TEXT NOT NULL,capital INTEGER NOT NULL CHECK(capital>=0),interes INTEGER NOT NULL CHECK(interes>=0),nota TEXT NOT NULL DEFAULT '',creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,CHECK(capital+interes>0));
            CREATE INDEX IF NOT EXISTS idx_aportes_socio_fecha ON aportes(socio_id,fecha);
            CREATE INDEX IF NOT EXISTS idx_abonos_prestamo ON abonos(prestamo_id);
            CREATE TABLE IF NOT EXISTS historial_recibos(id TEXT PRIMARY KEY,socio_id INTEGER NOT NULL REFERENCES socios(id),fecha TEXT NOT NULL,hora TEXT NOT NULL DEFAULT '',centavos INTEGER NOT NULL,acumulado INTEGER NOT NULL,nota TEXT NOT NULL DEFAULT '',creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_recibos_socio ON historial_recibos(socio_id,creado DESC);
            PRAGMA user_version=1;
            ''')
        if os.name!='nt':self.path.chmod(0o600)

    @contextmanager
    def conexion(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:db.rollback();raise
        finally:db.close()

    @staticmethod
    def clave(password,salt=None):
        salt=salt or secrets.token_hex(32)
        value=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
        return 'pbkdf2_sha256$600000$'+salt+'$'+value

    def necesita_admin(self):
        with self.conexion() as db:return db.execute('SELECT COUNT(*) FROM administrador').fetchone()[0]==0

    def crear_admin(self,usuario,password):
        usuario=usuario.strip()
        if not usuario or len(password)<8:raise ValueError('Escribe un usuario y una contrasena de al menos 8 caracteres.')
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM administrador').fetchone():raise ValueError('El administrador ya esta creado.')
            db.execute('INSERT INTO administrador VALUES (?,?)',(usuario,self.clave(password)))

    def entrar(self,usuario,password):
        with self.conexion() as db:row=db.execute('SELECT hash FROM administrador WHERE usuario=?',(usuario.strip(),)).fetchone()
        if not row:
            self.clave(password,salt='00'*32);return False
        _,_,salt,_=row[0].split('$')
        return hmac.compare_digest(row[0],self.clave(password,salt))

    def socios(self):
        with self.conexion() as db:return [dict(r) for r in db.execute('''SELECT s.*,
        COALESCE((SELECT SUM(a.centavos) FROM aportes a WHERE a.socio_id=s.id),0) ahorro,
        COALESCE((SELECT SUM(p.capital) FROM prestamos p WHERE p.socio_id=s.id),0)-COALESCE((SELECT SUM(a.capital) FROM abonos a JOIN prestamos p ON p.id=a.prestamo_id WHERE p.socio_id=s.id),0) deuda
        FROM socios s ORDER BY s.nombre COLLATE NOCASE,s.id''')]

    def socio(self,nombre,telefono):
        nombre=nombre.strip();telefono=telefono.strip()
        if not nombre:raise ValueError('Escribe el nombre del socio.')
        if len(nombre)>150 or len(telefono)>40:raise ValueError('Nombre o telefono demasiado largo.')
        with self.conexion() as db:return db.execute('INSERT INTO socios(nombre,telefono) VALUES (?,?)',(nombre,telefono)).lastrowid

    @staticmethod
    def fecha(value):
        try:d=date.fromisoformat(value)
        except (ValueError,TypeError):raise ValueError('Fecha no valida.')
        if d>date.today():raise ValueError('No se pueden registrar movimientos con fecha futura.')
        return d.isoformat()

    @staticmethod
    def monto(n,positivo=False):
        if type(n) is not int or n<0 or n>9223372036854775807 or positivo and not n:raise ValueError('Monto no valido.')

    @staticmethod
    def repetir(db,tabla,key,campos):
        row=db.execute('SELECT * FROM '+tabla+' WHERE id=?',(key,)).fetchone()
        if row and any(row[k]!=v for k,v in campos.items()):raise ValueError('La operacion ya existe con otros datos.')
        return bool(row)

    def aportar(self,key,socio,fecha,monto,nota=''):
        self.monto(monto,True);fecha=self.fecha(fecha);nota=nota.strip()
        if monto%ACCION:raise ValueError('Cada accion vale RD$100. El aporte debe ser multiplo de 100.')
        campos={'socio_id':socio,'fecha':fecha,'centavos':monto,'nota':nota}
        hora_actual=datetime.now().strftime('%I:%M:%S %p')
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.repetir(db,'aportes',key,campos):return
            db.execute('INSERT INTO aportes(id,socio_id,fecha,centavos,nota) VALUES (?,?,?,?,?)',(key,socio,fecha,monto,nota))
            acum=int(db.execute('SELECT COALESCE(SUM(centavos),0) FROM aportes WHERE socio_id=?',(socio,)).fetchone()[0])
            db.execute('INSERT OR IGNORE INTO historial_recibos(id,socio_id,fecha,hora,centavos,acumulado,nota) VALUES (?,?,?,?,?,?,?)',(key,socio,fecha,hora_actual,monto,acum,nota))

    def recibos_socio(self, sid):
        with self.conexion() as db:
            rows = db.execute('''
                SELECT a.id, s.nombre AS socio_nombre, a.fecha, COALESCE(r.hora, '') AS hora, a.centavos, a.nota,
                       COALESCE(r.acumulado, (SELECT COALESCE(SUM(centavos),0) FROM aportes a2 WHERE a2.socio_id=a.socio_id AND a2.rowid<=a.rowid)) AS acumulado
                FROM aportes a
                JOIN socios s ON s.id = a.socio_id
                LEFT JOIN historial_recibos r ON r.id = a.id
                WHERE a.socio_id=?
                ORDER BY a.fecha DESC, a.rowid DESC
            ''', (int(sid),)).fetchall()
            return [dict(x) for x in rows]

    def eliminar_aporte(self, aporte_id, motivo=''):
        aid = str(aporte_id).strip()
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT a.id, a.socio_id, a.fecha, a.centavos, a.nota, s.nombre FROM aportes a JOIN socios s ON s.id=a.socio_id WHERE a.id=?', (aid,)).fetchone()
            if not row:
                raise ValueError('No se encontró el recibo o aporte seleccionado.')
            sid = int(row['socio_id'])
            db.execute('''CREATE TABLE IF NOT EXISTS auditoria_anulaciones(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aporte_id TEXT NOT NULL,
                socio_id INTEGER NOT NULL,
                socio_nombre TEXT NOT NULL,
                fecha TEXT NOT NULL,
                centavos INTEGER NOT NULL,
                motivo TEXT NOT NULL DEFAULT '',
                eliminado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )''')
            db.execute('INSERT INTO auditoria_anulaciones(aporte_id,socio_id,socio_nombre,fecha,centavos,motivo) VALUES (?,?,?,?,?,?)',
                       (aid, sid, row['nombre'], row['fecha'], int(row['centavos']), motivo.strip()))
            db.execute('DELETE FROM historial_recibos WHERE id=?', (aid,))
            db.execute('DELETE FROM aportes WHERE id=?', (aid,))
            # Recalcular saldo acumulado historico de los recibos restantes del socio
            rest = db.execute('SELECT id, centavos FROM aportes WHERE socio_id=? ORDER BY fecha ASC, rowid ASC', (sid,)).fetchall()
            acum = 0
            for r in rest:
                acum += int(r['centavos'])
                db.execute('UPDATE historial_recibos SET acumulado=? WHERE id=?', (acum, r['id']))

    @staticmethod
    def caja(db,fecha=None):
        # Las consultas filtran por fecha cuando se registra un movimiento retroactivo.
        limit=fecha or '9999-12-31'
        a=int(db.execute('SELECT COALESCE(SUM(centavos),0) FROM aportes WHERE fecha<=?',(limit,)).fetchone()[0])
        p=int(db.execute('SELECT COALESCE(SUM(capital),0) FROM prestamos WHERE fecha<=?',(limit,)).fetchone()[0])
        b=int(db.execute('SELECT COALESCE(SUM(capital+interes),0) FROM abonos WHERE fecha<=?',(limit,)).fetchone()[0])
        return a-p+b

    @staticmethod
    def validar_caja(db):
        saldo=0
        for row in db.execute('''SELECT fecha,SUM(monto) monto FROM (
        SELECT fecha,centavos monto FROM aportes UNION ALL SELECT fecha,-capital FROM prestamos UNION ALL SELECT fecha,capital+interes FROM abonos
        ) GROUP BY fecha ORDER BY fecha'''):
            saldo+=row['monto']
            if saldo<0:raise ValueError('El movimiento dejaria la caja sin fondos en la fecha indicada.')

    def prestar(self,key,socio,fecha,capital,interes,nota=''):
        self.monto(capital,True);self.monto(interes);fecha=self.fecha(fecha);nota=nota.strip()
        campos={'socio_id':socio,'fecha':fecha,'capital':capital,'interes':interes,'nota':nota}
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.repetir(db,'prestamos',key,campos):return
            if capital>self.caja(db,fecha):raise ValueError('No hay suficiente dinero disponible en esa fecha para desembolsar el prestamo.')
            db.execute('INSERT INTO prestamos(id,socio_id,fecha,capital,interes,nota) VALUES (?,?,?,?,?,?)',(key,socio,fecha,capital,interes,nota))
            self.validar_caja(db)

    def prestamos(self):
        with self.conexion() as db:return [dict(r) for r in db.execute('''SELECT p.*,s.nombre,
        p.capital-COALESCE((SELECT SUM(a.capital) FROM abonos a WHERE a.prestamo_id=p.id),0) capital_pendiente,
        p.interes-COALESCE((SELECT SUM(a.interes) FROM abonos a WHERE a.prestamo_id=p.id),0) interes_pendiente
        FROM prestamos p JOIN socios s ON s.id=p.socio_id ORDER BY p.fecha DESC,p.creado DESC''')]

    def abonar(self,key,prestamo,fecha,capital,interes,nota=''):
        self.monto(capital);self.monto(interes);fecha=self.fecha(fecha);nota=nota.strip()
        if not capital+interes:raise ValueError('Escribe un abono a capital o un interes pagado.')
        campos={'prestamo_id':prestamo,'fecha':fecha,'capital':capital,'interes':interes,'nota':nota}
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.repetir(db,'abonos',key,campos):return
            p=db.execute('SELECT * FROM prestamos WHERE id=?',(prestamo,)).fetchone()
            if not p:raise ValueError('Prestamo no encontrado.')
            if fecha<p['fecha']:raise ValueError('El abono no puede ser anterior al desembolso.')
            pagado=db.execute('SELECT COALESCE(SUM(capital),0),COALESCE(SUM(interes),0) FROM abonos WHERE prestamo_id=?',(prestamo,)).fetchone()
            if capital>p['capital']-pagado[0] or interes>p['interes']-pagado[1]:raise ValueError('El abono supera el capital o el interes pendiente.')
            db.execute('INSERT INTO abonos(id,prestamo_id,fecha,capital,interes,nota) VALUES (?,?,?,?,?,?)',(key,prestamo,fecha,capital,interes,nota))
            self.validar_caja(db)

    def resumen(self,year=None):
        year=year or date.today().year;start=f'{year:04d}-01-01';end=f'{year:04d}-12-31'
        with self.conexion() as db:
            scalar=lambda sql,args=():int(db.execute(sql,args).fetchone()[0])
            aportes=scalar('SELECT COALESCE(SUM(centavos),0) FROM aportes')
            prestado=scalar('SELECT COALESCE(SUM(capital),0) FROM prestamos')
            devuelto=scalar('SELECT COALESCE(SUM(capital),0) FROM abonos')
            interes=scalar('SELECT COALESCE(SUM(interes),0) FROM abonos')
            interes_prometido=scalar('SELECT COALESCE(SUM(interes),0) FROM prestamos')
            return {'socios':scalar('SELECT COUNT(*) FROM socios'),'aportes':aportes,'acciones':aportes//ACCION,'caja':self.caja(db),'capital_pendiente':prestado-devuelto,'interes_cobrado':interes,'interes_pendiente':interes_prometido-interes,'aportes_anuales':scalar('SELECT COALESCE(SUM(centavos),0) FROM aportes WHERE fecha BETWEEN ? AND ?',(start,end)),'interes_anual':scalar('SELECT COALESCE(SUM(interes),0) FROM abonos WHERE fecha BETWEEN ? AND ?',(start,end))}

    def movimientos(self):
        with self.conexion() as db:return [dict(r) for r in db.execute('''SELECT * FROM (
        SELECT a.fecha,s.nombre,'APORTE' tipo,a.centavos importe,a.nota,a.creado FROM aportes a JOIN socios s ON s.id=a.socio_id
        UNION ALL SELECT p.fecha,s.nombre,'PRESTAMO',-p.capital,p.nota,p.creado FROM prestamos p JOIN socios s ON s.id=p.socio_id
        UNION ALL SELECT a.fecha,s.nombre,'ABONO',a.capital+a.interes,a.nota,a.creado FROM abonos a JOIN prestamos p ON p.id=a.prestamo_id JOIN socios s ON s.id=p.socio_id
        ) ORDER BY fecha DESC,creado DESC''')]

    def respaldo(self):
        folder=self.path.parent/'Respaldos';folder.mkdir(exist_ok=True)
        target=folder/('ahorros_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.db')
        src=sqlite3.connect(self.path);dst=sqlite3.connect(target)
        try:src.backup(dst)
        finally:dst.close();src.close()
        if os.name!='nt':target.chmod(0o600)
        return target

    def editar_socio(self,i,n):
        if not str(n).strip(): raise ValueError("Nombre vacío")
        with self.conexion() as db: db.execute("UPDATE socios SET nombre=? WHERE id=?",(str(n).strip(),int(i)))
    def eliminar_socio(self,i):
        with self.conexion() as db:
            a=db.execute("SELECT COUNT(*) FROM aportes WHERE socio_id=?",(int(i),)).fetchone()[0]
            p=db.execute("SELECT COUNT(*) FROM prestamos WHERE socio_id=?",(int(i),)).fetchone()[0]
            if a or p: raise ValueError(f"Tiene {a} aportes y {p} préstamos")
            db.execute("DELETE FROM socios WHERE id=?",(int(i),))
