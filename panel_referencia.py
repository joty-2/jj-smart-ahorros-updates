"""Panel visual; conserva servicios y formularios existentes."""
from datetime import date
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,QScrollArea,QComboBox,QTableWidget,QHeaderView,QAbstractItemView,QDialog,QLineEdit)
from ahorros_datos import dinero,ACCION

def aplicar(Ventana,logo):
    anterior=Ventana.__init__; refrescar_anterior=Ventana.refrescar
    def iniciar(self,datos):
        anterior(self,datos)
        self.setWindowTitle('JJ SMART AHORROS 1.2.2')
        # Conservar las páginas y sus acciones; sustituir únicamente el contenedor visual.
        viejo=self.takeCentralWidget();self._panel_anterior=viejo
        self.tabs.setParent(None)
        root=QWidget();root.setStyleSheet('QWidget{background:#00162c;} QLabel{background:transparent;}')
        outer=QVBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        top=QFrame();top.setStyleSheet('QFrame{background:#001b36;border-bottom:1px solid #135681;}')
        h=QHBoxLayout(top);h.setContentsMargins(22,12,22,12);h.addWidget(logo(84))
        brand=QLabel('<b><i>JJ SMART AHORROS</i></b><br><span style="font-size:14px;color:#a9d6ef">JJ SMART SOFTWARE</span>');brand.setStyleSheet('font-size:27px;');h.addWidget(brand)
        subtitle=QLabel('Sistema de Ahorro por Acciones y Préstamos');subtitle.setWordWrap(True);subtitle.setStyleSheet('font-size:15px;color:#bdd9ef;padding-left:18px;');h.addWidget(subtitle,1)
        self.btn_volver=QPushButton('← Volver');self.btn_volver.setCursor(Qt.PointingHandCursor);self.btn_volver.setStyleSheet('QPushButton{background:#0b4f82;color:white;font-size:15px;font-weight:bold;padding:8px 16px;border:1px solid #3ea6e8;border-radius:10px;} QPushButton:hover{background:#1268a8;border:2px solid #73e4ff;}');self.btn_volver.hide();h.addWidget(self.btn_volver);self.btn_fs=QPushButton('⛶ Pantalla Completa');self.btn_fs.setCursor(Qt.PointingHandCursor);self.btn_fs.setStyleSheet('QPushButton{background:#0b4f82;color:white;font-size:13px;font-weight:bold;padding:8px 14px;border:1px solid #3ea6e8;border-radius:10px;} QPushButton:hover{background:#1268a8;}')
        def _toggle_fs():
            if self.isFullScreen():
                self.showMaximized(); self.btn_fs.setText('⛶ Pantalla Completa')
            else:
                self.showFullScreen(); self.btn_fs.setText('🗗 Salir Pantalla Completa')
        self.btn_fs.setText('🗗 Salir Pantalla Completa')
        self.btn_fs.clicked.connect(_toggle_fs)
        QShortcut(QKeySequence('F11'), self, activated=_toggle_fs)
        QTimer.singleShot(250, self.showFullScreen)
        h.addWidget(self.btn_fs)
        outer.addWidget(top)
        body=QHBoxLayout();body.setSpacing(0);outer.addLayout(body,1)
        side=QWidget();side.setFixedWidth(205);side.setStyleSheet('background:#00203b;border-right:1px solid #14446b;');nav=QVBoxLayout(side);nav.setContentsMargins(9,18,9,16)
        self.nav_buttons=[]
        for i,text in enumerate(('⌂  Inicio','♟  Socios','▣  Ahorros','＄  Préstamos','▥  Balance')):
            b=QPushButton(text);b.setObjectName('nav');b.setMinimumHeight(52);b.setCheckable(True);b.clicked.connect(lambda checked=False,index=i:self.tabs.setCurrentIndex(index));nav.addWidget(b);self.nav_buttons.append(b)
        for text,fn in [('▣  Cierre Anual',self.anual),('⚙  Configuración',lambda:configuracion(self)),('⏻  Salir',self.close)]:
            b=QPushButton(text);b.setObjectName('nav');b.setMinimumHeight(49);b.clicked.connect(fn);nav.addWidget(b)
        nav.addStretch();word=QLabel('<b><i>JJ SMART</i></b><br>SOFTWARE');word.setAlignment(Qt.AlignCenter);word.setStyleSheet('border:none;background:transparent;font-size:23px;color:white;padding:15px;');nav.addWidget(word)
        navscroll=QScrollArea();navscroll.setFrameShape(QFrame.NoFrame);navscroll.setStyleSheet('QScrollArea{border:none;background:#00203b;}');navscroll.setWidgetResizable(True);navscroll.setFixedWidth(207);navscroll.setWidget(side);body.addWidget(navscroll)
        body.addWidget(self.tabs,1)
        self._hist_tabs=[]
        def _al_cambiar_tab(idx):
            self.btn_volver.setVisible(idx!=0)
            if not getattr(self,'_volviendo',False) and (not self._hist_tabs or self._hist_tabs[-1]!=idx):
                self._hist_tabs.append(idx)
        def _ir_atras():
            self._volviendo=True
            if len(self._hist_tabs)>1:
                self._hist_tabs.pop()
                self.tabs.setCurrentIndex(self._hist_tabs[-1])
            else:
                self._hist_tabs=[0]
                self.tabs.setCurrentIndex(0)
            self._volviendo=False
        self.btn_volver.clicked.connect(_ir_atras)
        self.tabs.currentChanged.connect(_al_cambiar_tab)
        home=QWidget();box=QVBoxLayout(home);box.setContentsMargins(20,20,20,16);box.setSpacing(20)
        acts=QGridLayout();acts.setSpacing(14)
        for i,(ico,text,fn,color) in enumerate([('♟ +','Nuevo Socio',self.nuevo_socio,'#0876d0'),('▣ +','Registrar Ahorro',self.aporte,'#00a27d'),('＄','Nuevo Préstamo',self.prestamo,'#ed7900'),('⌕','Consultar Socio',lambda:(self.tabs.setCurrentIndex(1),consultar(self)),'#7040b6')]):
            b=QPushButton(ico+'\n'+text);b.setMinimumHeight(95);b.setCursor(Qt.PointingHandCursor);b.setStyleSheet(f'QPushButton{{font-size:17px;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {color},stop:1 #07355d);border:1px solid {color};border-radius:17px;}} QPushButton:hover{{border:2px solid #73e4ff;}}');b.clicked.connect(fn);acts.addWidget(b,0,i)
        box.addLayout(acts)
        cards=QGridLayout();cards.setSpacing(15);self.panel_values={}
        specs=[('socios','♟','Total de Socios','#00616a','#00363d',1),('acciones','▱','Acciones Totales','#07589c','#002d60',2),('aportes','▣','Ahorro Acumulado','#51368b','#241449',2),('capital_pendiente','＄','Préstamos Activos','#9e6507','#4b2c00',3)]
        for i,(key,ico,title,c1,c2,tab_idx) in enumerate(specs):
            card=QPushButton();card.setMinimumWidth(190);card.setMinimumHeight(115);card.setCursor(Qt.PointingHandCursor);card.setStyleSheet(f'QPushButton{{text-align:left;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {c1},stop:1 {c2});border:1px solid {c1};border-radius:16px;}} QPushButton:hover{{border:2px solid #73e4ff;}} QLabel{{border:0;background:transparent;}}');col=QVBoxLayout(card);col.setContentsMargins(20,15,16,18)
            icon=QLabel(ico);icon.setStyleSheet('font-size:34px;color:#77e6ef;');col.addWidget(icon);lab=QLabel(title);lab.setStyleSheet('font-size:16px;');col.addWidget(lab);val=QLabel('0');val.setStyleSheet('font-size:24px;font-weight:bold;');col.addWidget(val);self.panel_values[key]=val;card.clicked.connect(lambda checked=False,idx=tab_idx:self.tabs.setCurrentIndex(idx));cards.addWidget(card,0,i)
        box.addLayout(cards)
        row=QHBoxLayout();row.setSpacing(16)
        recent=QFrame();recent.setObjectName('card');rbox=QVBoxLayout(recent);rbox.setContentsMargins(14,14,14,14)
        rh=QHBoxLayout();title=QLabel('Últimos Movimientos');title.setStyleSheet('font-size:21px;font-weight:bold;');rh.addWidget(title);rh.addStretch()
        self.panel_year=QComboBox();self.panel_year.setToolTip('Año de los movimientos; los saldos muestran el total actual.');rh.addWidget(self.panel_year)
        see=QPushButton('Ver Todos');see.clicked.connect(lambda:todos(self));rh.addWidget(see);rbox.addLayout(rh)
        self.panel_recent=QTableWidget(0,5);self.panel_recent.setHorizontalHeaderLabels(['Fecha','Socio','Tipo','Monto','Acciones']);self.panel_recent.setEditTriggers(QAbstractItemView.NoEditTriggers);self.panel_recent.verticalHeader().hide();self.panel_recent.verticalHeader().setDefaultSectionSize(39);self.panel_recent.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents);self.panel_recent.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.panel_recent.setShowGrid(False);self.panel_recent.setMinimumHeight(245);rbox.addWidget(self.panel_recent)
        row.addWidget(recent,3)
        balance=QFrame();balance.setObjectName('card');bl=QVBoxLayout(balance);bl.setContentsMargins(18,18,18,18);t=QLabel('▥  Balance General');t.setStyleSheet('font-size:21px;font-weight:bold;');bl.addWidget(t);self.panel_balance={}
        for key,title in [('aportes','Ahorros Totales'),('capital_pendiente','Préstamos por Cobrar'),('interes_cobrado','Intereses Cobrados'),('caja','Dinero Disponible')]:
            line=QHBoxLayout();lab=QLabel(title);lab.setStyleSheet('font-size:14px;');line.addWidget(lab);value=QLabel();value.setStyleSheet('font-size:16px;font-weight:bold;');value.setAlignment(Qt.AlignRight|Qt.AlignVCenter);line.addWidget(value);bl.addLayout(line);self.panel_balance[key]=value
        row.addWidget(balance,2);box.addLayout(row,1)
        note=QLabel('Saldos actuales · Una acción = RD$100 · Aportes variables sin tope · Funciona sin Internet');note.setWordWrap(True);note.setStyleSheet('color:#91bad7;');box.addWidget(note)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(home)
        self.tabs.removeTab(0);self.tabs.insertTab(0,scroll,'Inicio');self.tabs.setCurrentIndex(0)
        self.setCentralWidget(root)
        self.panel_year.currentIndexChanged.connect(lambda:movimientos(self))
        self.refrescar()
    def refrescar(self):
        refrescar_anterior(self)
        if not hasattr(self,'panel_values'):return
        r=self.datos.resumen()
        for key,val in self.panel_values.items():val.setText(f"{r[key]:,}" if key in ('socios','acciones') else dinero(r[key]))
        for key,val in self.panel_balance.items():val.setText(dinero(r[key]))
        selected=self.panel_year.currentText() or str(date.today().year)
        years=sorted({str(date.today().year)}|{m['fecha'][:4] for m in self.datos.movimientos()},reverse=True)
        self.panel_year.blockSignals(True);self.panel_year.clear();self.panel_year.addItems(years);self.panel_year.setCurrentText(selected if selected in years else years[0]);self.panel_year.blockSignals(False)
        movimientos(self)
        # La página Ahorros contiene exclusivamente aportes; el historial completo está en Ver Todos.
        self.llenar(self.aportes_table,[(m['fecha'],m['nombre'],'Ahorro',dinero(m['importe']),m['nota']) for m in self.datos.movimientos() if m['tipo']=='APORTE'])
        self.statusBar().showMessage('Datos locales guardados · Versión 1.2.0')
    Ventana.__init__=iniciar;Ventana.refrescar=refrescar

