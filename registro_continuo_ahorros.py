from uuid import uuid4
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter, QWidget,
    QLabel, QLineEdit, QPushButton, QDateEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox
)
from ahorros_datos import ACCION, centavos, dinero
from impresion_ahorros import imprimir_recibo_aporte

def abrir_registro_continuo(ventana):
    if not ventana.hay_socios():
        return
    d = QDialog(ventana)
    d.setWindowTitle('Registro Continuo de Ahorros · JJ SMART AHORROS')
    d.resize(1020, 620)
    root = QVBoxLayout(d)
    banner = QLabel('💡 Selecciona un socio en la lista izquierda, registra su ahorro y continúa con el siguiente sin salir.')
    banner.setStyleSheet('background:#e0f2fe;color:#0369a1;padding:8px 12px;border-radius:6px;font-weight:bold;')
    root.addWidget(banner)
    split = QSplitter(Qt.Horizontal)
    root.addWidget(split, 1)

    izq = QWidget(); vl_izq = QVBoxLayout(izq)
    txt_buscar = QLineEdit(); txt_buscar.setPlaceholderText('🔍 Buscar socio por nombre o código...')
    vl_izq.addWidget(QLabel('<b>1. Lista Permanente de Socios</b>'))
    vl_izq.addWidget(txt_buscar)
    tbl_soc = QTableWidget(0, 3); tbl_soc.setHorizontalHeaderLabels(['Código', 'Socio', 'Saldo Ahorrado'])
    tbl_soc.setSelectionBehavior(QAbstractItemView.SelectRows); tbl_soc.setSelectionMode(QAbstractItemView.SingleSelection)
    tbl_soc.setEditTriggers(QAbstractItemView.NoEditTriggers); tbl_soc.verticalHeader().setVisible(False)
    tbl_soc.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    vl_izq.addWidget(tbl_soc, 1)
    split.addWidget(izq)

    der = QWidget(); vl_der = QVBoxLayout(der)
    lbl_socio_act = QLabel('<b>2. Socio seleccionado:</b> Ninguno')
    lbl_socio_act.setStyleSheet('font-size:14px;color:#00363d;padding:6px;background:#f0fdf4;border:1px solid #86efac;border-radius:6px;')
    vl_der.addWidget(lbl_socio_act)

    frm = QFormLayout()
    inp_fecha = QDateEdit(QDate.currentDate()); inp_fecha.setCalendarPopup(True); inp_fecha.setDisplayFormat('yyyy-MM-dd')
    inp_monto = QLineEdit(); inp_monto.setPlaceholderText('Ejemplo: 500 o 200000, sin separadores de miles')
    inp_nota = QLineEdit(); inp_nota.setPlaceholderText('Nota opcional del movimiento')
    lbl_info = QLabel('Cada accion vale RD$100. No hay un tope comercial de aporte.')
    lbl_info.setStyleSheet('color:#07589c;font-weight:bold;')
    frm.addRow('Fecha:', inp_fecha); frm.addRow('Aporte en RD$:', inp_monto); frm.addRow('Acciones:', lbl_info); frm.addRow('Nota (opcional):', inp_nota)
    vl_der.addLayout(frm)

    row_btns = QHBoxLayout()
    btn_guardar = QPushButton('💾 Guardar Ahorro y Generar Recibo')
    btn_guardar.setStyleSheet('background:#0d9488;color:white;font-weight:bold;padding:10px 16px;border-radius:6px;')
    btn_limpiar = QPushButton('Limpiar monto')
    row_btns.addWidget(btn_guardar, 2); row_btns.addWidget(btn_limpiar, 1)
    vl_der.addLayout(row_btns)

    lbl_estado_op = QLabel(''); lbl_estado_op.setWordWrap(True); vl_der.addWidget(lbl_estado_op)
    vl_der.addWidget(QLabel('<b>3. Historial de Recibos Guardados del Socio (Consulta y Reimpresión)</b>'))
    tbl_rec = QTableWidget(0, 6); tbl_rec.setHorizontalHeaderLabels(['Operación', 'Socio', 'Fecha', 'Hora', 'Monto', 'Acumulado'])
    tbl_rec.setSelectionBehavior(QAbstractItemView.SelectRows); tbl_rec.setSelectionMode(QAbstractItemView.SingleSelection)
    tbl_rec.setEditTriggers(QAbstractItemView.NoEditTriggers); tbl_rec.verticalHeader().setVisible(False)
    tbl_rec.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    vl_der.addWidget(tbl_rec, 1)

    row_rec_btns = QHBoxLayout()
    btn_reimp = QPushButton('🖨️ Consultar / Reimprimir Recibo')
    btn_reimp.setStyleSheet('background:#1d4ed8;color:white;font-weight:bold;padding:8px 14px;border-radius:6px;')
    btn_elim_rec = QPushButton('🗑️ Eliminar Recibo Seleccionado')
    btn_elim_rec.setStyleSheet('background:#dc2626;color:white;font-weight:bold;padding:8px 14px;border-radius:6px;')
    row_rec_btns.addWidget(btn_reimp, 2); row_rec_btns.addWidget(btn_elim_rec, 1)
    vl_der.addLayout(row_rec_btns)
    split.addWidget(der); split.setSizes([360, 660])
    pie = QHBoxLayout(); pie.addStretch(); btn_cerrar = QPushButton('Cerrar y Volver al Menú Principal')
    btn_cerrar.clicked.connect(d.accept); pie.addWidget(btn_cerrar); root.addLayout(pie)

    est = {'sid': None, 'recibos': []}
    def _prev():
        try:
            a = centavos(inp_monto.text())
            lbl_info.setText(f'{a//ACCION} acciones' if a > 0 and a % ACCION == 0 else 'El monto debe ser positivo y multiplo de RD$100.')
        except ValueError: lbl_info.setText('Cada accion vale RD$100. No hay un tope comercial de aporte.')
    inp_monto.textChanged.connect(_prev)

    def _cargar_rec(sid):
        recs = ventana.datos.recibos_socio(sid); est['recibos'] = recs; tbl_rec.setRowCount(len(recs))
        for i, r in enumerate(recs):
            for c, val in enumerate([str(r['id'])[:8].upper(), r.get('socio_nombre', ''), r['fecha'], r['hora'] or '', dinero(r['centavos']), dinero(r['acumulado'])]):
                tbl_rec.setItem(i, c, QTableWidgetItem(val))

    def _sel_soc():
        r = tbl_soc.currentRow()
        if r < 0: return
        sid = int(tbl_soc.item(r, 0).data(Qt.UserRole))
        s = {x['id']: x for x in ventana.datos.socios()}.get(sid)
        if not s: return
        est['sid'] = sid
        lbl_socio_act.setText(f"<b>2. Socio activo:</b> SOC-{s['id']:05d} · {s['nombre']}  |  <b>Saldo:</b> {dinero(s['ahorro'])} ({s['ahorro']//ACCION:,} acc.)")
        _cargar_rec(sid)

    def _cargar_soc(sel_id=None):
        flt = txt_buscar.text().strip().lower()
        todos = [s for s in ventana.datos.socios() if not flt or flt in s['nombre'].lower() or flt in f"soc-{s['id']:05d}"]
        tbl_soc.blockSignals(True); tbl_soc.setRowCount(len(todos)); idx = 0
        for i, s in enumerate(todos):
            it0 = QTableWidgetItem(f"SOC-{s['id']:05d}"); it0.setData(Qt.UserRole, s['id'])
            tbl_soc.setItem(i, 0, it0); tbl_soc.setItem(i, 1, QTableWidgetItem(s['nombre'])); tbl_soc.setItem(i, 2, QTableWidgetItem(dinero(s['ahorro'])))
            if sel_id is not None and s['id'] == sel_id: idx = i
        tbl_soc.blockSignals(False)
        if todos: tbl_soc.selectRow(idx); _sel_soc()
        else: est['sid'] = None; lbl_socio_act.setText('<b>2. Socio seleccionado:</b> Ninguno'); tbl_rec.setRowCount(0)

    def _guardar():
        sid = est['sid']
        if not sid: QMessageBox.warning(d, 'Aviso', 'Selecciona un socio de la lista izquierda.'); return
        fec = inp_fecha.date().toString('yyyy-MM-dd'); nt = inp_nota.text(); key = str(uuid4())
        try:
            imp = centavos(inp_monto.text()); ventana.datos.aportar(key, sid, fec, imp, nt)
        except Exception as e:
            QMessageBox.warning(d, 'No se registró', str(e)); return
        ventana.refrescar(); _cargar_soc(sid); inp_monto.clear(); inp_nota.clear(); inp_monto.setFocus()
        rec = next((r for r in est['recibos'] if r['id'] == key), None)
        lbl_estado_op.setStyleSheet('background:#dcfce7;color:#166534;padding:6px 10px;border-radius:5px;font-weight:bold;')
        lbl_estado_op.setText(f"✅ Ahorro de {dinero(imp)} guardado (Op. {key[:8].upper()}). Listo para el siguiente socio.")
        imprimir_recibo_aporte(d, ventana.datos, sid, fec, imp, nt, op_id=key, hora=rec['hora'] if rec else '', acumulado_centavos=rec['acumulado'] if rec else None)

    def _reimp():
        sid = est['sid']; r = tbl_rec.currentRow()
        if not sid or r < 0 or r >= len(est['recibos']): QMessageBox.information(d, 'Recibos', 'Selecciona un recibo de la tabla.'); return
        rec = est['recibos'][r]
        imprimir_recibo_aporte(d, ventana.datos, sid, rec['fecha'], rec['centavos'], rec['nota'], op_id=rec['id'], hora=rec['hora'], acumulado_centavos=rec['acumulado'])

    tbl_soc.itemSelectionChanged.connect(_sel_soc)
    txt_buscar.textChanged.connect(lambda: _cargar_soc(est['sid']))
    btn_limpiar.clicked.connect(lambda: (inp_monto.clear(), inp_nota.clear(), inp_monto.setFocus()))
    btn_guardar.clicked.connect(_guardar); inp_monto.returnPressed.connect(_guardar)
    def _eliminar_rec():
        sid = est['sid']; r = tbl_rec.currentRow()
        if not sid or r < 0 or r >= len(est['recibos']):
            QMessageBox.information(d, 'Eliminar recibo', 'Selecciona primero el recibo equivocado en la tabla de historial.'); return
        rec = est['recibos'][r]
        op_corto = str(rec['id'])[:8].upper()
        if QMessageBox.question(
            d, 'Confirmar eliminación de recibo',
            f"¿Seguro que deseas eliminar este recibo equivocado?\n\n"
            f"• Socio: {rec.get('socio_nombre', '')}\n• Operación: {op_corto}\n"
            f"• Fecha: {rec['fecha']} {rec['hora'] or ''}\n"
            f"• Monto a descontar: {dinero(rec['centavos'])}\n\n"
            f"El saldo del socio y el balance del grupo se recalcularán automáticamente.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        try:
            ventana.datos.eliminar_aporte(rec['id'], 'Anulado desde historial de recibos')
            ventana.refrescar()
            _cargar_soc(sid)
            lbl_estado_op.setStyleSheet('background:#fee2e2;color:#991b1b;padding:6px 10px;border-radius:5px;font-weight:bold;')
            lbl_estado_op.setText(f"🗑️ Recibo {op_corto} ({dinero(rec['centavos'])}) eliminado y saldo recalculado. Ya puedes registrar el monto correcto.")
            inp_monto.setFocus()
        except Exception as e:
            QMessageBox.warning(d, 'No se pudo eliminar', str(e))

    btn_reimp.clicked.connect(_reimp); tbl_rec.doubleClicked.connect(_reimp); btn_elim_rec.clicked.connect(_eliminar_rec)
    _cargar_soc(); inp_monto.setFocus(); d.exec()
