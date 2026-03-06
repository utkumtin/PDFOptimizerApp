1. Proje Dizin Yapısı

Geliştirme sürecini düzenli tutmak ve py2app ile paketleme aşamasında sorun yaşamamak için aşağıdaki modüler yapıyı kurmanız önerilir:

pdf_optimizer_mac/
├── main.py                 # Uygulamanın giriş noktası (Entry point)
├── core/
│   ├── init.py
│   ├── engine.py           # Ghostscript komutlarını hazırlayan ve çalıştıran motor
│   └── gs_detector.py      # macOS üzerinde gs binary'sini bulan modül
├── ui/
│   ├── init.py
│   ├── main_window.py      # PySide6 ana pencere ve sürükle-bırak (Drag&Drop) mantığı
│   └── components.py       # Kalite slider'ı, özel butonlar ve ilerleme çubuğu
├── resources/
│   ├── icon.icns           # macOS uygulama ikonu
│   └── style.qss           # Apple estetiği için arayüz stil dosyası
├── requirements.txt
└── setup.py                # py2app paketleme yapılandırması
2. Ghostscript Yol Tespiti (GS Detector)

Modern macOS sürümlerinde (SIP aktifken) ctypes.util.find_library komutu genellikle başarısız olur. Bu nedenle motorun manuel olarak yolları taraması gerekir.
Python

# core/gs_detector.py
import os

def find_ghostscript():
    """Apple Silicon ve Intel Mac'ler için varsayılan Homebrew yollarını tarar."""
    possible_paths =
        "/usr/local/bin/gs",     # Intel Mac
        "/opt/local/bin/gs"      # MacPorts
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
            
    return None # Bulunamazsa UI tarafında "brew install ghostscript" uyarısı gösterilecek

3. Asenkron İşlem Motoru (QProcess Mimarisi)

Arayüzün donmasını engellemek için subprocess yerine PySide6'nın QProcess sınıfı kullanılmalıdır. İlerlemeyi (progress) okumak ve süreci iptal etmek bu sayede çok daha güvenli olur.
Python

# core/engine.py
from PySide6.QtCore import QObject, QProcess, Signal
import re

class GhostscriptWorker(QObject):
    progress_updated = Signal(int)
    process_finished = Signal(int, str) # exit_code, output_message
    
    def __init__(self, gs_path):
        super().__init__()
        self.gs_path = gs_path
        self.process = QProcess()
        
        # Standart hata ve çıktıyı birleştirerek okuma [3]
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.finished.connect(self.handle_finished)
        
    def start_optimization(self, input_pdf, output_pdf, quality_preset="/ebook", grayscale=False, clean_meta=False):
        args =
        
        if grayscale:
            args.extend()
            
        args.extend([f"-sOutputFile={output_pdf}", input_pdf])
        
        # Eğer metadata silinecekse, pdfmark.txt dosyası oluşturulup args sonuna eklenmeli
        self.process.start(self.gs_path, args)
        
    def handle_stdout(self):
        """Çıktıları UTF-8 olarak okuyup ilerlemeyi ayrıştırır."""
        data = self.process.readAllStandardOutput()
        output = bytes(data).decode("utf8")
        
        # İsteğe bağlı: Ghostscript sayfa işleme çıktılarını (Page 1, Page 2 vb.) regex ile yakalayıp progress_updated sinyalini tetikleyebilirsiniz.
        page_match = re.search(r"Page (\d+)", output)
        if page_match:
            # İlerleme hesaplaması burada yapılabilir
            pass

    def stop_process(self):
        """Kullanıcı İptal butonuna bastığında süreci anında sonlandırır.[3]"""
        if self.process.state() == QProcess.Running:
            self.process.kill()
            
    def handle_finished(self, exit_code, exit_status):
        self.process_finished.emit(exit_code, "İşlem tamamlandı veya iptal edildi.")

4. Sürükle-Bırak (Drag & Drop) ve UI Kurulumu

PySide6 ana penceresinde dosya kabul etmek için setAcceptDrops aktif edilmelidir.
Python

# ui/main_window.py
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Optimizer")
        self.resize(600, 400)
        self.setAcceptDrops(True) # Sürükle-Bırak aktif
        
        # Apple estetiği için pencere arkaplanını saydam yapıp NSVisualEffectView (Vibrancy) eklenebilir.
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        layout = QVBoxLayout()
        self.drop_label = QLabel("PDF Dosyalarını Buraya Sürükleyin")
        self.drop_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.drop_label)
        
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # Sadece PDF dosyalarına izin ver
            urls = event.mimeData().urls()
            if all(url.toLocalFile().lower().endswith('.pdf') for url in urls):
                event.accept()
                self.drop_label.setText("Bırakın...")
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = [url.toLocalFile() for url in urls]
        self.drop_label.setText(f"{len(files)} dosya eklendi.")
        # Dosyalar buradan kuyruğa (Queue) aktarılacak

5. macOS İçin Uygulama Paketleme (py2app)

Uygulama bittiğinde kullanıcıların bir .app dosyası olarak çalıştırabilmesi için py2app kullanılır. setup.py dosyasına uygulamanın Info.plist ayarları (ikon ve sürüm bilgisi) tanımlanır.
Python

# setup.py
from setuptools import setup

APP = ['main.py']
DATA_FILES =)
]
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'resources/icon.icns',
    'plist': {
        'CFBundleName': 'PDF Optimizer',
        'CFBundleDisplayName': 'PDF Optimizer',
        'CFBundleGetInfoString': "Gelişmiş PDF Optimizasyon Aracı",
        'CFBundleIdentifier': "com.isim.pdfoptimizer",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHighResolutionCapable': True,
    },
    'packages':,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

Paketleme Komutu:
Terminalde python setup.py py2app -A (geliştirme/test için) veya doğrudan python setup.py py2app (dağıtım için) komutunu çalıştırarak dist/ klasörü içerisinde PDF Optimizer.app dosyanızı oluşturabilirsiniz.