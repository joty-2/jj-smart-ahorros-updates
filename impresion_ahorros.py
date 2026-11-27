import os, re, subprocess, sys, threading
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QMimeData, QRectF, Qt, QTimer, QUrl, QUrlQuery
from PySide6.QtGui import QColor, QImage, QDesktopServices, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QMessageBox, QPushButton, QTextBrowser, QVBoxLayout
from ahorros_datos import ACCION, dinero

CARPETA_PDF = Path.home() / "Desktop" / "JJ_SMART_PDF"

def _tel_wa(tel):
    d = re.sub(r"\D", "", str(tel or ""))
    return ("1" + d) if (len(d) == 10 and d.startswith(("809", "829", "849"))) else d

def _crear_imagen_wa(nombre_base, titulo_doc, lineas):
    CARPETA_PDF.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = CARPETA_PDF / f"{nombre_base}_{ts}.png"
    alto = max(460, 220 + len(lineas) * 34)
    img = QImage(680, alto, QImage.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    pt = QPainter(img)
    pt.setPen(QColor("#00363d")); pt.setFont(QFont("Helvetica", 20, QFont.Bold)); pt.drawText(36, 52, "JJ SMART AHORROS")
    pt.setPen(QColor("#07589c")); pt.setFont(QFont("Helvetica", 13, QFont.Bold)); pt.drawText(36, 82, titulo_doc)
    pt.setPen(QColor("#cccccc")); pt.drawLine(36, 98, 644, 98)
    y = 132
    for txt, neg in lineas:
        pt.setPen(QColor("#111111")); pt.setFont(QFont("Helvetica", 12, QFont.Bold if neg else QFont.Normal)); pt.drawText(36, y, str(txt)); y += 32
    pt.setPen(QColor(0, 54, 61, 110)); pt.setFont(QFont("Helvetica", 11, QFont.Bold)); pt.drawText(QRectF(0, alto - 45, 680, 30), Qt.AlignCenter, "JJSMART AHORRO CREADO POR JOSE JOSE BAUTISTA")
    pt.end(); img.save(str(ruta), "PNG"); QApplication.clipboard().setImage(img)
    return ruta

def _crear_pdf_nativo(nombre_base, titulo_doc, lineas):
    CARPETA_PDF.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = CARPETA_PDF / f"{nombre_base}_{ts}.pdf"
    writer = QPdfWriter(str(ruta))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setResolution(150)
    painter = QPainter(writer)
    w = writer.width(); h = writer.height(); y = 120
    painter.setPen(QColor("#00363d"))
    painter.setFont(QFont("Helvetica", 18, QFont.Bold))
    painter.drawText(100, y, "JJ SMART AHORROS")
    y += 45
    painter.setPen(QColor("#07589c"))
    painter.setFont(QFont("Helvetica", 12, QFont.Bold))
    painter.drawText(100, y, titulo_doc)
    y += 35
    painter.setPen(QColor("#cccccc"))
    painter.drawLine(100, y, w - 100, y)
    y += 45
    for texto, negrita in lineas:
        if y > h - 220:
            writer.newPage(); y = 120
        painter.setPen(QColor("#111111"))
        painter.setFont(QFont("Helvetica", 11, QFont.Bold if negrita else QFont.Normal))
        painter.drawText(100, y, str(texto))
        y += 38
    painter.setPen(QColor(0, 54, 61, 95))
    painter.setFont(QFont("Helvetica", 11, QFont.Bold))
    painter.drawText(QRectF(0, h - 140, w, 60), Qt.AlignCenter, "JJSMART AHORRO CREADO POR JOSE JOSE BAUTISTA")
    painter.end()
    return ruta

def _copiar_pdf_al_portapapeles(ruta):
    if sys.platform=="darwin": subprocess.run(["/usr/bin/osascript", "-e", f'set the clipboard to (POSIX file "{ruta}")'])

def _pegar_auto():
    import ctypes, time
    cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    cg.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    for kc, fl, dn in [(55, 0x100000, True), (9, 0x100000, True), (9, 0x100000, False), (55, 0, False)]:
        ev = cg.CGEventCreateKeyboardEvent(None, kc, dn)
        cg.CGEventSetFlags(ev, fl)
        cg.CGEventPost(0, ev)
        time.sleep(0.04)

def _mostrar_vista_previa(parent, titulo, nombre_archivo, titulo_doc, lineas_pdf, html, ancho=450, alto=490, telefono=""):
    dlg = QDialog(parent); dlg.setWindowTitle(titulo); dlg.resize(ancho, alto)
    layout = QVBoxLayout(dlg); visor = QTextBrowser(); visor.setHtml(html)
    visor.setStyleSheet("background: white; color: #111; border-radius: 8px; padding: 8px;")
    layout.addWidget(visor); btns = QHBoxLayout()
    b_imp = QPushButton("🖨 Imprimir"); b_imp.setStyleSheet("background:#0876d0; color:white; font-weight:bold; padding:8px 12px; border-radius:8px;")
    b_pdf = QPushButton("📥 Guardar PDF"); b_pdf.setStyleSheet("background:#00a27d; color:white; font-weight:bold; padding:8px 12px; border-radius:8px;")
    b_dir = QPushButton("📂 Carpeta PDF"); b_dir.setStyleSheet("background:#455a64; color:white; font-weight:bold; padding:8px 12px; border-radius:8px;")
    b_wa = QPushButton("💬 Enviar por WhatsApp"); b_wa.setStyleSheet("background:#1ebe5d; color:white; font-weight:bold; padding:8px 12px; border-radius:8px;")
    b_cer = QPushButton("Cerrar"); b_cer.setStyleSheet("padding:8px 12px; border-radius:8px;")
    def _imp():
        printer = QPrinter(QPrinter.HighResolution); printer.setDocName(nombre_archivo)
        pd = QPrintDialog(printer, dlg)
        if pd.exec() == QPrintDialog.Accepted:
            doc = QTextDocument(); doc.setHtml(html); doc.print_(printer)
    def _pdf():
        try:
            ruta = _crear_pdf_nativo(nombre_archivo, titulo_doc, lineas_pdf)
            if sys.platform.startswith('win'): os.startfile(str(ruta))
            else: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta)))
        except Exception as e:
            QMessageBox.warning(dlg, 'Error al abrir PDF', str(e))
    def _wa():
        tel = _tel_wa(telefono)
        if not tel: QMessageBox.warning(dlg, "Sin teléfono", "Este socio no tiene teléfono registrado."); return
        ruta_img = _crear_imagen_wa(nombre_archivo, titulo_doc, lineas_pdf)
        cuerpo = "*JJ SMART AHORROS*\n*" + titulo_doc + "*\n--------------------------------\n" + "\n".join(x[0] for x in lineas_pdf) + "\n--------------------------------\n_JJSMART AHORRO CREADO POR JOSE JOSE BAUTISTA_"
        u = QUrl(); u.setScheme("whatsapp"); u.setHost("send"); q = QUrlQuery(); q.addQueryItem("phone", tel); q.addQueryItem("text", cuerpo); u.setQuery(q)
        dlg.accept()
        QDesktopServices.openUrl(u)
    def _abrir_dir():
        CARPETA_PDF.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith('win'): os.startfile(str(CARPETA_PDF))
        else: QDesktopServices.openUrl(QUrl.fromLocalFile(str(CARPETA_PDF)))
    b_imp.clicked.connect(_imp); b_pdf.clicked.connect(_pdf); b_dir.clicked.connect(_abrir_dir); b_wa.clicked.connect(_wa); b_cer.clicked.connect(dlg.accept)
    btns.addWidget(b_imp); btns.addWidget(b_pdf); btns.addWidget(b_dir); btns.addWidget(b_wa); btns.addStretch(); btns.addWidget(b_cer); layout.addLayout(btns); dlg.exec()

