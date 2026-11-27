"""Alta por voz local; audio en memoria y confirmación antes de registrar."""
import json,re,threading,sys
from pathlib import Path
import numpy as np
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLineEdit,QPushButton,QLabel,QHBoxLayout,QCheckBox,QMessageBox)

def reducir_ruido(audio,referencia,rate=16000):
    """Sustracción espectral suave de ruido estacionario con solapamiento."""
    audio=np.asarray(audio,dtype=np.float64).reshape(-1)
    referencia=np.asarray(referencia,dtype=np.float64).reshape(-1)
    if len(audio)<512 or len(referencia)<512:return audio.astype(np.int16)
    n=512;hop=256;window=np.hanning(n);freq=np.fft.rfftfreq(n,1/rate)
    noise=np.mean([np.abs(np.fft.rfft(referencia[i:i+n]*window))**2 for i in range(0,len(referencia)-n+1,hop)],axis=0)
    padded=np.pad(audio,(n,n));out=np.zeros_like(padded);weight=np.zeros_like(padded)
    for i in range(0,len(padded)-n+1,hop):
        z=np.fft.rfft(padded[i:i+n]*window);power=np.abs(z)**2
        gain=np.sqrt(np.maximum(.04,1-1.3*noise/np.maximum(power,1e-9)))
        gain[(freq<90)|(freq>7400)]=0
        out[i:i+n]+=np.fft.irfft(z*gain,n)*window;weight[i:i+n]+=window**2
    out=out[n:n+len(audio)]/np.maximum(weight[n:n+len(audio)],1e-9)
    return np.clip(out,-32768,32767).astype(np.int16)

def telefono_dictado(text):
    words={'cero':'0','uno':'1','un':'1','dos':'2','tres':'3','cuatro':'4','cinco':'5','seis':'6','siete':'7','ocho':'8','nueve':'9'}
    return ''.join(words.get(w,w if w.isdigit() else '') for w in re.findall(r'\w+',text.lower()))

class Captura(QThread):
    estado=Signal(str);texto=Signal(str);error=Signal(str)
    def __init__(self,filtro,parent=None):super().__init__(parent);self.filtro=filtro;self.parar=threading.Event()
    def run(self):
        try:
            import sounddevice as sd
            from vosk import Model,KaldiRecognizer,SetLogLevel
            self.estado.emit('Preparando reconocimiento local…')
            modelpath=Path(__file__).resolve().parent/'assets/vosk-es'
            if not modelpath.is_dir():raise RuntimeError('No se encuentra el modelo de voz. Reinstala esta actualización.')
            SetLogLevel(-1);model=Model(str(modelpath))
            if self.parar.is_set():return
            with sd.InputStream(samplerate=16000,channels=1,dtype='int16') as stream:
                self.estado.emit('Guarda silencio un segundo: midiendo el ruido ambiental…')
                ref=[]
                for _ in range(10):
                    if self.parar.is_set():return
                    chunk,overflow=stream.read(1600)
                    if overflow:raise RuntimeError('Se perdió audio. Cierra otras aplicaciones de sonido y vuelve a intentar.')
                    ref.append(chunk.reshape(-1).copy())
                self.estado.emit('HABLA AHORA. Hasta 8 segundos; puedes pulsar Detener.')
                chunks=[]
                for _ in range(80):
                    if self.parar.is_set():break
                    chunk,overflow=stream.read(1600)
                    if overflow:raise RuntimeError('Se perdió audio. Vuelve a intentar con menos aplicaciones abiertas.')
                    chunks.append(chunk.reshape(-1).copy())
            if not chunks:return
            self.estado.emit('Reconociendo la voz en esta Mac…')
            audio=np.concatenate(chunks)
            if self.filtro:audio=reducir_ruido(audio,np.concatenate(ref))
            rec=KaldiRecognizer(model,16000);parts=[]
            for i in range(0,len(audio),4000):
                if rec.AcceptWaveform(audio[i:i+4000].tobytes()):parts.append(json.loads(rec.Result()).get('text',''))
            parts.append(json.loads(rec.FinalResult()).get('text',''));result=' '.join(parts).strip()
            if not result:raise RuntimeError('No se entendió la voz. Acércate al micrófono y repite, o escribe los datos.')
            self.texto.emit(result)
        except Exception as e:
            message=str(e)
            if 'cannot load library' in message or 'No module named' in message:
                self.error.emit('Falta un componente del motor de voz en la aplicación. Reinstala la actualización corregida. Detalle: '+message)
            else:
                self.error.emit('No se pudo dictar: '+message+'\nSi el micrófono está bloqueado, revisa Ajustes del Sistema > Privacidad y seguridad > Micrófono.')

