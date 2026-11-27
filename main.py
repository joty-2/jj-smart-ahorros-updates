import impresion_ahorros
"""JJ SMART AHORROS 1.0 — aplicacion independiente del grupo de ahorro."""
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
from uuid import uuid4
from PySide6.QtGui import QPixmap,QIcon
from PySide6.QtCore import QDate,QTimer,Qt,QLockFile
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,
    QDialog,QFormLayout,QLineEdit,QDialogButtonBox,QMessageBox,QComboBox,QDateEdit,
    QFileDialog,QInputDialog,QAbstractItemView)
from ahorros_datos import centavos,dinero,ACCION
from prestamos_flexibles import Datos

STYLE='\n* {font-family:Arial;font-size:13px;}\nQWidget {background:#0B1422;color:#E5EEF8;}\nQWidget#side {background:#0E1D30;border-right:1px solid #22364C;}\nQWidget#page {background:#0B1422;}\nQFrame#card {background:#13243A;border:1px solid #29415B;border-radius:14px;}\nQFrame#hero {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #123C51,stop:1 #12283F);border:1px solid #226276;border-radius:14px;}\nQLabel {background:transparent;border:none;}\nQLabel#page_title {font-size:25px;font-weight:bold;color:#F1F7FD;}\nQLabel#subtitle {color:#8EA8C1;font-size:13px;}\nQLabel#metric_title {color:#91ABC5;font-size:12px;}\nQLabel#metric_value {font-size:23px;font-weight:bold;color:#F0F8FF;}\nQLabel#metric_note {font-size:11px;color:#8EA8C1;}\nQLabel#section_title {font-size:16px;font-weight:bold;color:#E8F3FD;}\nQLabel#titulo {font-size:25px;font-weight:bold;color:#42D9CE;}\nQLineEdit,QComboBox,QDateEdit {background:#13263D;color:#F1F7FD;border:1px solid #365673;border-radius:8px;padding:10px;selection-background-color:#086CB5;}\nQComboBox QAbstractItemView {background:#152A41;color:white;selection-background-color:#087AB8;}\nQPushButton {background:#086AC7;color:white;border:1px solid #218BE8;border-radius:9px;padding:11px 14px;font-weight:bold;}\nQPushButton:hover {background:#0B81E4;border-color:#45AEFF;}\nQPushButton:pressed {background:#0755A1;}\nQPushButton:disabled {background:#22364A;color:#7891AA;border-color:#2D4358;}\nQPushButton#primary {background:#12A89C;color:#061D26;border:1px solid #49D7CA;}\nQPushButton#primary:hover {background:#37C7B8;}\nQPushButton#secondary {background:#192D45;border-color:#34526F;color:#D7E8F9;}\nQPushButton#nav {background:transparent;border:none;text-align:left;padding:13px 16px;color:#A6BAD0;font-size:14px;font-weight:normal;}\nQPushButton#nav:hover {background:#172C44;color:#F3F8FF;}\nQPushButton#nav:checked {background:#153D52;color:#51E0D0;border-left:3px solid #39D3C1;font-weight:bold;}\nQTableWidget {background:#102035;alternate-background-color:#13263C;border:1px solid #29405A;border-radius:10px;gridline-color:#213A53;selection-background-color:#1B5374;selection-color:white;}\nQTableWidget::item {padding:8px;border-bottom:1px solid #20364B;}\nQHeaderView::section {background:#182D44;color:#91ADC8;padding:11px 8px;border:none;border-bottom:1px solid #2C4864;font-size:12px;font-weight:bold;}\nQTabWidget::pane {border:0;background:#0B1422;}\nQScrollArea {border:none;background:#0B1422;}\nQScrollBar:vertical {background:#101F31;width:10px;margin:0;}\nQScrollBar::handle:vertical {background:#365774;min-height:36px;border-radius:5px;}\nQScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}\nQScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:none;}\nQStatusBar {background:#0C1B2B;border-top:1px solid #223A51;}\nQStatusBar QLabel {font-size:11px;color:#A9BED3;padding:3px 8px;}\nQDialog {background:#0E1E31;}\n'



def logo_ahorros(tamano):
    imagen=QPixmap(str(Path(__file__).resolve().parent/'assets/logo_ahorros.png'))
    etiqueta=QLabel()
    etiqueta.setAlignment(Qt.AlignCenter)
    etiqueta.setFixedHeight(tamano)
    if not imagen.isNull():
        etiqueta.setPixmap(imagen.scaled(tamano,tamano,Qt.KeepAspectRatio,Qt.SmoothTransformation))
    else:
        etiqueta.setText('JJ SMART AHORROS')
    etiqueta.setAccessibleName('Logo JJ SMART AHORROS')
    return etiqueta


