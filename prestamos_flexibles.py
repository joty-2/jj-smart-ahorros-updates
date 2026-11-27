"""Interes mensual fijo, capital flexible y prioridad del interes vencido."""
import calendar
from datetime import date
from ahorros_datos import Datos as DatosBase


def mes(fecha,desplazamiento):
    d=date.fromisoformat(fecha);n=d.year*12+d.month-1+desplazamiento;y,m=divmod(n,12);m+=1
    return date(y,m,min(d.day,calendar.monthrange(y,m)[1])).isoformat()


def cuotas_vencidas(primera,hasta):
    a=date.fromisoformat(primera);b=date.fromisoformat(hasta)
    if b<a:return 0
    n=(b.year-a.year)*12+b.month-a.month
    return n+1 if mes(primera,n)<=hasta else n


class Datos(DatosBase):
    def __init__(self,path=None):
        super().__init__(path)
        with self.conexion() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS prestamos_mensuales (
            prestamo_id TEXT PRIMARY KEY REFERENCES prestamos(id),
            cuotas_previstas INTEGER NOT NULL CHECK(cuotas_previstas>0),
            interes_mensual INTEGER NOT NULL CHECK(interes_mensual>=0),
            primer_vencimiento TEXT NOT NULL, liquidado_fecha TEXT)''')

    @staticmethod
    def _saldo(db,identificador,fecha):
        p=db.execute('SELECT * FROM prestamos WHERE id=?',(identificador,)).fetchone()
        if p is None:raise ValueError('Prestamo no encontrado.')
        plan=db.execute('SELECT * FROM prestamos_mensuales WHERE prestamo_id=?',(identificador,)).fetchone()
        if fecha<p['fecha']:raise ValueError('El pago no puede ser anterior al prestamo.')
        pagado=db.execute('SELECT COALESCE(SUM(capital),0),COALESCE(SUM(interes),0) FROM abonos WHERE prestamo_id=? AND fecha<=?',(identificador,fecha)).fetchone()
        limit=min(fecha,plan['liquidado_fecha']) if plan and plan['liquidado_fecha'] else fecha
        total=cuotas_vencidas(plan['primer_vencimiento'],limit)*plan['interes_mensual'] if plan else p['interes']
        return {'capital':p['capital']-pagado[0],'interes':max(0,total-pagado[1]),'interes_generado':total,'interes_pagado':pagado[1],
            'cuotas_vencidas':cuotas_vencidas(plan['primer_vencimiento'],limit) if plan else None,'plan':dict(plan) if plan else None,'prestamo':dict(p)}

    def saldo_pago(self,prestamo,fecha):
        fecha=self.fecha(fecha)
        with self.conexion() as db:return self._saldo(db,prestamo,fecha)

    def prestar_mensual(self,key,socio,fecha,capital,interes_mensual,cuotas,primera,nota=''):
        fecha=self.fecha(fecha);self.monto(capital,True);self.monto(interes_mensual)
        if type(cuotas) is not int or not 1<=cuotas<=1200:raise ValueError('Indica entre 1 y 1200 cuotas previstas.')
        try:date.fromisoformat(primera);mes(primera,cuotas-1)
        except (ValueError,TypeError):raise ValueError('Fecha de la primera cuota no valida.')
        if primera<fecha:raise ValueError('La primera cuota no puede ser anterior al desembolso.')
        self.monto(interes_mensual*cuotas)
        nota=nota.strip()
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.repetir(db,'prestamos',key,{'socio_id':socio,'fecha':fecha,'capital':capital,'interes':0,'nota':nota}):
                plan=db.execute('SELECT * FROM prestamos_mensuales WHERE prestamo_id=?',(key,)).fetchone()
                if not plan or (plan['cuotas_previstas'],plan['interes_mensual'],plan['primer_vencimiento'])!=(cuotas,interes_mensual,primera):raise ValueError('Esta operacion ya existe con otro plan.')
                return
            if capital>self.caja(db,fecha):raise ValueError('No hay suficiente dinero disponible en esa fecha.')
            db.execute('INSERT INTO prestamos(id,socio_id,fecha,capital,interes,nota) VALUES (?,?,?,?,0,?)',(key,socio,fecha,capital,nota))
            db.execute('INSERT INTO prestamos_mensuales(prestamo_id,cuotas_previstas,interes_mensual,primer_vencimiento) VALUES (?,?,?,?)',(key,cuotas,interes_mensual,primera))
            self.validar_caja(db)

    def pagar(self,key,prestamo,fecha,total,nota='',destino='auto'):
        fecha=self.fecha(fecha);self.monto(total,True);nota=nota.strip()
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM abonos WHERE id=?',(key,)).fetchone()
            if old:
                if old['prestamo_id']!=prestamo or old['fecha']!=fecha or old['capital']+old['interes']!=total or old['nota']!=nota:raise ValueError('El pago ya existe con otros datos.')
                return {'capital':old['capital'],'interes':old['interes']}
            last=db.execute('SELECT MAX(fecha) FROM abonos WHERE prestamo_id=?',(prestamo,)).fetchone()[0]
            if last and fecha<last:raise ValueError('Registra el pago con fecha igual o posterior al ultimo pago de este prestamo.')
            saldo=self._saldo(db,prestamo,fecha)
            if destino=='interes':
                if total>saldo['interes']:raise ValueError('El pago supera el interés vencido pendiente.')
                interest,cap=total,0
            elif destino=='capital':
                if total>saldo['capital']:raise ValueError('El pago supera el capital pendiente.')
                interest,cap=0,total
            else:
                if total>saldo['capital']+saldo['interes']:raise ValueError('El pago supera el capital y el interes vencido pendientes. No se cobran intereses futuros.')
                interest=min(total,saldo['interes']);cap=total-interest
            if cap>saldo['capital']:raise ValueError('El pago supera el capital pendiente.')
            db.execute('INSERT INTO abonos(id,prestamo_id,fecha,capital,interes,nota) VALUES (?,?,?,?,?,?)',(key,prestamo,fecha,cap,interest,nota))
            if saldo['plan'] and cap==saldo['capital']:
                db.execute('UPDATE prestamos_mensuales SET liquidado_fecha=? WHERE prestamo_id=?',(fecha,prestamo))
            self.validar_caja(db)
            return {'capital':cap,'interes':interest}

    def abonar(self,key,prestamo,fecha,capital,interes,nota=''):
        # Mantener la API anterior para prestamos antiguos. El flujo nuevo usa pagar().
        with self.conexion() as db:
            if db.execute('SELECT 1 FROM prestamos_mensuales WHERE prestamo_id=?',(prestamo,)).fetchone():raise ValueError('Usa Registrar pago para aplicar primero el interes vencido.')
        return super().abonar(key,prestamo,fecha,capital,interes,nota)

    def prestamos(self):
        rows=super().prestamos();hoy=date.today().isoformat()
        with self.conexion() as db:
            for p in rows:
                saldo=self._saldo(db,p['id'],max(hoy,p['fecha']))
                plan=saldo['plan'];p['plan_mensual']=plan is not None
                p['capital_pendiente']=saldo['capital'];p['interes_pendiente']=saldo['interes']
                p['interes_generado']=saldo['interes_generado'];p['interes_mensual']=plan['interes_mensual'] if plan else None
                p['cuotas_previstas']=plan['cuotas_previstas'] if plan else None
                p['liquidado_fecha']=plan['liquidado_fecha'] if plan else None
        return rows

    def resumen(self,year=None):
        r=super().resumen(year);r['interes_pendiente']=sum(p['interes_pendiente'] for p in self.prestamos());return r

    def detalle_cuotas(self,prestamo):
        with self.conexion() as db:
            saldo=self._saldo(db,prestamo,date.today().isoformat());plan=saldo['plan']
            if not plan:return [],[dict(a) for a in db.execute('SELECT * FROM abonos WHERE prestamo_id=? ORDER BY fecha,creado',(prestamo,))]
            filas=[];cobrado=saldo['interes_pagado'];hoy=date.today().isoformat()
            # Mostrar todas las previstas y las vencidas adicionales si el plazo se extendio.
            count=max(plan['cuotas_previstas'],saldo['cuotas_vencidas'])
            for n in range(count):
                vencimiento=mes(plan['primer_vencimiento'],n)
                cancelada=bool(plan['liquidado_fecha'] and vencimiento>plan['liquidado_fecha'])
                generado=0 if cancelada else plan['interes_mensual']
                recibido=min(cobrado,generado) if vencimiento<=hoy else 0;cobrado-=recibido
                estado='No aplica: capital saldado' if cancelada else ('Prevista' if vencimiento>hoy else ('Pagada' if recibido==generado else 'Pendiente'))
                filas.append((n+1,vencimiento,generado,recibido,estado))
            pagos=[dict(a) for a in db.execute('SELECT * FROM abonos WHERE prestamo_id=? ORDER BY fecha,creado',(prestamo,))]
            return filas,pagos