def movimientos(w):
    rows=[m for m in w.datos.movimientos() if m['fecha'].startswith(w.panel_year.currentText())][:5]
    labels={'APORTE':'Ahorro','PRESTAMO':'Préstamo','ABONO':'Pago Préstamo'}
    w.llenar(w.panel_recent,[(m['fecha'],m['nombre'],labels[m['tipo']],dinero(m['importe']),f"{m['importe']//ACCION:,}" if m['tipo']=='APORTE' else '—') for m in rows])
    for i,m in enumerate(rows):w.panel_recent.item(i,2).setBackground(QColor({'APORTE':'#006f55','PRESTAMO':'#075a96','ABONO':'#57329b'}[m['tipo']]))

def todos(w):
    d=QDialog(w);d.setWindowTitle('Todos los movimientos');d.resize(850,500);box=QVBoxLayout(d)
    t=QTableWidget(0,5);t.setHorizontalHeaderLabels(['Fecha','Socio','Tipo','Monto','Nota']);t.setEditTriggers(QAbstractItemView.NoEditTriggers);t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents);t.horizontalHeader().setStretchLastSection(True);box.addWidget(t)
    w.llenar(t,[(m['fecha'],m['nombre'],m['tipo'],dinero(m['importe']),m['nota']) for m in w.datos.movimientos()]);b=QPushButton('Cerrar');b.clicked.connect(d.accept);box.addWidget(b);d.exec()

