import json, os, shutil, subprocess, sys
from datetime import date, datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
)
from ahorros_datos import dinero, ruta_datos

def _dir_reglas():
    d = ruta_datos() / "Reglas_Reparto"; d.mkdir(parents=True, exist_ok=True); return d

def _leer_cfg():
    f = _dir_reglas() / "config_reparto.json"
    if f.exists():
        try: return json.loads(f.read_text(encoding="utf-8"))
        except Exception: pass
    return {"pct_socios": 100.0, "criterio": "proporcional", "notas_reglas": "", "archivo_reglas": ""}

def _guardar_cfg(cfg):
    (_dir_reglas() / "config_reparto.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def _leer_historial():
    f = _dir_reglas() / "historial_cierres.json"
    if f.exists():
        try: return json.loads(f.read_text(encoding="utf-8"))
        except Exception: pass
    return {}

def _guardar_historial(hist):
    (_dir_reglas() / "historial_cierres.json").write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")

def abrir_reparto_anual(parent, datos):
    d = QDialog(parent); d.setWindowTitle("Reportes Semanales y Cierre Anual · JJ SMART AHORROS"); d.resize(980, 680)
    lay = QVBoxLayout(d); cfg = _leer_cfg(); hist = _leer_historial()
    lbl_t = QLabel("El reparto se hará según las reglas del ahorro o la cooperativa")
    lbl_t.setStyleSheet("font-size:15px; font-weight:bold; color:#51E0D0; padding:2px 0;"); lay.addWidget(lbl_t)
    tabs = QTabWidget(); lay.addWidget(tabs, 1)

    tab_anual = QWidget(); la = QVBoxLayout(tab_anual); bar_hist = QHBoxLayout()
    cmb_anio = QComboBox(); cmb_anio.addItem("📅 Año Actual (Cálculo en vivo)", "ACTUAL")
    anios_db = set(hist.keys()) | {str(datetime.now().year)}
    with datos.conexion() as db:
        for r in db.execute("SELECT DISTINCT substr(fecha,1,4) FROM aportes UNION SELECT DISTINCT substr(fecha,1,4) FROM abonos").fetchall():
            if r[0]: anios_db.add(r[0])
    for yr in sorted(anios_db, reverse=True):
        if yr in hist: cmb_anio.addItem(f"📁 Cierre Archivado · Año {yr}", f"HIST:{yr}")
        elif yr != str(datetime.now().year): cmb_anio.addItem(f"📆 Movimientos del Año {yr}", f"DB:{yr}")
    txt_buscar = QLineEdit(); txt_buscar.setPlaceholderText("🔍 Buscar socio, código o cifra en el reporte anual...")
    btn_cerrar_anio = QPushButton("💾 Guardar Cierre Anual")
    bar_hist.addWidget(QLabel("Año:")); bar_hist.addWidget(cmb_anio); bar_hist.addWidget(txt_buscar, 1); bar_hist.addWidget(btn_cerrar_anio)
    la.addLayout(bar_hist)

    box = QGroupBox("Reglas del Reparto Anual (Escribir, Foto o Documento)"); rlay = QVBoxLayout(box); top_r = QHBoxLayout()
    lbl_doc = QLabel(f"Archivo cargado: {cfg.get('archivo_reglas') or 'Ninguno aún'}"); lbl_doc.setStyleSheet("font-weight:bold; color:#51E0D0;")
    btn_subir = QPushButton("📎 Subir Foto o Documento"); btn_ver = QPushButton("👁 Ver Archivo")
    top_r.addWidget(lbl_doc, 1); top_r.addWidget(btn_subir); top_r.addWidget(btn_ver); rlay.addLayout(top_r)

    form = QFormLayout()
    sp_pct = QDoubleSpinBox(); sp_pct.setRange(0.0, 100.0); sp_pct.setSuffix(" %"); sp_pct.setValue(float(cfg.get("pct_socios", 100.0)))
    cmb_crit = QComboBox(); cmb_crit.addItem("Proporcional al ahorro de cada socio", "proporcional"); cmb_crit.addItem("Partes iguales entre socios activos", "igual")
    if cfg.get("criterio") == "igual": cmb_crit.setCurrentIndex(1)
    txt_reg = QTextEdit(); txt_reg.setMaximumHeight(50); txt_reg.setPlaceholderText("Escribe o pega aquí las reglas..."); txt_reg.setPlainText(cfg.get("notas_reglas", ""))
    form.addRow("% Intereses Préstamos a repartir:", sp_pct); form.addRow("Criterio:", cmb_crit); form.addRow("Reglas escritas:", txt_reg)
    rlay.addLayout(form); la.addWidget(box)

    lbl_res = QLabel(); lbl_res.setStyleSheet("font-weight:bold; padding:6px; background:#13243A; color:#51E0D0; border:1px solid #29415B; border-radius:8px;"); la.addWidget(lbl_res)
    tbl = QTableWidget(0, 6); tbl.setHorizontalHeaderLabels(["Código", "Socio", "Ahorro Acumulado", "% Participación", "Utilidad Préstamos", "TOTAL A RECIBIR"])
    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); la.addWidget(tbl, 1)

    filas_actuales = []
    def llenar_tabla(filas):
        q = txt_buscar.text().strip().lower()
        vis = [r for r in filas if not q or any(q in str(x).lower() for x in r)]
        tbl.setRowCount(len(vis))
        for i, r in enumerate(vis):
            for c, v in enumerate(r):
                it = QTableWidgetItem(str(v)); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if c >= 2: it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tbl.setItem(i, c, it)

    def calcular():
        nonlocal filas_actuales
        modo = cmb_anio.currentData()
        if modo.startswith("HIST:"):
            yr = modo.split(":", 1)[1]; rep = hist[yr]
            lbl_res.setText(f"[CIERRE ARCHIVADO AÑO {yr} · {rep.get('fecha','')}]  {rep.get('resumen','')}")
            filas_actuales = rep.get("filas", []); llenar_tabla(filas_actuales); return
        yr_filtro = modo.split(":", 1)[1] if modo.startswith("DB:") else None
        socios = datos.socios()
        with datos.conexion() as db:
            if yr_filtro:
                ah_map = {r[0]: r[1] for r in db.execute("SELECT socio_id, COALESCE(SUM(centavos),0) FROM aportes WHERE substr(fecha,1,4)=? GROUP BY socio_id", (yr_filtro,)).fetchall()}
                int_cobrado = db.execute("SELECT COALESCE(SUM(interes),0) FROM abonos WHERE substr(fecha,1,4)=?", (yr_filtro,)).fetchone()[0]
            else:
                ah_map = {s["id"]: s.get("ahorro", 0) for s in socios}
                int_cobrado = db.execute("SELECT COALESCE(SUM(interes),0) FROM abonos").fetchone()[0]
        activos = [s for s in socios if ah_map.get(s["id"], 0) > 0]
        tot_ahorro = sum(ah_map.get(s["id"], 0) for s in activos)
        bolsa = int(round(int_cobrado * (sp_pct.value() / 100.0)))
        lbl_res.setText(f"[{'AÑO '+yr_filtro if yr_filtro else 'ACUMULADO ACTUAL'}]  Fondo: {dinero(tot_ahorro)}  |  Intereses Préstamos: {dinero(int_cobrado)}  |  Bolsa ({sp_pct.value():.1f}%): {dinero(bolsa)}")
        filas_actuales = []
        for s in activos:
            ah = ah_map.get(s["id"], 0)
            prop = (ah / tot_ahorro) if (tot_ahorro > 0 and cmb_crit.currentData() == "proporcional") else (1.0 / len(activos) if activos else 0.0)
            util = int(round(bolsa * prop)); filas_actuales.append([f"SOC-{s['id']:05d}", s["nombre"], dinero(ah), f"{prop*100:.2f} %", dinero(util), dinero(ah + util)])
        llenar_tabla(filas_actuales)
        cfg.update({"pct_socios": sp_pct.value(), "criterio": cmb_crit.currentData(), "notas_reglas": txt_reg.toPlainText()}); _guardar_cfg(cfg)

    def guardar_cierre():
        yr = str(datetime.now().year)
        if QMessageBox.question(d, "Guardar Cierre Anual", f"¿Archivar el cierre oficial del año {yr} en el historial?") != QMessageBox.Yes: return
        hist[yr] = {"fecha": datetime.now().strftime("%d/%m/%Y %I:%M %p"), "resumen": lbl_res.text(), "reglas": txt_reg.toPlainText(), "filas": filas_actuales}
        _guardar_historial(hist); QMessageBox.information(d, "Cierre guardado", f"Reporte del año {yr} archivado.")

    def subir():
        ruta, _ = QFileDialog.getOpenFileName(d, "Subir Foto o Documento de Reglas", "", "Archivos (*.pdf *.png *.jpg *.jpeg *.txt *.docx);;Todos (*.*)")
        if not ruta: return
        src = Path(ruta); dst = _dir_reglas() / f"Reglas_{datetime.now().strftime('%Y%m%d_%H%M%S')}{src.suffix}"; shutil.copy2(src, dst)
        cfg["archivo_reglas"] = dst.name; _guardar_cfg(cfg); lbl_doc.setText(f"Archivo cargado: {dst.name}")
        if src.suffix.lower() == ".txt": txt_reg.setPlainText(src.read_text(encoding="utf-8", errors="ignore"))
        calcular()

    def ver():
        f = _dir_reglas() / cfg.get("archivo_reglas", "")
        if not cfg.get("archivo_reglas") or not f.exists(): QMessageBox.information(d, "Sin archivo", "No hay archivo subido."); return
        if sys.platform == "darwin": subprocess.Popen(["open", str(f)])
        elif os.name == "nt": os.startfile(str(f))
        else: subprocess.Popen(["xdg-open", str(f)])

    btn_subir.clicked.connect(subir); btn_ver.clicked.connect(ver); btn_cerrar_anio.clicked.connect(guardar_cierre)
    cmb_anio.currentIndexChanged.connect(calcular); txt_buscar.textChanged.connect(lambda: llenar_tabla(filas_actuales))
    sp_pct.valueChanged.connect(calcular); cmb_crit.currentIndexChanged.connect(calcular); txt_reg.textChanged.connect(calcular)
    tabs.addTab(tab_anual, "📊 Reporte Anual y Cierre")

    tab_sem = QWidget(); ls = QVBoxLayout(tab_sem); bar_s = QHBoxLayout()
    cmb_yr_s = QComboBox()
    for yr in sorted(anios_db, reverse=True): cmb_yr_s.addItem(f"Año {yr}", yr)
    cmb_sem = QComboBox(); cmb_sem.addItem("Todas las semanas del año", "ALL")
    for w in range(1, 54): cmb_sem.addItem(f"Semana {w:02d}", f"{w:02d}")
    txt_bus_s = QLineEdit(); txt_bus_s.setPlaceholderText("🔍 Buscar socio, semana o movimiento...")
    bar_s.addWidget(QLabel("Año:")); bar_s.addWidget(cmb_yr_s); bar_s.addWidget(QLabel("Semana:")); bar_s.addWidget(cmb_sem); bar_s.addWidget(txt_bus_s, 1)
    ls.addLayout(bar_s)
    lbl_res_s = QLabel(); lbl_res_s.setStyleSheet("font-weight:bold; padding:6px; background:#13243A; color:#51E0D0; border:1px solid #29415B; border-radius:8px;"); ls.addWidget(lbl_res_s)
    tbl_s = QTableWidget(0, 6); tbl_s.setHorizontalHeaderLabels(["Semana", "Fecha", "Socio", "Operación", "Monto", "Detalle"])
    tbl_s.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); ls.addWidget(tbl_s, 1)

    def cargar_semanal():
        yr = cmb_yr_s.currentData(); sem_f = cmb_sem.currentData(); q = txt_bus_s.text().strip().lower()
        soc_map = {s["id"]: s["nombre"] for s in datos.socios()}; movs = []; tot_ap = tot_int = tot_cap = 0
        with datos.conexion() as db:
            for r in db.execute("SELECT socio_id, fecha, centavos, nota FROM aportes WHERE substr(fecha,1,4)=?", (yr,)).fetchall():
                wnum = f"{date.fromisoformat(r[1]).isocalendar()[1]:02d}"
                if sem_f != "ALL" and wnum != sem_f: continue
                tot_ap += r[2]; movs.append((f"Sem {wnum}", r[1], soc_map.get(r[0], f"Socio {r[0]}"), "Aporte Ahorro", dinero(r[2]), r[3] or ""))
            for r in db.execute("SELECT p.socio_id, a.fecha, a.interes, a.capital, a.nota FROM abonos a JOIN prestamos p ON p.id=a.prestamo_id WHERE substr(a.fecha,1,4)=?", (yr,)).fetchall():
                wnum = f"{date.fromisoformat(r[1]).isocalendar()[1]:02d}"
                if sem_f != "ALL" and wnum != sem_f: continue
                tot_int += r[2]; tot_cap += r[3]; movs.append((f"Sem {wnum}", r[1], soc_map.get(r[0], f"Socio {r[0]}"), "Pago Préstamo", dinero(r[2]+r[3]), f"Int: {dinero(r[2])} | Cap: {dinero(r[3])} · {r[4] or ''}"))
        movs.sort(key=lambda x: x[1], reverse=True)
        vis = [m for m in movs if not q or any(q in str(x).lower() for x in m)]
        lbl_res_s.setText(f"Año {yr} ({'Todas' if sem_f=='ALL' else 'Sem '+sem_f})  |  Aportes: {dinero(tot_ap)}  |  Intereses: {dinero(tot_int)}  |  Capital: {dinero(tot_cap)}")
        tbl_s.setRowCount(len(vis))
        for i, m in enumerate(vis):
            for c, v in enumerate(m):
                it = QTableWidgetItem(str(v)); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if c == 4: it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tbl_s.setItem(i, c, it)

    cmb_yr_s.currentIndexChanged.connect(cargar_semanal); cmb_sem.currentIndexChanged.connect(cargar_semanal); txt_bus_s.textChanged.connect(cargar_semanal)
    tabs.addTab(tab_sem, "📅 Reporte Semanal")
    b_close = QPushButton("Cerrar"); b_close.clicked.connect(d.accept); lay.addWidget(b_close, alignment=Qt.AlignRight)
    calcular(); cargar_semanal(); d.exec()
