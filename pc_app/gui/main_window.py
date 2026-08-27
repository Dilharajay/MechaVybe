from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox,
                             QTabWidget, QFormLayout, QGroupBox, QTextEdit, QSpinBox,
                             QDoubleSpinBox, QCheckBox, QScrollArea)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QTransform, QIcon, QPixmap
import pyqtgraph as pg
import numpy as np
import time
import json
import os

from core.serial_manager import SerialManager
from core.data_logger import DataLogger
from core.plot_manager import PlotManager
from core.fft_manager import FftManager
from core.filter_manager import FilterManager

class ImuApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MECHAVYBE - Data Acquisition System")
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1000, 800)
        
        self.serial_mgr = SerialManager()
        self.logger = DataLogger()
        self.plot_mgr = PlotManager(max_points=500)
        self.fft_mgr = FftManager(size=1024)
        self.filter_mgr = FilterManager()
        
        self.setup_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        
        self.ping_timer = QTimer()
        self.ping_timer.timeout.connect(self.send_ping)
        
        self.start_time = time.time()
        self.record_stop_time = 0
        
        self.samples_received = 0
        self.dropped_samples = 0
        self.duplicate_samples = 0
        self.usb_disconnects = 0
        self.stream_start_seq = -1
        self.last_packet_id = -1
        self.was_connected = False
        
    def send_ping(self):
        self.serial_mgr.send_ping()
        
    def setup_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        def make_scrollable(widget):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            scroll.setStyleSheet('QScrollArea { border: none; }')
            return scroll

        # Main Tab Widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # --- TAB 1: Dashboard (Plotting, Configuration & Data Logger) ---
        dash_widget = QWidget()
        dash_layout = QHBoxLayout()  # Main layout is Side-by-Side
        dash_widget.setLayout(dash_layout)
        
        # --- LEFT COLUMN: Controls & Config ---
        left_col_widget = QWidget()
        left_col = QVBoxLayout()
        left_col_widget.setLayout(left_col)
        
        # 0. Logo
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        logo_pixmap = QPixmap(logo_path)
        if not logo_pixmap.isNull():
            # Scale logo width to fit the column width decently, preserving aspect ratio
            logo_pixmap = logo_pixmap.scaledToWidth(250, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            left_col.addWidget(logo_label)
        
        # 1. Connection Panel
        conn_group = QGroupBox("Connection & Logging")
        conn_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        for port in self.serial_mgr.get_ports():
            self.port_combo.addItem(port)
            
        conn_layout.addWidget(self.port_combo)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        conn_layout.addWidget(self.refresh_btn)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)
        
        self.rec_btn = QPushButton("Start Recording")
        self.rec_btn.clicked.connect(self.toggle_recording)
        conn_layout.addWidget(self.rec_btn)
        
        conn_group.setLayout(conn_layout)
        left_col.addWidget(conn_group)
        
        # 2. Dashboard Status Pane
        status_group = QGroupBox("Data Acquisition Status")
        status_layout = QHBoxLayout()
        
        col1 = QFormLayout()
        self.lbl_device = QLabel("ESP32-S3-01")
        self.lbl_sensor = QLabel("MPU6050")
        self.lbl_conn = QLabel("Disconnected")
        col1.addRow("Device:", self.lbl_device)
        col1.addRow("Sensor:", self.lbl_sensor)
        col1.addRow("Connection:", self.lbl_conn)
        
        col2 = QFormLayout()
        self.lbl_sampling = QLabel("50 Hz")
        self.lbl_received = QLabel("0")
        self.lbl_expected = QLabel("0")
        col2.addRow("Actual Rate:", self.lbl_sampling)
        col2.addRow("Received Samples:", self.lbl_received)
        col2.addRow("Expected Samples:", self.lbl_expected)
        
        col3 = QFormLayout()
        self.lbl_dropped = QLabel("0")
        self.lbl_duplicates = QLabel("0")
        self.lbl_integrity = QLabel("100.00%")
        self.lbl_disconnects = QLabel("0")
        col3.addRow("Dropped Samples:", self.lbl_dropped)
        col3.addRow("Duplicate/Reset:", self.lbl_duplicates)
        col3.addRow("Stream Integrity:", self.lbl_integrity)
        col3.addRow("USB Disconnects:", self.lbl_disconnects)
        
        status_layout.addLayout(col1)
        status_layout.addLayout(col2)
        status_layout.addLayout(col3)
        status_group.setLayout(status_layout)
        left_col.addWidget(status_group)
        
        # 3. Data Acquisition Parameters
        daq_group = QGroupBox("Data Acquisition Parameters")
        daq_form = QFormLayout()
        
        self.id_input = QLineEdit("ESP32-S3-01")
        self.id_btn = QPushButton("Set Device ID")
        self.id_btn.clicked.connect(lambda: self.send_cmd(f"SET:ID:{self.id_input.text().strip()}"))
        daq_form.addRow(self.id_input, self.id_btn)
        
        self.sensor_combo = QComboBox()
        self.sensor_combo.addItems(["MPU6050", "ADXL345 (I2C)"])
        self.sensor_btn = QPushButton("Set Sensor")
        self.sensor_btn.clicked.connect(lambda: self.send_cmd(f"SET:SENSOR:{self.sensor_combo.currentText().split(' ')[0]}"))
        daq_form.addRow(self.sensor_combo, self.sensor_btn)
        
        self.conn_combo = QComboBox()
        self.conn_combo.addItems(["USB (Serial)", "Wi-Fi UDP"])
        daq_form.addRow("Connection:", self.conn_combo)
        
        self.rate_combo = QComboBox()
        self.rate_combo.addItems(["10", "20", "50", "100", "200", "500", "1000", "2000", "4000"])
        self.rate_btn = QPushButton("Set Sampling Rate (Hz)")
        self.rate_btn.clicked.connect(lambda: self.send_cmd(f"SET:RATE:{self.rate_combo.currentText()}"))
        daq_form.addRow(self.rate_combo, self.rate_btn)
        
        self.accel_combo = QComboBox()
        self.accel_combo.addItems(["2", "4", "8", "16"])
        self.accel_btn = QPushButton("Set Accel Range (±g)")
        self.accel_btn.clicked.connect(lambda: self.send_cmd(f"SET:ACCEL:{self.accel_combo.currentText()}"))
        daq_form.addRow(self.accel_combo, self.accel_btn)
        
        self.gyro_combo = QComboBox()
        self.gyro_combo.addItems(["250", "500", "1000", "2000"])
        self.gyro_btn = QPushButton("Set Gyro Range (±deg/s)")
        self.gyro_btn.clicked.connect(lambda: self.send_cmd(f"SET:GYRO:{self.gyro_combo.currentText()}"))
        daq_form.addRow(self.gyro_combo, self.gyro_btn)
        
        self.chan_combo = QComboBox()
        self.chan_combo.addItems(["6 (Accel + Gyro)", "3 (Accel Only)"])
        daq_form.addRow("Number of channels:", self.chan_combo)
        
        self.time_combo = QComboBox()
        self.time_combo.addItems(["Device (ESP32 microsecond clock)", "Host (PC time.time)"])
        daq_form.addRow("Timestamp source:", self.time_combo)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 3600)
        self.duration_spin.setSuffix(" seconds (0 = Infinite)")
        daq_form.addRow("Recording duration:", self.duration_spin)
        
        daq_group.setLayout(daq_form)
        left_col.addWidget(daq_group)
        
        # 4. Wi-Fi Configuration
        wifi_group = QGroupBox("Wi-Fi Configuration (NVS)")
        wifi_form = QFormLayout()
        self.ssid_input = QLineEdit()
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.send_wifi_btn = QPushButton("Apply Wi-Fi & Reboot")
        self.send_wifi_btn.clicked.connect(self.send_wifi_config)
        wifi_form.addRow("SSID:", self.ssid_input)
        wifi_form.addRow("Password:", self.pwd_input)
        wifi_form.addRow("", self.send_wifi_btn)
        wifi_group.setLayout(wifi_form)
        left_col.addWidget(wifi_group)
        
        # 5. Recording Metadata
        meta_group = QGroupBox("Dataset & Recording Metadata")
        meta_layout = QVBoxLayout()
        
        prof_layout = QHBoxLayout()
        prof_layout.addWidget(QLabel("Metadata Profile:"))
        self.meta_profile_combo = QComboBox()
        self.meta_profile_combo.currentIndexChanged.connect(self.build_dynamic_metadata_ui)
        prof_layout.addWidget(self.meta_profile_combo)
        
        btn_reload_prof = QPushButton("Reload Profiles")
        btn_reload_prof.clicked.connect(self.load_metadata_profiles)
        prof_layout.addWidget(btn_reload_prof)
        meta_layout.addLayout(prof_layout)
        
        self.dynamic_meta_form = QFormLayout()
        meta_layout.addLayout(self.dynamic_meta_form)
        
        meta_group.setLayout(meta_layout)
        left_col.addWidget(meta_group)
        
        self.metadata_profiles = {}
        self.meta_widgets = {}
        
        left_col.addStretch()
        
        # Add left column to dash layout wrapped in scroll area
        dash_layout.addWidget(make_scrollable(left_col_widget), stretch=2)
        
        # --- RIGHT COLUMN: Plots ---
        right_col_widget = QWidget()
        right_col = QVBoxLayout()
        right_col_widget.setLayout(right_col)
        
        self.graph_widget = pg.GraphicsLayoutWidget()
        right_col.addWidget(self.graph_widget)
        self.accel_plot = self.graph_widget.addPlot(title="Accelerometer (m/s²)")
        self.accel_plot.addLegend()
        self.graph_widget.nextRow()
        self.gyro_plot = self.graph_widget.addPlot(title="Gyroscope (rad/s)")
        self.gyro_plot.addLegend()
        
        self.curves = {
            'ax': self.accel_plot.plot(pen='r', name="Acc X"), 'ay': self.accel_plot.plot(pen='g', name="Acc Y"), 'az': self.accel_plot.plot(pen='b', name="Acc Z"),
            'gx': self.gyro_plot.plot(pen='r', name="Gyro X"), 'gy': self.gyro_plot.plot(pen='g', name="Gyro Y"), 'gz': self.gyro_plot.plot(pen='b', name="Gyro Z")
        }
        
        # Add right column to dash layout
        dash_layout.addWidget(right_col_widget, stretch=5)
        
        self.tabs.addTab(dash_widget, "Dashboard")
        
        # --- TAB 3: Diagnostics & Calibration ---
        diag_widget = QWidget()
        diag_layout = QVBoxLayout()
        diag_widget.setLayout(diag_layout)
        
        # Manual Calibration Panel
        man_cal_group = QGroupBox("Accelerometer Calibration")
        man_cal_layout = QFormLayout()
        
        self.cal_ox = QLineEdit("0.0")
        self.cal_oy = QLineEdit("0.0")
        self.cal_oz = QLineEdit("0.0")
        man_cal_layout.addRow("X Offset (m/s²):", self.cal_ox)
        man_cal_layout.addRow("Y Offset (m/s²):", self.cal_oy)
        man_cal_layout.addRow("Z Offset (m/s²):", self.cal_oz)
        
        self.cal_sx = QLineEdit("1.0")
        self.cal_sy = QLineEdit("1.0")
        self.cal_sz = QLineEdit("1.0")
        man_cal_layout.addRow("Scale X:", self.cal_sx)
        man_cal_layout.addRow("Scale Y:", self.cal_sy)
        man_cal_layout.addRow("Scale Z:", self.cal_sz)
        
        cal_btn_layout = QHBoxLayout()
        self.apply_cal_btn = QPushButton("Apply to Device")
        self.apply_cal_btn.clicked.connect(self.apply_calibration)
        self.save_cal_btn = QPushButton("Save Profile")
        self.save_cal_btn.clicked.connect(self.save_calibration_profile)
        self.load_cal_btn = QPushButton("Load Profile")
        self.load_cal_btn.clicked.connect(self.load_calibration_profile)
        
        cal_btn_layout.addWidget(self.apply_cal_btn)
        cal_btn_layout.addWidget(self.save_cal_btn)
        cal_btn_layout.addWidget(self.load_cal_btn)
        man_cal_layout.addRow(cal_btn_layout)
        
        man_cal_group.setLayout(man_cal_layout)
        diag_layout.addWidget(man_cal_group)
        
        # Auto-Calibration
        calib_btn = QPushButton("Run Auto Zero-Offset Calibration (Keep level and still!)")
        calib_btn.clicked.connect(lambda: self.send_cmd("CMD:CALIBRATE"))
        calib_btn.setStyleSheet("background-color: orange; font-weight: bold; padding: 10px;")
        diag_layout.addWidget(calib_btn)

        # Diagnostics
        self.get_info_btn = QPushButton("Fetch Device Info")
        self.get_info_btn.clicked.connect(lambda: self.send_cmd("GET:INFO"))
        diag_layout.addWidget(self.get_info_btn)
        
        self.info_display = QTextEdit()
        self.info_display.setReadOnly(True)
        diag_layout.addWidget(self.info_display)
        
        self.tabs.addTab(make_scrollable(diag_widget), "Diagnostics & Calibration")
        
        # --- TAB 4: Frequency Analysis (FFT) ---
        fft_widget = QWidget()
        fft_layout = QVBoxLayout()
        fft_widget.setLayout(fft_layout)
        
        # FFT Controls
        fft_ctrl_layout = QHBoxLayout()
        
        self.fft_size_combo = QComboBox()
        self.fft_size_combo.addItems(["256", "512", "1024", "2048", "4096"])
        self.fft_size_combo.setCurrentText("1024")
        self.fft_size_combo.currentTextChanged.connect(lambda t: self.fft_mgr.set_size(int(t)))
        
        self.fft_win_combo = QComboBox()
        self.fft_win_combo.addItems(["Hanning", "Hamming", "Blackman", "Rectangular"])
        
        self.fft_axis_combo = QComboBox()
        self.fft_axis_combo.addItems(["Z Axis", "X Axis", "Y Axis"])
        
        self.fft_mode_combo = QComboBox()
        self.fft_mode_combo.addItems(["Magnitude", "PSD"])
        
        fft_ctrl_layout.addWidget(QLabel("FFT Size:"))
        fft_ctrl_layout.addWidget(self.fft_size_combo)
        fft_ctrl_layout.addWidget(QLabel("Window:"))
        fft_ctrl_layout.addWidget(self.fft_win_combo)
        fft_ctrl_layout.addWidget(QLabel("Axis:"))
        fft_ctrl_layout.addWidget(self.fft_axis_combo)
        fft_ctrl_layout.addWidget(QLabel("Mode:"))
        fft_ctrl_layout.addWidget(self.fft_mode_combo)
        fft_ctrl_layout.addStretch()
        
        fft_layout.addLayout(fft_ctrl_layout)
        
        # FFT Plot
        self.fft_graph = pg.GraphicsLayoutWidget()
        fft_layout.addWidget(self.fft_graph)
        self.fft_plot = self.fft_graph.addPlot(title="Frequency Spectrum")
        self.fft_plot.setLabel('bottom', 'Frequency', units='Hz')
        self.fft_plot.setLabel('left', 'Amplitude')
        self.fft_curve = self.fft_plot.plot(pen='y')
        
        # FFT Metrics Panel
        fft_metrics_group = QGroupBox("Spectral Features")
        fft_metrics_layout = QHBoxLayout()
        
        col_f1 = QFormLayout()
        self.lbl_fft_res = QLabel("0 Hz")
        self.lbl_fft_dom = QLabel("0 Hz")
        self.lbl_fft_peak = QLabel("0.0")
        col_f1.addRow("Frequency resolution:", self.lbl_fft_res)
        col_f1.addRow("Dominant frequency:", self.lbl_fft_dom)
        col_f1.addRow("Peak amplitude:", self.lbl_fft_peak)
        
        col_f2 = QFormLayout()
        self.lbl_fft_h2 = QLabel("0 Hz")
        self.lbl_fft_h3 = QLabel("0 Hz")
        self.lbl_fft_cent = QLabel("0 Hz")
        self.lbl_fft_band = QLabel("0.0")
        col_f2.addRow("2nd harmonic:", self.lbl_fft_h2)
        col_f2.addRow("3rd harmonic:", self.lbl_fft_h3)
        col_f2.addRow("Spectral centroid:", self.lbl_fft_cent)
        col_f2.addRow("Band power:", self.lbl_fft_band)
        
        fft_metrics_layout.addLayout(col_f1)
        fft_metrics_layout.addLayout(col_f2)
        fft_metrics_group.setLayout(fft_metrics_layout)
        
        fft_layout.addWidget(fft_metrics_group)
        
        # Time-Domain Metrics Panel
        time_metrics_group = QGroupBox("Time-Domain Features (AC-Coupled)")
        time_metrics_layout = QHBoxLayout()
        
        col_t1 = QFormLayout()
        self.lbl_time_rms = QLabel("0.0000")
        self.lbl_time_peak = QLabel("0.0000")
        col_t1.addRow("RMS Vibration:", self.lbl_time_rms)
        col_t1.addRow("Peak Amplitude:", self.lbl_time_peak)
        
        col_t2 = QFormLayout()
        self.lbl_time_p2p = QLabel("0.0000")
        self.lbl_time_crest = QLabel("0.0000")
        col_t2.addRow("Peak-to-Peak:", self.lbl_time_p2p)
        col_t2.addRow("Crest Factor:", self.lbl_time_crest)
        
        time_metrics_layout.addLayout(col_t1)
        time_metrics_layout.addLayout(col_t2)
        time_metrics_group.setLayout(time_metrics_layout)
        
        fft_layout.addWidget(time_metrics_group)
        self.tabs.addTab(make_scrollable(fft_widget), "Frequency Analysis (FFT)")
        
        # --- TAB 5: Signal Processing (DSP) ---
        dsp_widget = QWidget()
        dsp_layout = QVBoxLayout()
        dsp_widget.setLayout(dsp_layout)
        
        dsp_group = QGroupBox("Digital Filter Configuration")
        dsp_form = QFormLayout()
        
        self.dsp_enable = QCheckBox("Enable DSP Filters (Applies to FFT and Time Metrics, RAW data logging remains unchanged)")
        self.dsp_enable.stateChanged.connect(self.update_dsp_settings)
        dsp_form.addRow(self.dsp_enable)
        
        self.dsp_type = QComboBox()
        self.dsp_type.addItems(["None", "Low-pass", "High-pass", "Band-pass", "Band-stop"])
        self.dsp_type.currentTextChanged.connect(self.update_dsp_settings)
        dsp_form.addRow("Filter Type:", self.dsp_type)
        
        self.dsp_order = QSpinBox()
        self.dsp_order.setRange(1, 10)
        self.dsp_order.setValue(4)
        self.dsp_order.valueChanged.connect(self.update_dsp_settings)
        dsp_form.addRow("Butterworth Order:", self.dsp_order)
        
        self.dsp_low = QDoubleSpinBox()
        self.dsp_low.setRange(0.1, 2000.0)
        self.dsp_low.setValue(10.0)
        self.dsp_low.valueChanged.connect(self.update_dsp_settings)
        dsp_form.addRow("Low Cutoff (Hz):", self.dsp_low)
        
        self.dsp_high = QDoubleSpinBox()
        self.dsp_high.setRange(0.1, 2000.0)
        self.dsp_high.setValue(500.0)
        self.dsp_high.valueChanged.connect(self.update_dsp_settings)
        dsp_form.addRow("High Cutoff (Hz):", self.dsp_high)
        
        # Additional features
        self.dsp_dc = QCheckBox("Remove DC Offset (Mean)")
        self.dsp_dc.stateChanged.connect(self.update_dsp_settings)
        dsp_form.addRow(self.dsp_dc)
        
        self.dsp_detrend = QCheckBox("Linear Detrending")
        self.dsp_detrend.stateChanged.connect(self.update_dsp_settings)
        dsp_form.addRow(self.dsp_detrend)
        
        notch_layout = QHBoxLayout()
        self.dsp_notch = QCheckBox("Enable Notch Filter")
        self.dsp_notch.stateChanged.connect(self.update_dsp_settings)
        self.dsp_notch_freq = QComboBox()
        self.dsp_notch_freq.addItems(["50.0", "60.0"])
        self.dsp_notch_freq.currentTextChanged.connect(self.update_dsp_settings)
        notch_layout.addWidget(self.dsp_notch)
        notch_layout.addWidget(self.dsp_notch_freq)
        notch_layout.addStretch()
        dsp_form.addRow("Mains Interference:", notch_layout)
        
        dsp_group.setLayout(dsp_form)
        dsp_layout.addWidget(dsp_group)
        
        aa_group = QGroupBox("Hardware Anti-Aliasing Status")
        aa_layout = QVBoxLayout()
        aa_layout.addWidget(QLabel("The ESP32 IMU Manager currently configures the hardware Digital Low Pass Filter (DLPF) to 21 Hz by default for stability."))
        aa_layout.addWidget(QLabel("Raw sensor data is sampled internally at up to 1-8 kHz, but signals above the DLPF threshold are hardware-attenuated before reaching the serial bus."))
        aa_group.setLayout(aa_layout)
        dsp_layout.addWidget(aa_group)
        
        dsp_layout.addStretch()
        self.tabs.addTab(make_scrollable(dsp_widget), "Signal Processing (DSP)")
        
        # --- TAB 6: Spectrogram ---
        spec_widget = QWidget()
        spec_layout = QVBoxLayout()
        spec_widget.setLayout(spec_layout)
        
        self.spec_plot = pg.PlotWidget(title="Live Spectrogram")
        self.spec_img = pg.ImageItem()
        self.spec_plot.addItem(self.spec_img)
        
        # Setup colormap (Heatmap)
        pos = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        color = np.array([[0,0,0,255], [0,0,255,255], [0,255,255,255], [255,255,0,255], [255,0,0,255]], dtype=np.uint8)
        cmap = pg.ColorMap(pos, color)
        self.spec_img.setLookupTable(cmap.getLookupTable())
        
        self.spec_plot.setLabel('bottom', 'Time Windows', units='steps')
        self.spec_plot.setLabel('left', 'Frequency', units='Hz')
        
        spec_layout.addWidget(self.spec_plot)
        self.tabs.addTab(make_scrollable(spec_widget), "Spectrogram")
        
        self.spec_history_size = 150
        self.spec_history = None
        
        # FFT Update Timer (updates at 10 Hz independent of serial)
        self.fft_timer = QTimer()
        self.fft_timer.timeout.connect(self.update_fft_plot)
        
        self.load_metadata_profiles()
        
    def load_metadata_profiles(self):
        self.metadata_profiles.clear()
        self.meta_profile_combo.blockSignals(True)
        self.meta_profile_combo.clear()
        
        profiles_dir = "metadata_profiles"
        os.makedirs(profiles_dir, exist_ok=True)
        
        # Load all JSONs
        for fname in os.listdir(profiles_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(profiles_dir, fname), 'r') as f:
                        data = json.load(f)
                        name = data.get("name", fname)
                        self.metadata_profiles[name] = data
                        self.meta_profile_combo.addItem(name)
                except Exception as e:
                    print(f"Error loading profile {fname}: {e}")
                    
        self.meta_profile_combo.blockSignals(False)
        
        # Default select the first or "Standard Industrial"
        idx = self.meta_profile_combo.findText("Standard Industrial")
        if idx >= 0:
            self.meta_profile_combo.setCurrentIndex(idx)
        elif self.meta_profile_combo.count() > 0:
            self.meta_profile_combo.setCurrentIndex(0)
            
        self.build_dynamic_metadata_ui()
        
    def build_dynamic_metadata_ui(self):
        # Clear existing layout
        while self.dynamic_meta_form.count():
            item = self.dynamic_meta_form.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        self.meta_widgets.clear()
        
        profile_name = self.meta_profile_combo.currentText()
        profile_data = self.metadata_profiles.get(profile_name, {})
        fields = profile_data.get("fields", [])
        
        for field in fields:
            field_id = field.get("id")
            f_type = field.get("type", "text")
            label = field.get("label", field_id)
            default = field.get("default", "")
            
            if f_type == "text":
                w = QLineEdit(str(default))
            elif f_type == "dropdown":
                w = QComboBox()
                w.addItems(field.get("options", []))
                idx = w.findText(str(default))
                if idx >= 0:
                    w.setCurrentIndex(idx)
            elif f_type == "number":
                w = QSpinBox()
                w.setRange(field.get("min", 0), field.get("max", 1000000))
                w.setValue(int(default) if str(default).isdigit() else 0)
                if "suffix" in field:
                    w.setSuffix(field["suffix"])
            else:
                w = QLineEdit(str(default))
                
            self.dynamic_meta_form.addRow(label + ":", w)
            self.meta_widgets[field_id] = w

    def refresh_ports(self):
        self.port_combo.clear()
        for port in self.serial_mgr.get_ports():
            self.port_combo.addItem(port)
            
    def toggle_connection(self):
        if self.serial_mgr.is_connected():
            self.timer.stop()
            self.ping_timer.stop()
            self.fft_timer.stop()
            self.serial_mgr.disconnect()
            self.connect_btn.setText("Connect")
            self.lbl_conn.setText("Disconnected")
        else:
            conn_type = self.conn_combo.currentText()
            if "UDP" in conn_type:
                port = "UDP"
            else:
                port = self.port_combo.currentText()
                
            if port:
                try:
                    self.serial_mgr.connect(port)
                    self.connect_btn.setText("Disconnect")
                    self.lbl_conn.setText(self.conn_combo.currentText())
                    self.start_time = time.time()
                    self.samples_received = 0
                    self.dropped_samples = 0
                    self.duplicate_samples = 0
                    self.stream_start_seq = -1
                    self.last_packet_id = -1
                    self.plot_mgr.clear()
                    self.fft_mgr.clear()
                    self.timer.start(10) # Run UI updates fast (10ms) to drain the serial buffer quickly
                    self.ping_timer.start(1000) # 1Hz ping
                    self.fft_timer.start(100) # 10Hz FFT
                    # Automatically fetch info on connect
                    QTimer.singleShot(1000, lambda: self.send_cmd("GET:INFO"))
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to connect: {str(e)}")

    def send_cmd(self, cmd):
        if self.serial_mgr.is_connected():
            self.serial_mgr.send_cmd(cmd)
        else:
            QMessageBox.warning(self, "Warning", "Please connect to the device first!")

    def send_wifi_config(self):
        ssid = self.ssid_input.text().strip()
        pwd = self.pwd_input.text().strip()
        if ssid:
            if self.serial_mgr.send_wifi_config(ssid, pwd):
                QMessageBox.information(self, "Sent", "Wi-Fi credentials sent. The ESP32 will process them and reboot.")
            else:
                QMessageBox.warning(self, "Warning", "Not connected!")

    def toggle_recording(self):
        if self.logger.is_recording:
            self.stop_recording_sequence()
        else:
            self.logger.start_recording()
            self.rec_btn.setText("Stop Recording")
            self.rec_btn.setStyleSheet("background-color: red; color: white; font-weight: bold;")
            
            duration = self.duration_spin.value()
            if duration > 0:
                self.record_stop_time = time.time() + duration
            else:
                self.record_stop_time = 0

    def stop_recording_sequence(self):
        self.logger.stop_recording()
        self.rec_btn.setText("Start Recording")
        self.rec_btn.setStyleSheet("")
        
        # Gather dynamic metadata for ML dataset organization
        metadata = {}
        for f_id, w in self.meta_widgets.items():
            if isinstance(w, QComboBox):
                metadata[f_id] = w.currentText()
            elif isinstance(w, QSpinBox):
                metadata[f_id] = w.value()
            elif isinstance(w, QLineEdit):
                metadata[f_id] = w.text().strip()
                
        # Ensure session_id exists
        if not metadata.get("session_id"):
            metadata["session_id"] = f"run_{int(time.time())}"
            
        # Add hardware parameters
        metadata["sensor_id"] = self.id_input.text().strip()
        metadata["sampling_rate"] = self.rate_combo.currentText()
        metadata["sensor_range"] = f"Accel: {self.accel_combo.currentText()}, Gyro: {self.gyro_combo.currentText()}"
        
        result = self.logger.save_parquet(metadata)
        if result:
            filename, count = result
            QMessageBox.information(self, "Saved", f"Saved {count} samples to {filename}")
            
    def apply_calibration(self):
        try:
            ox = float(self.cal_ox.text())
            oy = float(self.cal_oy.text())
            oz = float(self.cal_oz.text())
            sx = float(self.cal_sx.text())
            sy = float(self.cal_sy.text())
            sz = float(self.cal_sz.text())
            cmd = f"SET:CALIBA:{ox:.5f},{oy:.5f},{oz:.5f},{sx:.5f},{sy:.5f},{sz:.5f}"
            self.send_cmd(cmd)
        except ValueError:
            QMessageBox.critical(self, "Error", "Please enter valid numbers for calibration.")
            
    def save_calibration_profile(self):
        dev_id = self.id_input.text().strip()
        if not dev_id:
            QMessageBox.warning(self, "Warning", "Device ID is missing! Cannot save profile.")
            return
            
        profile = {
            "device_id": dev_id,
            "calib_ax": self.cal_ox.text(),
            "calib_ay": self.cal_oy.text(),
            "calib_az": self.cal_oz.text(),
            "scale_ax": self.cal_sx.text(),
            "scale_ay": self.cal_sy.text(),
            "scale_az": self.cal_sz.text()
        }
        
        os.makedirs("data", exist_ok=True)
        filename = f"data/calibration_{dev_id}.json"
        with open(filename, 'w') as f:
            json.dump(profile, f, indent=4)
        QMessageBox.information(self, "Saved", f"Calibration profile saved to {filename}")
        
    def load_calibration_profile(self):
        dev_id = self.id_input.text().strip()
        if not dev_id:
            QMessageBox.warning(self, "Warning", "Device ID is missing! Cannot load profile.")
            return
            
        filename = f"data/calibration_{dev_id}.json"
        if not os.path.exists(filename):
            QMessageBox.warning(self, "Warning", f"No profile found for {dev_id} at {filename}")
            return
            
        with open(filename, 'r') as f:
            profile = json.load(f)
            self.cal_ox.setText(profile.get("calib_ax", "0.0"))
            self.cal_oy.setText(profile.get("calib_ay", "0.0"))
            self.cal_oz.setText(profile.get("calib_az", "0.0"))
            self.cal_sx.setText(profile.get("scale_ax", "1.0"))
            self.cal_sy.setText(profile.get("scale_ay", "1.0"))
            self.cal_sz.setText(profile.get("scale_az", "1.0"))
        QMessageBox.information(self, "Loaded", f"Loaded profile for {dev_id}. Click 'Apply' to send to device.")

    def update_data(self):
        # Auto-stop recording if duration met
        if self.logger.is_recording and self.record_stop_time > 0:
            if time.time() >= self.record_stop_time:
                self.stop_recording_sequence()
                
        events = self.serial_mgr.read_events()
        for evt_type, evt_data in events:
            if evt_type == "IMU":
                try:
                    pkt_id, dev_ts_us, ax, ay, az, gx, gy, gz, rpm, voltage, current = evt_data
                    
                    if self.stream_start_seq == -1:
                        self.stream_start_seq = pkt_id
                        self.last_packet_id = pkt_id - 1
                        
                    # Tracking stream integrity
                    if pkt_id > self.last_packet_id + 1:
                        # Dropped samples detected
                        if pkt_id - self.last_packet_id > 10000:
                            # Massive jump: assume ESP32 rebooted or stream reset
                            self.stream_start_seq = pkt_id
                            self.samples_received = 0
                            self.dropped_samples = 0
                            self.duplicate_samples = 0
                        else:
                            self.dropped_samples += (pkt_id - self.last_packet_id - 1)
                    elif pkt_id <= self.last_packet_id:
                        self.duplicate_samples += 1
                        
                    self.last_packet_id = max(self.last_packet_id, pkt_id)
                    self.samples_received += 1
                    
                    # Update monitoring UI occasionally (every 50 samples)
                    if self.samples_received % 50 == 0:
                        self.lbl_rpm.setText(f"{rpm:.1f}" if rpm >= 0 else "N/A")
                        self.lbl_voltage.setText(f"{voltage:.2f} V" if voltage >= 0 else "N/A")
                        self.lbl_current.setText(f"{current:.2f} A" if current >= 0 else "N/A")
                    
                    # Timestamps
                    t_dev = dev_ts_us / 1_000_000.0
                    if self.time_combo.currentIndex() == 0:
                        t = t_dev
                    else:
                        # Use device time spacing but anchor it to PC time to avoid batching steps
                        if not hasattr(self, 'pc_time_offset') or self.samples_received <= 1:
                            self.pc_time_offset = (time.time() - self.start_time) - t_dev
                        t = t_dev + self.pc_time_offset
                        
                    # Graph only needs to update occasionally, but we log every point
                    self.plot_mgr.add_data(t, ax, ay, az, gx, gy, gz)
                    self.fft_mgr.add_data(ax, ay, az)
                    self.logger.add_sample(pkt_id, t, ax, ay, az, gx, gy, gz, rpm, voltage, current)
                except ValueError:
                    pass
                except Exception as e:
                    import traceback
                    traceback.print_exc()
            elif evt_type == "TEXT":
                line = evt_data
                if line.startswith("INFO:"):
                    try:
                        data = json.loads(line[5:])
                        formatted = json.dumps(data, indent=4)
                        self.info_display.setText(formatted)
                        
                        dev_id = data.get("id", "")
                        self.id_input.setText(dev_id)
                        self.lbl_device.setText(dev_id)
                        
                        sensor_val = data.get("sensor", "MPU6050")
                        for i in range(self.sensor_combo.count()):
                            if self.sensor_combo.itemText(i).startswith(sensor_val):
                                self.sensor_combo.setCurrentIndex(i)
                                break
                        self.lbl_sensor.setText(sensor_val)
                        
                        rate = str(data.get("rate", "50"))
                        idx = self.rate_combo.findText(rate)
                        if idx >= 0: self.rate_combo.setCurrentIndex(idx)
                        self.lbl_sampling.setText(f"{rate} Hz")
                        
                        accel = str(data.get("accel", "8"))
                        idx = self.accel_combo.findText(accel)
                        if idx >= 0: self.accel_combo.setCurrentIndex(idx)
                        
                        gyro = str(data.get("gyro", "500"))
                        idx = self.gyro_combo.findText(gyro)
                        if idx >= 0: self.gyro_combo.setCurrentIndex(idx)
                        
                        self.cal_ox.setText(str(data.get("calib_ax", 0.0)))
                        self.cal_oy.setText(str(data.get("calib_ay", 0.0)))
                        self.cal_oz.setText(str(data.get("calib_az", 0.0)))
                        self.cal_sx.setText(str(data.get("scale_ax", 1.0)))
                        self.cal_sy.setText(str(data.get("scale_ay", 1.0)))
                        self.cal_sz.setText(str(data.get("scale_az", 1.0)))
                    except Exception as e:
                        self.info_display.setText(f"Error parsing INFO: {str(e)}\nRaw: {line}")
        
        # Update Dashboard metrics
        expected = self.last_packet_id - self.stream_start_seq + 1 if self.stream_start_seq != -1 else 0
        expected = max(self.samples_received, expected) # Sanity check
        
        integrity = 100.0
        if expected > 0:
            integrity = (self.samples_received / expected) * 100.0
            
        self.lbl_expected.setText(f"{expected:,}")
        self.lbl_received.setText(f"{self.samples_received:,}")
        self.lbl_integrity.setText(f"{integrity:.2f}%")
        
        self.lbl_dropped.setText(f"{self.dropped_samples:,}")
        self.lbl_duplicates.setText(f"{self.duplicate_samples:,}")
        
        # Track disconnects
        current_connected = self.serial_mgr.is_connected()
        if self.was_connected and not current_connected:
            self.usb_disconnects += 1
        self.was_connected = current_connected
        self.lbl_disconnects.setText(f"{self.usb_disconnects:,}")
        
        fs = float(self.rate_combo.currentText()) if self.rate_combo.currentText() else 1000.0
        self.plot_mgr.update_curves(self.curves, filter_mgr=self.filter_mgr, fs=fs)

    def update_fft_plot(self):
        if not self.serial_mgr.is_connected() or not self.fft_mgr.is_full:
            return
            
        fs = float(self.rate_combo.currentText())
        axis_idx = self.fft_axis_combo.currentIndex()
        axis = 'z' if axis_idx == 0 else 'x' if axis_idx == 1 else 'y'
        
        window = self.fft_win_combo.currentText()
        mode = self.fft_mode_combo.currentText()
        
        xf, yf, metrics = self.fft_mgr.compute_fft(axis=axis, fs=fs, window_type=window, mode=mode, filter_mgr=self.filter_mgr)
        
        if xf is not None and len(xf) > 0:
            self.fft_curve.setData(xf, yf)
            
            if metrics:
                self.lbl_fft_res.setText(f"{metrics.get('resolution', 0):.2f} Hz")
                self.lbl_fft_dom.setText(f"{metrics.get('peak_freq', 0):.2f} Hz")
                self.lbl_fft_peak.setText(f"{metrics.get('peak_amp', 0):.4f}")
                self.lbl_fft_h2.setText(f"{metrics.get('harm_2', 0):.2f} Hz")
                self.lbl_fft_h3.setText(f"{metrics.get('harm_3', 0):.2f} Hz")
                self.lbl_fft_cent.setText(f"{metrics.get('centroid', 0):.2f} Hz")
                self.lbl_fft_band.setText(f"{metrics.get('band_power', 0):.4f}")
                
            # Spectrogram Update
            if self.spec_history is None or self.spec_history.shape[1] != len(yf):
                self.spec_history = np.zeros((self.spec_history_size, len(yf)))
                
            # Roll history backward (oldest data falls off the front, new data added to the end)
            self.spec_history = np.roll(self.spec_history, -1, axis=0)
            self.spec_history[-1, :] = yf
            
            self.spec_img.setImage(self.spec_history, autoLevels=False)
            
            # Auto-scale intensity for visibility
            max_val = np.max(self.spec_history)
            if max_val > 0:
                self.spec_img.setLevels([0, max_val])
                
            # Scale the image axes so Y matches Frequency
            self.spec_img.resetTransform()
            df = xf[1] - xf[0] if len(xf) > 1 else 1.0
            
            # Use QTransform for PyQt6 compatibility instead of scale(x, y)
            tr = QTransform()
            tr.scale(1.0, float(df))  # Must cast to float, numpy.float64 crashes some Qt bindings
            self.spec_img.setTransform(tr)

        time_metrics = self.fft_mgr.compute_time_metrics(axis=axis, fs=fs, filter_mgr=self.filter_mgr)
        if time_metrics:
            self.lbl_time_rms.setText(f"{time_metrics.get('rms', 0):.4f}")
            self.lbl_time_peak.setText(f"{time_metrics.get('peak', 0):.4f}")
            self.lbl_time_p2p.setText(f"{time_metrics.get('p2p', 0):.4f}")
            self.lbl_time_crest.setText(f"{time_metrics.get('crest', 0):.4f}")

    def update_dsp_settings(self):
        self.filter_mgr.enabled = self.dsp_enable.isChecked()
        self.filter_mgr.filter_type = self.dsp_type.currentText()
        self.filter_mgr.order = self.dsp_order.value()
        self.filter_mgr.low_cutoff = self.dsp_low.value()
        self.filter_mgr.high_cutoff = self.dsp_high.value()
        self.filter_mgr.dc_removal = self.dsp_dc.isChecked()
        self.filter_mgr.detrend = self.dsp_detrend.isChecked()
        self.filter_mgr.notch_enabled = self.dsp_notch.isChecked()
        self.filter_mgr.notch_freq = float(self.dsp_notch_freq.currentText())