def consultar(w):
    w.tabs.setCurrentIndex(1)
    if not hasattr(w,'buscar_socio'):
        w.buscar_socio=QLineEdit();w.buscar_socio.setPlaceholderText('Buscar socio por nombre, código o teléfono…');w.socios_tab.layout().insertWidget(0,w.buscar_socio)
        def filtrar(text):
            for i in range(w.socios_table.rowCount()):w.socios_table.setRowHidden(i,not any(text.casefold() in w.socios_table.item(i,j).text().casefold() for j in range(3)))
        w.buscar_socio.textChanged.connect(filtrar)
    w.buscar_socio.setFocus()

def configuracion(w):
    from recuperacion_ahorros import seguridad
    from actualizaciones_ahorros import Actualizaciones, es_entorno_desarrollador
    d=QDialog(w);d.setWindowTitle('Configuración · JJ SMART AHORROS');d.resize(460,340)
    d.setStyleSheet('QDialog{background:#00162c;color:white;} QLabel{color:#a9d6ef;} QPushButton{background:#0b4f82;color:white;font-weight:bold;padding:10px;border:1px solid #3ea6e8;border-radius:8px;} QPushButton:hover{background:#1268a8;}')
    box=QVBoxLayout(d)
    opciones=[
        ('🔄 Centro de actualizaciones',lambda:Actualizaciones(w).exec()),
        ('🔐 Seguridad y recuperación de acceso',lambda:seguridad(w.datos,d)),
        ('💾 Crear respaldo de base de datos',w.respaldo),
    ]
    if es_entorno_desarrollador():
        opciones.append(('🚀 Publicar actualización (Desarrollador)',lambda:w.abrir_control_propietario()))
    opciones.append(('Cerrar',d.accept))
    for text,fn in opciones:
        b=QPushButton(text);b.clicked.connect(fn);box.addWidget(b)
    box.addWidget(QLabel('JJ SMART AHORROS 1.2.2\nCreado por: José José Bautista'));d.exec()
