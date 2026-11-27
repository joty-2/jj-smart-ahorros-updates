"""Formularios del plan mensual y pagos con capital variable."""
from uuid import uuid4
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QLabel,QComboBox,QLineEdit,
    QDateEdit,QSpinBox,QPushButton,QTableWidget,QHeaderView,QMessageBox,QAbstractItemView)
from ahorros_datos import centavos,dinero
from prestamos_flexibles import mes


def tabla(parent,title,headers,rows,note=''):
    d=QDialog(parent);d.setWindowTitle(title);d.resize(790,480);layout=QVBoxLayout(d)
    if note:
        label=QLabel(note);label.setWordWrap(True);layout.addWidget(label)
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers);t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents);t.horizontalHeader().setStretchLastSection(True);t.verticalHeader().hide();layout.addWidget(t)
    parent.llenar(t,rows);b=QPushButton('Cerrar');b.clicked.connect(d.accept);layout.addWidget(b);d.exec()


def crear_prestamo(w,Formulario):
    if not w.hay_socios():return
    d=Formulario('Préstamo: cuotas e interés mensual',w);d.resize(620,550)
    socio=d.socio(w.datos);fecha=d.fecha();capital=d.texto('Capital a entregar RD$:')
    interes=d.texto('Interés mensual fijo (pesos RD$):','3,000.00')
    cuotas=QSpinBox();cuotas.setRange(1,1200);cuotas.setValue(12);d.form.addRow('Cuotas previstas (meses):',cuotas)
    primera=QDateEdit(fecha.date().addMonths(1));primera.setCalendarPopup(True);primera.setDisplayFormat('dd/MM/yyyy');d.form.addRow('Primera cuota de interés:',primera)
    fecha.dateChanged.connect(lambda value:primera.setDate(value.addMonths(1)))
    nota=d.texto('Acuerdo / nota:');key=str(uuid4())
    d.info.setText('La cuota no tiene un capital fijo: el socio paga el interés vencido y abona al capital lo que pueda.\nEl interés mensual no disminuye por abonos parciales. Al saldar el capital, no se cobran intereses futuros.\nEl plazo es previsto: si queda capital después, el interés mensual continúa hasta saldarlo.')
    preview=QPushButton('Ver cuotas y montos previstos');d.layout().insertWidget(d.layout().count()-1,preview)
    def schedule():
        try:
            m=centavos(interes.text());c=centavos(capital.text());primera_iso=primera.date().toString('yyyy-MM-dd')
            if c<=0:raise ValueError('Escribe el capital del préstamo.')
            rows=[(i+1,mes(primera_iso,i),dinero(m),dinero(c//cuotas.value()+(1 if i<c%cuotas.value() else 0)),dinero(m+c//cuotas.value()+(1 if i<c%cuotas.value() else 0))) for i in range(cuotas.value())]
            tabla(w,'Plan previsto del préstamo',['Cuota','Fecha','Interés fijo','Capital sugerido','Total orientativo'],rows,
                'Capital: '+dinero(c)+'. Capital repartido entre los meses elegidos SOLO como orientación: el socio puede abonar más o menos. Primero paga el interés vencido. No se cobran intereses futuros al saldar.')
        except Exception as e:QMessageBox.warning(d,'Plan',str(e))
    preview.clicked.connect(schedule)
    def save():
        try:
            c=centavos(capital.text());m=centavos(interes.text());f=fecha.date().toString('yyyy-MM-dd');p=primera.date().toString('yyyy-MM-dd')
            w.datos.monto(c,True);w.datos.monto(m)
            if p<f:raise ValueError('La primera cuota no puede ser anterior al desembolso.')
            text=f"Socio: {socio.currentText()}\nCapital: {dinero(c)}\nInterés mensual fijo: {dinero(m)} ({m//100} pesos)\nCuotas previstas: {cuotas.value()}\nPrimera cuota: {primera.date().toString('dd/MM/yyyy')}\n\nCapital variable, primero interés vencido. ¿Registrar el desembolso?"
            if QMessageBox.question(d,'Confirmar préstamo',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            def registrar():
                w.datos.prestar_mensual(key,socio.currentData(),f,c,m,cuotas.value(),p,nota.text())
            d.registrar(registrar,'Préstamo y plan mensual guardados. El capital de cada cuota es orientativo, no obligatorio.',w)
            if d.result()==QDialog.Accepted:mostrar_plan(w,key)
        except Exception as e:QMessageBox.warning(d,'No se registró',str(e))
    d.buttons.accepted.connect(save);d.exec()


def registrar_pago(w,Formulario):
    loans=[p for p in w.datos.prestamos() if p['capital_pendiente']+p['interes_pendiente']>0]
    if not loans:QMessageBox.information(w,'Pagos','No hay préstamos pendientes.');return
    d=Formulario('Registrar pago de préstamo',w);d.resize(600,450)
    loan=QComboBox()
    for p in loans:loan.addItem(f"{p['nombre']} · {p['id'][:8]} · {p['fecha']}",p['id'])
    tipo_pago=QComboBox();tipo_pago.addItem('Solo Interés','interes');tipo_pago.addItem('Solo Capital','capital')
    d.form.addRow('Préstamo:',loan);d.form.addRow('Aplicar pago a:',tipo_pago);fecha=d.fecha();total=d.texto('Monto a pagar RD$:');nota=d.texto('Nota (opcional):');key=str(uuid4())
    btn_full=QPushButton('Usar cantidad completa pendiente')
    d.form.addRow('',btn_full)
    def llenar_completo():
        s=w.datos.saldo_pago(loan.currentData(),fecha.date().toString('yyyy-MM-dd'))
        val=s['interes'] if tipo_pago.currentData()=='interes' else s['capital']
        total.setText(f"{val/100:,.2f}")
    btn_full.clicked.connect(llenar_completo)
    def distribution():
        saldo=w.datos.saldo_pago(loan.currentData(),fecha.date().toString('yyyy-MM-dd'));amount=centavos(total.text() or '0')
        dest=tipo_pago.currentData()
        if dest=='interes':
            if amount>saldo['interes']:raise ValueError('Supera el interés pendiente.')
            interest,cap=amount,0
        else:
            if amount>saldo['capital']:raise ValueError('Supera el capital pendiente.')
            interest,cap=0,amount
        return saldo,amount,interest,cap
    def show():
        try:
            saldo,amount,interest,cap=distribution()
            legacy='\nPréstamo anterior: conserva su interés total acordado.' if saldo['plan'] is None else '\nInterés mensual fijo: '+dinero(saldo['plan']['interes_mensual'])
            d.info.setText('Interés vencido pendiente: '+dinero(saldo['interes'])+'\nCapital pendiente: '+dinero(saldo['capital'])+legacy+'\n\nEste pago: '+dinero(interest)+' a interés y '+dinero(cap)+' a capital.')
        except Exception as e:d.info.setText(str(e))
    loan.currentIndexChanged.connect(show);tipo_pago.currentIndexChanged.connect(show);fecha.dateChanged.connect(show);total.textChanged.connect(show);show()
    def save():
        try:
            saldo,amount,interest,cap=distribution()
            if amount<=0:raise ValueError('Introduce el monto recibido.')
            mensaje=f"Pago recibido: {dinero(amount)}\nPrimero a interés: {dinero(interest)}\nLuego a capital: {dinero(cap)}\nCapital restante: {dinero(saldo['capital']-cap)}\n\n¿Guardar este pago?"
            if QMessageBox.question(d,'Confirmar pago',mensaje,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            pid,fec_iso,nt_txt,dest_sel=loan.currentData(),fecha.date().toString('yyyy-MM-dd'),nota.text(),tipo_pago.currentData()
            d.registrar(lambda:w.datos.pagar(key,pid,fec_iso,amount,nt_txt,dest_sel),'Pago guardado: '+dinero(interest)+' a interés y '+dinero(cap)+' a capital.',w)
            if d.result()==QDialog.Accepted:
                from impresion_ahorros import imprimir_recibo_prestamo
                imprimir_recibo_prestamo(w,w.datos,pid,fec_iso,interest,cap,saldo['capital']-cap,saldo['interes']-interest,nt_txt,key)
        except Exception as e:QMessageBox.warning(d,'No se registró',str(e))
    d.buttons.accepted.connect(save);d.exec()


def ver_cuotas(w):
    loans=w.datos.prestamos()
    if not loans:QMessageBox.information(w,'Cuotas','No hay préstamos registrados.');return
    d=QDialog(w);d.setWindowTitle('Cuotas y pagos registrados');d.resize(660,280);layout=QVBoxLayout(d);choice=QComboBox()
    for p in loans:choice.addItem(f"{p['nombre']} · {p['id'][:8]} · {p['fecha']}",p['id'])
    layout.addWidget(choice)
    def schedule():
        mostrar_plan(w,choice.currentData())
    def history():
        filas,pagos=w.datos.detalle_cuotas(choice.currentData())
        tabla(w,'Pagos registrados',['Fecha','Pago total','A interés','A capital','Nota'],[(p['fecha'],dinero(p['capital']+p['interes']),dinero(p['interes']),dinero(p['capital']),p['nota']) for p in pagos])
    for title,fn in (('Ver cuotas previstas y pendientes',schedule),('Ver pagos registrados',history),('Cerrar',d.accept)):
        b=QPushButton(title);b.clicked.connect(fn);layout.addWidget(b)
    d.exec()


def mostrar_plan(w,prestamo_id):
    filas,pagos=w.datos.detalle_cuotas(prestamo_id)
    if not filas:
        QMessageBox.information(w,'Préstamo anterior','Este préstamo conserva su interés total original. No tiene cuotas mensuales acordadas; no se cambian sus condiciones automáticamente.');return
    prestamo=next(p for p in w.datos.prestamos() if p['id']==prestamo_id)
    cantidad=prestamo['cuotas_previstas'];capital=prestamo['capital'];rows=[]
    for n,f,interes,pagado,estado in filas:
        sugerido=capital//cantidad+(1 if n<=capital%cantidad else 0) if n<=cantidad else 0
        rows.append((n,f,dinero(interes),dinero(pagado),dinero(sugerido),dinero(interes+sugerido),estado))
    abonado=sum(p['capital'] for p in pagos)
    tabla(w,'Cuotas de interés y capital',
        ['Cuota','Vencimiento','Interés mensual','Interés pagado','Capital sugerido','Total orientativo','Estado'],rows,
        'Capital prestado: '+dinero(capital)+' · Capital abonado: '+dinero(abonado)+' · Capital pendiente: '+dinero(prestamo['capital_pendiente'])+
        '\nEl capital sugerido divide el préstamo entre los meses elegidos, pero NO es obligatorio. El socio abona lo que pueda. Primero se cubre el interés vencido y luego el capital. Los pagos reales se consultan en «Ver pagos registrados».')
