from datetime import datetime
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout
)
from ahorros_datos import dinero, ruta_datos

def abrir_cuadre_diario(parent, datos):
    d = QDialog(parent); d.setWindowTitle("💵 Cuadre del Día · Arqueo Rápido de Caja"); d.resize(840, 580)
    lay = QVBoxLayout(d)

    top = QHBoxLayout()
    lbl_t = QLabel("Arqueo y Cuadre de Caja")
    lbl_t.setStyleSheet("font-size:15px; font-weight:bold; color:#00363d;")
    cfg_dia = ruta_datos() / "dia_reunion.txt"
    cmb_dia = QComboBox()
    for nom, num in [("Domingo",7),("Lunes",1),("Martes",2),("Miércoles",3),("Jueves",4),("Viernes",5),("Sábado",6)]:
        cmb_dia.addItem(nom, num)
    if cfg_dia.exists():
        try:
            idx = cmb_dia.findData(int(cfg_dia.read_text().strip()))
            if idx >= 0: cmb_dia.setCurrentIndex(idx)
        except Exception: pass

    def _reunion_reciente():
        q = QDate.currentDate()
        while q.dayOfWeek() != cmb_dia.currentData():
            q = q.addDays(-1)
        return q

    f_edit = QDateEdit(_reunion_reciente()); f_edit.setCalendarPopup(True); f_edit.setDisplayFormat("dd/MM/yyyy")
    def _cambiar_dia():
        cfg_dia.write_text(str(cmb_dia.currentData())); f_edit.setDate(_reunion_reciente())
    cmb_dia.currentIndexChanged.connect(_cambiar_dia)
    btn_reu = QPushButton("🗓 Última Reunión"); btn_reu.clicked.connect(lambda: f_edit.setDate(_reunion_reciente()))
    btn_hoy = QPushButton("Hoy"); btn_hoy.clicked.connect(lambda: f_edit.setDate(QDate.currentDate()))
    top.addWidget(lbl_t, 1); top.addWidget(QLabel("Día reunión:")); top.addWidget(cmb_dia); top.addWidget(QLabel("Fecha:")); top.addWidget(f_edit); top.addWidget(btn_reu); top.addWidget(btn_hoy)
    lay.addLayout(top)

    box = QGroupBox("Resumen de Movimientos de la Fecha"); form = QFormLayout(box)
    lbl_ap = QLabel(); lbl_int = QLabel(); lbl_cap = QLabel(); lbl_ent = QLabel()
    lbl_sal = QLabel(); lbl_neto = QLabel(); lbl_caja = QLabel()
    for l in (lbl_ap, lbl_int, lbl_cap, lbl_ent, lbl_sal, lbl_neto, lbl_caja):
        l.setStyleSheet("font-size:13px; font-weight:bold;")
    lbl_ent.setStyleSheet("font-size:13px; font-weight:bold; color:#0b7a4b;")
    lbl_sal.setStyleSheet("font-size:13px; font-weight:bold; color:#b42318;")
    lbl_neto.setStyleSheet("font-size:14px; font-weight:bold; color:#00363d;")
    lbl_caja.setStyleSheet("font-size:14px; font-weight:bold; color:#086AC7;")

    form.addRow("(+) Aportes de Ahorro recibidos:", lbl_ap)
    form.addRow("(+) Intereses de Préstamos cobrados:", lbl_int)
    form.addRow("(+) Capital de Préstamos recuperado:", lbl_cap)
    form.addRow("= TOTAL ENTRADAS DEL DÍA:", lbl_ent)
    form.addRow("(-) Préstamos nuevos entregados:", lbl_sal)
    form.addRow("= FLUJO NETO DEL DÍA (Entradas - Salidas):", lbl_neto)
    form.addRow("💰 SALDO TOTAL EN CAJA ACUMULADO:", lbl_caja)
    lay.addWidget(box)

    tbl = QTableWidget(0, 5)
    tbl.setHorizontalHeaderLabels(["Fecha", "Socio", "Operación", "Monto", "Nota"])
    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    lay.addWidget(tbl, 1)

    res = {"val": None}
    def calcular():
        iso = f_edit.date().toString("yyyy-MM-dd")
        soc_map = {s["id"]: s["nombre"] for s in datos.socios()}
        movs = []
        with datos.conexion() as db:
            ap = db.execute("SELECT COALESCE(SUM(centavos),0) FROM aportes WHERE fecha=?", (iso,)).fetchone()[0]
            ic = db.execute("SELECT COALESCE(SUM(interes),0) FROM abonos WHERE fecha=?", (iso,)).fetchone()[0]
            cp = db.execute("SELECT COALESCE(SUM(capital),0) FROM abonos WHERE fecha=?", (iso,)).fetchone()[0]
            pr = db.execute("SELECT COALESCE(SUM(capital),0) FROM prestamos WHERE fecha=?", (iso,)).fetchone()[0]
            for r in db.execute("SELECT socio_id, fecha, centavos, nota FROM aportes WHERE fecha=?", (iso,)).fetchall():
                movs.append((r[1], soc_map.get(r[0], f"Socio {r[0]}"), "Aporte Ahorro", dinero(r[2]), r[3] or ""))
            for r in db.execute("SELECT p.socio_id, a.fecha, a.interes, a.capital, a.nota FROM abonos a JOIN prestamos p ON p.id=a.prestamo_id WHERE a.fecha=?", (iso,)).fetchall():
                movs.append((r[1], soc_map.get(r[0], f"Socio {r[0]}"), "Pago Préstamo", dinero(r[2]+r[3]), f"Int: {dinero(r[2])} | Cap: {dinero(r[3])} · {r[4] or ''}"))
            for r in db.execute("SELECT socio_id, fecha, capital, nota FROM prestamos WHERE fecha=?", (iso,)).fetchall():
                movs.append((r[1], soc_map.get(r[0], f"Socio {r[0]}"), "Préstamo Entregado (-)", dinero(r[2]), r[3] or ""))

        entradas = ap + ic + cp; neto = entradas - pr; caja_tot = datos.resumen().get("caja", 0)
        lbl_ap.setText(dinero(ap)); lbl_int.setText(dinero(ic)); lbl_cap.setText(dinero(cp))
        lbl_ent.setText(dinero(entradas)); lbl_sal.setText(dinero(pr))
        lbl_neto.setText(dinero(neto)); lbl_caja.setText(dinero(caja_tot))
        tbl.setRowCount(len(movs))
        for i, m in enumerate(movs):
            for c, v in enumerate(m):
                it = QTableWidgetItem(str(v)); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if c == 3: it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tbl.setItem(i, c, it)
        res["val"] = (iso, ap, ic, cp, entradas, pr, neto, caja_tot, len(movs))

    def imprimir_cuadre():
        from impresion_ahorros import _mostrar_vista_previa
        iso, ap, ic, cp, entradas, pr, neto, caja_tot, cnt = res["val"]
        ahora = datetime.now().strftime("%d/%m/%Y %I:%M %p")
        lineas = [(f"Emitido: {ahora}", False), (f"Fecha Cuadrada: {iso} ({cnt} operaciones)", True), ("--------------------------------------------------", False), (f"(+) Aportes recibidos: {dinero(ap)}", False), (f"(+) Intereses cobrados: {dinero(ic)}", False), (f"(+) Capital recuperado: {dinero(cp)}", False), (f"= TOTAL ENTRADAS: {dinero(entradas)}", True), (f"(-) Préstamos entregados: {dinero(pr)}", False), (f"= FLUJO NETO DEL DÍA: {dinero(neto)}", True), (f"SALDO EN CAJA ACUMULADO: {dinero(caja_tot)}", True)]
        html = f"<div style='font-family:Helvetica,Arial;padding:10px;color:#111;font-size:11px;'><h3 style='margin:0;color:#00363d;'>JJ SMART AHORROS</h3><p style='margin:2px 0 6px;color:#555;'>Cuadre Diario de Caja · {iso}</p><hr><table style='width:100%;font-size:11px;'><tr><td>(+) Aportes recibidos:</td><td style='text-align:right;'>{dinero(ap)}</td></tr><tr><td>(+) Intereses cobrados:</td><td style='text-align:right;'>{dinero(ic)}</td></tr><tr><td>(+) Capital recuperado:</td><td style='text-align:right;'>{dinero(cp)}</td></tr><tr style='background:#eef7f2;'><td><b>= TOTAL ENTRADAS:</b></td><td style='text-align:right;'><b>{dinero(entradas)}</b></td></tr><tr><td>(-) Préstamos entregados:</td><td style='text-align:right;'>{dinero(pr)}</td></tr><tr style='background:#f4f8fa;'><td><b>= FLUJO NETO DEL DÍA:</b></td><td style='text-align:right;'><b>{dinero(neto)}</b></td></tr><tr style='background:#e6f0fa;'><td><b>SALDO TOTAL EN CAJA:</b></td><td style='text-align:right;'><b>{dinero(caja_tot)}</b></td></tr></table><div style='margin-top:16px;padding-top:8px;border-top:1px dashed #ccc;text-align:center;font-family:Georgia,serif;font-style:italic;color:rgba(0,54,61,0.65);font-size:11.5px;font-weight:600;letter-spacing:1.4px;'>JJSMART AHORRO CREADO POR JOSE JOSE BAUTISTA</div></div>"
        _mostrar_vista_previa(d, f"Cuadre Diario - {iso}", f"Cuadre_{iso}", "COMPROBANTE DE CUADRE DIARIO DE CAJA", lineas, html, ancho=430, alto=470)

    f_edit.dateChanged.connect(calcular)
    btns = QHBoxLayout()
    b_imp = QPushButton("🖨 Imprimir / Enviar Cuadre"); b_imp.clicked.connect(imprimir_cuadre)
    b_close = QPushButton("Cerrar"); b_close.clicked.connect(d.accept)
    btns.addWidget(b_imp); btns.addStretch(); btns.addWidget(b_close)
    lay.addLayout(btns); calcular(); d.exec()