def imprimir_recibo_aporte(parent, datos, socio_id, fecha, importe_centavos, nota='', op_id=None, hora=None, acumulado_centavos=None):
    s = {x["id"]: x for x in datos.socios()}.get(int(socio_id))
    if not s: return
    acum_val = s["ahorro"] if acumulado_centavos is None else int(acumulado_centavos)
    acc = importe_centavos // ACCION; tot = acum_val // ACCION
    ahora = f"{fecha} {hora}" if hora else datetime.now().strftime("%d/%m/%Y %I:%M %p")
    ref_txt = f"  |  Op: {str(op_id)[:8].upper()}" if op_id else ""
    lineas = [(f"Emitido: {ahora}", False), (f"Código: SOC-{s['id']:05d}", True), (f"Socio: {s['nombre']}", True), (f"Teléfono: {s['telefono'] or 'N/D'}", False), (f"Fecha del Aporte: {fecha}", False), (f"Nota: {nota or 'Aporte semanal'}", False), ("--------------------------------------------------", False), (f"MONTO APORTADO: {dinero(importe_centavos)}", True), (f"Acciones Adquiridas (RD$100): {acc:,} acciones", False), (f"AHORRO ACUMULADO TOTAL: {dinero(acum_val)} ({tot:,} acc.)", True)]
    html = f"<div style='font-family:Helvetica,Arial;padding:10px;color:#111;font-size:11px;'><h3 style='margin:0;color:#00363d;font-size:14px;'>JJ SMART AHORROS</h3><p style='margin:2px 0 6px;font-size:10px;color:#555;'>Recibo de Ahorro · {ahora}</p><hr><table style='width:100%;font-size:11px;'><tr><td><b>Código:</b></td><td>SOC-{s['id']:05d}</td></tr><tr><td><b>Socio:</b></td><td>{s['nombre']}</td></tr><tr><td><b>Tel:</b></td><td>{s['telefono'] or 'N/D'}</td></tr><tr><td><b>Fecha:</b></td><td>{fecha}</td></tr><tr><td><b>Nota:</b></td><td>{nota or 'Aporte semanal'}</td></tr></table><hr><table style='width:100%;font-size:11px;background:#f4f8fa;'><tr><td style='padding:4px;'><b>Monto:</b></td><td style='text-align:right;padding:4px;'><b>{dinero(importe_centavos)}</b></td></tr><tr><td style='padding:4px;'><b>Acciones:</b></td><td style='text-align:right;padding:4px;'>{acc:,} acc.</td></tr><tr><td style='padding:4px;'><b>Acumulado:</b></td><td style='text-align:right;padding:4px;'><b>{dinero(acum_val)} ({tot:,} acc.)</b></td></tr></table><div style='margin-top:16px;padding-top:8px;border-top:1px dashed #ccc;text-align:center;color:rgba(0,54,61,0.35);font-size:11px;font-weight:bold;letter-spacing:1px;'>JJSMART AHORRO CREADO POR JOSE JOSE BAUTISTA</div></div>"
    _mostrar_vista_previa(parent, f"Recibo - {s['nombre']}", f"Recibo_SOC-{s['id']:05d}", "COMPROBANTE INDIVIDUAL DE AHORRO", lineas, html, ancho=430, alto=460, telefono=s["telefono"])