class Acceso(QDialog):
    def __init__(self,datos):
        super().__init__();self.datos=datos;self.nuevo=datos.necesita_admin();self.intentos=0
        self.setWindowTitle('JJ SMART AHORROS | '+('Crear acceso' if self.nuevo else 'Iniciar sesión'));self.resize(450,310)
        self.resize(450,520)
        layout=QVBoxLayout(self);layout.addWidget(logo_ahorros(154))
        title=QLabel('JJ SMART AHORROS');title.setObjectName('titulo');title.setAlignment(Qt.AlignCenter);layout.addWidget(title)
        note=QLabel('Crea el acceso para administrar el grupo de ahorro.' if self.nuevo else 'Introduce el acceso de este grupo de ahorro.');note.setWordWrap(True);layout.addWidget(note)
        form=QFormLayout();self.user=QLineEdit();self.password=QLineEdit();self.password.setEchoMode(QLineEdit.Password)
        form.addRow('Usuario:',self.user);form.addRow('Contraseña:',self.password)
        self.confirm=QLineEdit();self.confirm.setEchoMode(QLineEdit.Password)
        if self.nuevo:form.addRow('Repetir contraseña:',self.confirm)
        layout.addLayout(form);self.message=QLabel('');layout.addWidget(self.message)
        self.enter=QPushButton('CREAR ACCESO' if self.nuevo else 'INGRESAR');self.enter.clicked.connect(self.validar);layout.addWidget(self.enter)
        self.password.returnPressed.connect(self.validar)
        forgot=QPushButton('Olvidé mi contraseña');forgot.setObjectName('secondary')
        from recuperacion_ahorros import mostrar_recuperacion
        forgot.clicked.connect(lambda:mostrar_recuperacion(self.datos,self));layout.addWidget(forgot)
    def validar(self):
        if not self.enter.isEnabled():return
        try:
            if self.nuevo:
                if self.password.text()!=self.confirm.text():raise ValueError('Las contrasenas no coinciden.')
                self.datos.crear_admin(self.user.text(),self.password.text())
            elif not self.datos.entrar(self.user.text(),self.password.text()):
                self.intentos+=1
                if self.intentos%5==0:
                    self.enter.setEnabled(False);QTimer.singleShot(30000,lambda:self.enter.setEnabled(True))
                    raise ValueError('Acceso incorrecto. Espera 30 segundos para volver a intentar.')
                raise ValueError('Usuario o contrasena incorrectos.')
            self.password.clear();self.confirm.clear();self.accept()
        except Exception as e:self.message.setText(str(e))


class Formulario(QDialog):
    def __init__(self,title,parent):
        super().__init__(parent);self.setWindowTitle(title);self.resize(530,360)
        layout=QVBoxLayout(self);self.form=QFormLayout();layout.addLayout(self.form)
        self.info=QLabel('');self.info.setWordWrap(True);layout.addWidget(self.info)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setText('Registrar')
        self.buttons.button(QDialogButtonBox.Cancel).setText('Cancelar')
        self.buttons.rejected.connect(self.reject);layout.addWidget(self.buttons)
    def texto(self,label,default=''):
        widget=QLineEdit(default);self.form.addRow(label,widget);return widget
    def fecha(self):
        widget=QDateEdit(QDate.currentDate());widget.setCalendarPopup(True);widget.setDisplayFormat('dd/MM/yyyy');widget.setMaximumDate(QDate.currentDate());self.form.addRow('Fecha:',widget);return widget
    def socio(self,datos):
        widget=QComboBox()
        for s in datos.socios():widget.addItem(f"SOC-{s['id']:05d} · {s['nombre']}",s['id'])
        self.form.addRow('Socio:',widget);return widget
    def registrar(self,operation,success,parent):
        self.buttons.setEnabled(False)
        try:operation();self.accept();parent.refrescar();QMessageBox.information(parent,'Registro guardado',success)
        except Exception as e:QMessageBox.warning(self,'No se registro',str(e));self.buttons.setEnabled(True)