class AltaSocio(QDialog):
    def __init__(self,w):
        super().__init__(w);self.w=w;self.worker=None;self.setWindowTitle('Registrar socio · Voz o teclado');self.resize(620,370)
        box=QVBoxLayout(self);note=QLabel('Dicta el nombre y el teléfono por separado. Revisa y corrige antes de guardar. El audio se procesa en esta Mac y no se guarda ni se envía a Internet.');note.setWordWrap(True);box.addWidget(note)
        form=QFormLayout();self.nombre=QLineEdit();self.telefono=QLineEdit();self.mics=[]
        for title,field,kind in [('Nombre:',self.nombre,'nombre'),('Teléfono (opcional):',self.telefono,'telefono')]:
            row=QHBoxLayout();row.addWidget(field);b=QPushButton('Dictar');b.clicked.connect(lambda checked=False,k=kind:self.dictar(k));row.addWidget(b);form.addRow(title,row);self.mics.append(b)
        box.addLayout(form);self.filtro=QCheckBox('Reducir ruido ambiental constante');self.filtro.setChecked(True);box.addWidget(self.filtro)
        self.estado=QLabel('Para el teléfono, pronuncia cada dígito por separado. El filtro atenúa ruido; no separa perfectamente otras voces.');self.estado.setWordWrap(True);box.addWidget(self.estado)
        self.stop=QPushButton('Detener dictado');self.stop.setEnabled(False);self.stop.clicked.connect(self.detener);box.addWidget(self.stop)
        row=QHBoxLayout();self.save=QPushButton('Revisar y guardar socio');self.save.clicked.connect(self.guardar);row.addWidget(self.save);cancel=QPushButton('Cerrar');cancel.clicked.connect(self.reject);row.addWidget(cancel);box.addLayout(row)
    def dictar(self,kind):
        if self.worker and self.worker.isRunning():return
        self.worker=Captura(self.filtro.isChecked(),self)
        self.worker.estado.connect(self.estado.setText);self.worker.error.connect(self.estado.setText)
        def recibido(text):
            (self.nombre if kind=='nombre' else self.telefono).setText(text.title() if kind=='nombre' else telefono_dictado(text))
            self.estado.setText('Dictado terminado. Revisa lo escrito; puedes corregirlo o volver a dictar.')
        self.worker.texto.connect(recibido);self.worker.finished.connect(self.terminado)
        for b in self.mics:b.setEnabled(False)
        self.save.setEnabled(False);self.stop.setEnabled(True);self.worker.start()
    def detener(self):
        if self.worker:self.worker.parar.set();self.stop.setEnabled(False)
    def terminado(self):
        for b in self.mics:b.setEnabled(True)
        self.save.setEnabled(True);self.stop.setEnabled(False)
    def reject(self):
        if self.worker and self.worker.isRunning():self.detener();self.estado.setText('Terminando dictado… Pulsa Cerrar cuando termine.');return
        super().reject()
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():self.detener();event.ignore()
        else:event.accept()
    def guardar(self):
        name=self.nombre.text().strip();phone=self.telefono.text().strip()
        if not name:QMessageBox.warning(self,'Nombre requerido','Escribe o dicta el nombre del socio.');return
        duplicado=any(s['nombre'].strip().casefold()==name.casefold() for s in self.w.datos.socios())
        text='Nombre: '+name+'\nTeléfono: '+(phone or 'Sin teléfono')+('\n\nYa existe un socio con ese nombre. Revisa si es la misma persona.' if duplicado else '')+'\n\n¿Guardar este socio?'
        if QMessageBox.question(self,'Confirmar datos',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        self.save.setEnabled(False)
        try:self.w.datos.socio(name,phone);self.w.refrescar();self.accept()
        except Exception as e:self.save.setEnabled(True);QMessageBox.warning(self,'No se guardó',str(e))

def instalar(Ventana):
    def nuevo_socio(self):AltaSocio(self).exec()
    Ventana.nuevo_socio=nuevo_socio