def imprimir_estado_cuenta_socio(parent, datos, socio_id):
    sid = int(socio_id); s = {x["id"]: x for x in datos.socios()}.get(sid)
    if not s: return
    movs = [m for m in datos.movimientos() if m.get("socio_id") == sid or m.get("nombre") == s["nombre"]]
    prests = [x for x in datos.prestamos() if x.get("socio_id") == sid or x.get("nombre") == s["nombre"]]
    ahora = datetime.now().strftime("%d/%m/%Y %I:%M %p")
    lineas = [(f"Emitido: {ahora}", False), (f"Código: SOC-{s['id']:05d}   |   Tel: {s['telefono'] or 'N/D'}", False), (f"Socio: {s['nombre']}", True), (f"Ahorro Acumulado: {dinero(s['ahorro'])} ({s['ahorro']//ACCION:,} acciones)", True), (f"Deuda Pendiente en Préstamos: {dinero(s['deuda'])}", True), ("--------------------------------------------------", False), ("HISTORIAL DE MOVIMIENTOS:", True)] + [(f"{m['fecha']}  |  {m['tipo']}  |  {dinero(m['importe'])}  {m['nota']}", False) for m in movs] + [("--------------------------------------------------", False), ("PRÉSTAMOS DEL SOCIO:", True)] + [(f"Ref {str(x['id'])[:8]}  |  {x['fecha']}  |  Cap: {dinero(x['capital'])}  |  Pend: {dinero(x['capital_pendiente'])}", False) for x in prests]
    fm = "".join(f"<tr><td style='padding:3px;border-bottom:1px solid #ddd;'>{m['fecha']}</td><td style='padding:3px;border-bottom:1px solid #ddd;'>{m['tipo']}</td><td style='padding:3px;border-bottom:1px solid #ddd;text-align:right;'>{dinero(m['importe'])}</td><td style='padding:3px;border-bottom:1px solid #ddd;'>{m['nota']}</td></tr>" for m in movs) or "<tr><td colspan='4'>Sin movimientos</td></tr>"
    fp = "".join(f"<tr><td style='padding:3px;border-bottom:1px solid #ddd;'>{str(x['id'])[:8]}</td><td style='padding:3px;border-bottom:1px solid #ddd;'>{x['fecha']}</td><td style='padding:3px;border-bottom:1px solid #ddd;text-align:right;'>{dinero(x['capital'])}</td><td style='padding:3px;border-bottom:1px solid #ddd;text-align:right;'>{dinero(x['capital_pendiente'])}</td></tr>" for x in prests) or "<tr><td colspan='4'>Sin préstamos</td></tr>"
    html = f"<div style='font-family:Helvetica,Arial;padding:10px;color:#111;font-size:11px;'><h3 style='margin:0;color:#00363d;'>JJ SMART AHORROS</h3><p style='margin:2px 0 8px;color:#07589c;font-weight:bold;'>ESTADO DE CUENTA INDIVIDUAL · {ahora}</p><table style='width:100%;background:#f2f6f9;padding:6px;font-size:11px;'><tr><td><b>Código:</b> SOC-{s['id']:05d}</td><td><b>Tel:</b> {s['telefono'] or 'N/D'}</td></tr><tr><td colspan='2'><b>Socio:</b> {s['nombre']}</td></tr><tr><td><b>Ahorro:</b> {dinero(s['ahorro'])}</td><td><b>Acciones:</b> {s['ahorro']//ACCION:,}</td></tr><tr><td colspan='2'><b>Deuda Préstamos:</b> {dinero(s['deuda'])}</td></tr></table><h4 style='margin:10px 0 4px;'>Movimientos</h4><table style='width:100%;border-collapse:collapse;font-size:10px;'><tr style='background:#e6eef4;'><th>Fecha</th><th>Tipo</th><th>Importe</th><th>Nota</th></tr>{fm}</table><h4 style='margin:10px 0 4px;'>Préstamos</h4><table style='width:100%;border-collapse:collapse;font-size:10px;'><tr style='background:#e6eef4;'><th>Ref</th><th>Fecha</th><th>Capital</th><th>Pendiente</th></tr>{fp}</table><div style='margin-top:16px;padding-top:8px;border-top:1px dashed #ccc;text-align:center;color:rgba(0,54,61,0.35);font-size:11px;font-weight:bold;letter-spacing:1px;'>JJSMART AHORRO CREADO POR JOSE JOSE BAUTISTA</div></div>"
    _mostrar_vista_previa(parent, f"Estado - {s['nombre']}", f"Estado_SOC-{s['id']:05d}", "ESTADO DE CUENTA INDIVIDUAL DEL SOCIO", lineas, html, ancho=480, alto=520, telefono=s["telefono"])