class Ventana(QMainWindow):
    def __init__(self,datos):
        super().__init__()
        from PySide6.QtWidgets import QFrame,QGridLayout,QScrollArea,QSizePolicy
        self.datos=datos;self.setWindowTitle('JJ SMART AHORROS 1.1.7')
        area=QApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(min(760,area.width()),min(460,area.height()-40))
        self.resize(min(1180,area.width()),min(800,max(460,area.height()-40)))
        root=QWidget();outer=QHBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        side=QWidget();side.setObjectName('side');side.setFixedWidth(205)
        nav=QVBoxLayout(side);nav.setContentsMargins(16,24,16,18);nav.setSpacing(7)
        nav.addWidget(logo_ahorros(132 if area.height()<700 else 152))
        label=QLabel('JJ SMART SOFTWARE');label.setObjectName('subtitle');label.setStyleSheet('font-size:10px;letter-spacing:1px;padding-top:6px;');nav.addWidget(label);nav.addSpacing(12)
        self.nav_buttons=[]
        for i,text in enumerate(('Inicio','Socios','Movimientos','Préstamos','Balance')):
            b=QPushButton(text);b.setObjectName('nav');b.setCheckable(True);b.setChecked(i==0)
            b.clicked.connect(lambda checked=False,index=i:self.tabs.setCurrentIndex(index));nav.addWidget(b);self.nav_buttons.append(b)
        from recuperacion_ahorros import seguridad
        security=QPushButton('Seguridad y acceso');security.setObjectName('secondary');security.clicked.connect(lambda:seguridad(self.datos,self));nav.addWidget(security)
        salir=QPushButton('Salir');salir.setObjectName('secondary');salir.clicked.connect(self.close);nav.addWidget(salir)
        nav.addStretch();local=QLabel('●  Funciona sin Internet');local.setStyleSheet('color:#50D9B7;font-size:11px;');nav.addWidget(local)
        version_label=QLabel('Versión 1.1.7  ·  Datos en esta Mac');version_label.setObjectName('subtitle');version_label.setStyleSheet('font-size:10px;');nav.addWidget(version_label)
        outer.addWidget(side)
        content=QWidget();content.setObjectName('page');body=QVBoxLayout(content);body.setContentsMargins(22,18,22,10);body.setSpacing(18)
        header=QHBoxLayout();self.page_title=QLabel('Resumen del grupo');self.page_title.setObjectName('page_title');header.addWidget(self.page_title);header.addStretch()
        day=QLabel(QDate.currentDate().toString('dd/MM/yyyy'));day.setObjectName('subtitle');header.addWidget(day)
        refresh=QPushButton('Actualizar');refresh.setObjectName('secondary');refresh.clicked.connect(self.refrescar);header.addWidget(refresh);body.addLayout(header)
        self.tabs=QTabWidget();self.tabs.tabBar().hide();self.tabs.setMinimumSize(0,0);self.tabs.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Ignored);body.addWidget(self.tabs,1);outer.addWidget(content,1)
        self.home=QWidget();box=QVBoxLayout(self.home);box.setContentsMargins(0,0,8,4);box.setSpacing(18)
        hero=QFrame();hero.setObjectName('hero');hero_box=QVBoxLayout(hero);hero_box.setContentsMargins(22,20,22,20)
        title=QLabel('Tu grupo de ahorro, en orden.');title.setStyleSheet('font-size:22px;font-weight:bold;');hero_box.addWidget(title)
        self.resumen_acciones=QLabel();self.resumen_acciones.setWordWrap(True);self.resumen_acciones.setStyleSheet('color:#A6D5DC;font-size:13px;');hero_box.addWidget(self.resumen_acciones);box.addWidget(hero)
        grid=QGridLayout();grid.setHorizontalSpacing(12);grid.setVerticalSpacing(12);self.metric_values={}
        for i,(key,label,note) in enumerate((('caja','DISPONIBLE EN CAJA','Dinero disponible para el grupo'),('aportes','AHORRO ACUMULADO','Suma de los aportes registrados'),('capital_pendiente','CAPITAL POR COBRAR','Préstamos pendientes de devolver'),('interes_cobrado','INTERESES COBRADOS','Pagos de interés recibidos'))):
            card=QFrame();card.setObjectName('card');col=QVBoxLayout(card);col.setContentsMargins(16,17,16,17);col.setSpacing(8)
            caption=QLabel(label);caption.setObjectName('metric_title');col.addWidget(caption)
            value=QLabel('RD$ 0.00');value.setObjectName('metric_value');value.setTextInteractionFlags(Qt.TextSelectableByMouse);col.addWidget(value);self.metric_values[key]=value
            hint=QLabel(note);hint.setObjectName('metric_note');hint.setWordWrap(True);col.addWidget(hint);grid.addWidget(card,i//2,i%2)
        box.addLayout(grid)
        actions=QHBoxLayout();actions.setSpacing(10)
        for i,(text,fn) in enumerate((('+ Registrar aporte',self.aporte),('Registrar préstamo',self.prestamo),('Registrar pago',self.abono))):
            b=QPushButton(text);b.setObjectName('primary' if i==0 else 'secondary');b.clicked.connect(fn);actions.addWidget(b)
        box.addLayout(actions)
        recent_header=QHBoxLayout();title=QLabel('Últimos movimientos');title.setObjectName('section_title');recent_header.addWidget(title);recent_header.addStretch()
        see=QPushButton('Ver todos');see.setObjectName('secondary');see.clicked.connect(lambda:self.tabs.setCurrentIndex(2));recent_header.addWidget(see);box.addLayout(recent_header)
        self.recientes=QTableWidget(0,4);self.recientes.setHorizontalHeaderLabels(['Fecha','Socio','Movimiento','Importe']);self.recientes.setEditTriggers(QAbstractItemView.NoEditTriggers);self.recientes.setAlternatingRowColors(True)
        self.recientes.setSelectionBehavior(QAbstractItemView.SelectRows);self.recientes.verticalHeader().hide();self.recientes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents);self.recientes.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.recientes.horizontalHeader().setStretchLastSection(True);self.recientes.setMinimumHeight(190);self.recientes.setMaximumHeight(265);self.recientes.verticalHeader().setDefaultSectionSize(38);box.addWidget(self.recientes)
        self.empty_state=QLabel('Todavía no hay movimientos. Agrega un socio y registra su primer aporte.');self.empty_state.setObjectName('subtitle');self.empty_state.setWordWrap(True);box.addWidget(self.empty_state)
        utilities=QHBoxLayout();self.add_button(utilities,'Resumen anual',self.anual).setObjectName('secondary');self.add_button(utilities,'Crear respaldo',self.respaldo).setObjectName('secondary');self.add_button(utilities,'🔄 Actualizaciones',self.abrir_actualizaciones).setObjectName('secondary');self.add_button(utilities,'🔐 Control Propietario',self.abrir_control_propietario).setObjectName('secondary');utilities.addStretch();box.addLayout(utilities)
        note=QLabel('Una acción = RD$100 · Aportes semanales variables · El reparto anual se definirá con las reglas del grupo.');note.setObjectName('subtitle');note.setWordWrap(True);box.addWidget(note);box.addStretch()
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(self.home);self.tabs.addTab(scroll,'Inicio')
        self.socios_tab,self.socios_table=self.tabla(['Código','Socio','Teléfono','Ahorro acumulado','Acciones','Capital pendiente','Estado de cuenta'],'Socios',[('+ Agregar socio',self.nuevo_socio),('✎ Editar nombre',self.editar_socio),('🗑 Eliminar socio',self.eliminar_socio)])
        _,self.aportes_table=self.tabla(['Fecha','Socio','Tipo','Importe','Nota'],'Movimientos',[('Registrar aporte',self.aporte),('Exportar CSV',self.exportar)])
        _,self.prestamos_table=self.tabla(['Referencia','Socio','Fecha','Capital entregado','Interés mensual','Capital pendiente','Interés vencido'],'Préstamos',[('Nuevo préstamo',self.prestamo),('Registrar pago',self.abono),('Ver cuotas y pagos',self.ver_cuotas)])
        _,self.balance_table=self.tabla(['Concepto','Importe'],'Balance',[('Actualizar',self.refrescar),('Resumen anual',self.anual)])
        for table in (self.socios_table,self.aportes_table,self.prestamos_table,self.balance_table):
            table.verticalHeader().hide();table.verticalHeader().setDefaultSectionSize(42);table.setShowGrid(False)
        def page_changed(index):
            for i,b in enumerate(self.nav_buttons):b.setChecked(i==index)
            self.page_title.setText(('Resumen del grupo','Socios','Movimientos','Préstamos y abonos','Balance del grupo')[index])
        self.tabs.currentChanged.connect(page_changed)
        self.setCentralWidget(root);self.statusBar().setSizeGripEnabled(False);self.statusBar().addPermanentWidget(QLabel('Creado por: José José Bautista'))
        self.refrescar()
        from PySide6.QtCore import QTimer
        from actualizaciones_ahorros import verificar_notificacion_inicio
        QTimer.singleShot(2500, lambda: verificar_notificacion_inicio(self))

    def abrir_actualizaciones(self):
        from actualizaciones_ahorros import Actualizaciones
        Actualizaciones(self).exec()

    def abrir_control_propietario(self):
        from panel_propietario import verificar_acceso_propietario, PanelPropietario
        if verificar_acceso_propietario(self):
            PanelPropietario(self).exec()

    def closeEvent(self,event):
        if QMessageBox.question(self,'Salir de JJ SMART AHORROS','¿Deseas salir? Los registros guardados se conservan.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def ver_cuotas(self):
        from prestamos_interfaz import ver_cuotas
        ver_cuotas(self)

    def add_button(self,layout,text,fn):
        b=QPushButton(text);b.clicked.connect(fn);layout.addWidget(b);return b
    def tabla(self,headers,title,actions):
        page=QWidget();layout=QVBoxLayout(page);row=QHBoxLayout()
        for text,fn in actions:self.add_button(row,text,fn)
        row.addStretch();layout.addLayout(row)
        table=QTableWidget(0,len(headers));table.setHorizontalHeaderLabels(headers);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setAlternatingRowColors(True);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents);table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table);self.tabs.addTab(page,title);return page,table
    @staticmethod
    def llenar(table,rows):
        table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,value in enumerate(row):table.setItem(i,j,QTableWidgetItem(str(value)))
    def refrescar(self):
        try:
            r=self.datos.resumen()
            for key,label in self.metric_values.items():label.setText(dinero(r[key]))
            self.resumen_acciones.setText(f"{r['socios']} socios  ·  {r['acciones']:,} acciones acumuladas  ·  Cada acción vale RD$100")
            movimientos=self.datos.movimientos()
            self.llenar(self.recientes,[(m['fecha'],m['nombre'],{'APORTE':'Aporte','PRESTAMO':'Préstamo','ABONO':'Abono'}[m['tipo']],dinero(m['importe'])) for m in movimientos[:5]])
            self.empty_state.setVisible(not movimientos)
            socs=self.datos.socios()
            self.llenar(self.socios_table,[(f"SOC-{s['id']:05d}",s['nombre'],s['telefono'],dinero(s['ahorro']),s['ahorro']//ACCION,dinero(s['deuda']),'') for s in socs])
            from impresion_ahorros import imprimir_estado_cuenta_socio, imprimir_recibo_aporte
            for i,s in enumerate(socs):
                b=QPushButton('📄 Estado');b.setCursor(Qt.PointingHandCursor);b.setStyleSheet('padding:4px 8px;font-size:12px;');b.clicked.connect(lambda checked=False,sid=s['id']:imprimir_estado_cuenta_socio(self,self.datos,sid));self.socios_table.setCellWidget(i,6,b)
            self.llenar(self.aportes_table,[(m['fecha'],m['nombre'],m['tipo'],dinero(m['importe']),m['nota']) for m in self.datos.movimientos()])
            self.llenar(self.prestamos_table,[(p['id'][:8],p['nombre'],p['fecha'],dinero(p['capital']),(dinero(p['interes_mensual']) if p['plan_mensual'] else 'Total anterior: '+dinero(p['interes'])),dinero(p['capital_pendiente']),dinero(p['interes_pendiente'])) for p in self.datos.prestamos()])
            rows=[('Aportes acumulados',r['aportes']),('Dinero en caja',r['caja']),('Capital por cobrar',r['capital_pendiente']),('Interes cobrado',r['interes_cobrado']),('Interés vencido pendiente',r['interes_pendiente']),('Caja + capital por cobrar',r['caja']+r['capital_pendiente'])]
            self.llenar(self.balance_table,[(k,dinero(v)) for k,v in rows]);self.statusBar().showMessage('Datos locales guardados · Versión 1.1.7')
        except Exception as e:QMessageBox.warning(self,'Datos',str(e))
    def _sel_soc(self):
        r=self.socios_table.currentRow()
        if r<0: QMessageBox.information(self,"Aviso","Selecciona un socio."); return None
        return int(self.socios_table.item(r,0).text().replace("SOC-","")),self.socios_table.item(r,1).text()
    def editar_socio(self):
        s=self._sel_soc()
        if not s: return
        nom,ok=QInputDialog.getText(self,"Editar socio","Nuevo nombre:",text=s[1])
        if ok and nom.strip(): self.datos.editar_socio(s[0],nom); self.refrescar()
    def eliminar_socio(self):
        s=self._sel_soc()
        if not s: return
        if QMessageBox.question(self,"Eliminar",f"¿Eliminar a {s[1]}?")==QMessageBox.Yes:
            try: self.datos.eliminar_socio(s[0]); self.refrescar()
            except Exception as e: QMessageBox.warning(self,"Bloqueado",str(e))
    def nuevo_socio(self):
        d=Formulario('Agregar socio',self);name=d.texto('Nombre:');phone=d.texto('Telefono (opcional):')
        d.buttons.accepted.connect(lambda:d.registrar(lambda:self.datos.socio(name.text(),phone.text()),'Socio agregado.',self));d.exec()
    def hay_socios(self):
        if self.datos.socios():return True
        QMessageBox.information(self,'Socios','Primero agrega un socio en la pestana Socios.');return False
    def aporte(self):
        from registro_continuo_ahorros import abrir_registro_continuo
        abrir_registro_continuo(self)
    def prestamo(self):
        from prestamos_interfaz import crear_prestamo
        crear_prestamo(self,Formulario)
    def abono(self):
        from prestamos_interfaz import registrar_pago
        registrar_pago(self,Formulario)
    def anual(self):
        year,ok=QInputDialog.getInt(self,'Resumen anual','Ano a resumir:',date.today().year,1900,date.today().year)
        if not ok:return
        r=self.datos.resumen(year)
        QMessageBox.information(self,'Preparacion del cierre anual',f"Ano: {year}\nAportes de ese ano: {dinero(r['aportes_anuales'])}\nIntereses cobrados ese ano: {dinero(r['interes_anual'])}\n\nSaldo actual de caja: {dinero(r['caja'])}\nCapital pendiente actual: {dinero(r['capital_pendiente'])}\n\nRESUMEN PRELIMINAR. No distribuye ganancias ni cierra el ano. Falta acordar las reglas del reparto anual.")
    def respaldo(self):
        try:QMessageBox.information(self,'Respaldo creado','Copia guardada en:\n'+str(self.datos.respaldo()))
        except Exception as e:QMessageBox.warning(self,'Respaldo',str(e))
    def exportar(self):
        path,_=QFileDialog.getSaveFileName(self,'Exportar movimientos',str(Path.home()/f'ahorros_movimientos_{date.today()}.csv'),'CSV (*.csv)')
        if not path:return
        try:
            def safe(t):
                t=str(t)
                return "'"+t if t.lstrip().startswith(('=','+','-','@','\t','\r')) else t
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f);writer.writerow(['Fecha','Socio','Tipo','Importe_RD','Nota'])
                for m in self.datos.movimientos():writer.writerow([m['fecha'],safe(m['nombre']),m['tipo'],str(Decimal(m['importe'])/100),safe(m['nota'])])
            QMessageBox.information(self,'Exportacion','Movimientos exportados correctamente.')
        except Exception as e:QMessageBox.warning(self,'Exportacion',str(e))


from panel_referencia import aplicar
aplicar(Ventana,logo_ahorros)
from socios_voz import instalar
instalar(Ventana)

def main():
    if '--verificar-motor-voz' in sys.argv:
        from vosk import Model,SetLogLevel
        SetLogLevel(-1)
        Model(str(Path(__file__).resolve().parent/'assets/vosk-es'))
        print('MOTOR DE VOZ EMPAQUETADO: OK');return
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough);app=QApplication(sys.argv);app.setApplicationName('JJ SMART AHORROS');app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent/'assets/logo_ahorros.png')));app.setOrganizationName('JJ SMART SOFTWARE');app.setStyle('Fusion');app.setStyleSheet(STYLE)
    datos=Datos();lock=QLockFile(str(datos.path.parent/'sesion.lock'))
    if not lock.tryLock(100):QMessageBox.information(None,'JJ SMART AHORROS','El sistema de ahorro ya esta abierto.');return
    if Acceso(datos).exec()!=QDialog.Accepted:return
    # Copia diaria previa al trabajo. No depende de ningun archivo de JJ SMART POS.
    folder=datos.path.parent/'Respaldos'
    if not folder.exists() or not any(folder.glob('ahorros_'+date.today().strftime('%Y%m%d')+'_*')):
        try:datos.respaldo()
        except Exception as e:QMessageBox.warning(None,'Respaldo automatico','No se pudo guardar el respaldo diario: '+str(e))
    window=Ventana(datos);window.showMaximized()
    from recuperacion_ahorros import recordar_configuracion
    QTimer.singleShot(150,lambda:recordar_configuracion(datos,window))
    sys.exit(app.exec())

if __name__=='__main__':main()
