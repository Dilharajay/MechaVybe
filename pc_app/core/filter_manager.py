import numpy as np
import scipy.signal as signal

class FilterManager:
    def __init__(self):
        self.enabled = False
        self.filter_type = 'None' # None, Low-pass, High-pass, Band-pass, Band-stop
        self.order = 4
        self.low_cutoff = 10.0
        self.high_cutoff = 500.0
        
        self.dc_removal = False
        self.detrend = False
        self.notch_enabled = False
        self.notch_freq = 50.0

    def apply(self, data, fs):
        if len(data) < 10:
            return data
            
        y = np.array(data, dtype=float)
        
        # 1. DC Removal (Mean subtraction)
        if self.dc_removal:
            y = y - np.mean(y)
            
        # 2. Detrending (Linear)
        if self.detrend:
            y = signal.detrend(y)
            
        # 3. Notch Filter (e.g., mains frequency removal)
        if self.notch_enabled:
            # Check if nyquist is respected
            if self.notch_freq < 0.5 * fs:
                b, a = signal.iirnotch(self.notch_freq, 30.0, fs)
                y = signal.filtfilt(b, a, y)
            
        # 4. Main Band/Pass/Stop Filter
        if self.enabled and self.filter_type != 'None':
            nyq = 0.5 * fs
            if nyq <= 0: return y
            
            # Constrain cutoffs to valid Nyquist ranges
            lc = max(0.1, min(self.low_cutoff, nyq - 0.1))
            hc = max(lc + 0.1, min(self.high_cutoff, nyq - 0.1))
            
            b, a = None, None
            try:
                if self.filter_type == 'Low-pass':
                    b, a = signal.butter(self.order, hc / nyq, btype='low')
                elif self.filter_type == 'High-pass':
                    b, a = signal.butter(self.order, lc / nyq, btype='high')
                elif self.filter_type == 'Band-pass':
                    b, a = signal.butter(self.order, [lc / nyq, hc / nyq], btype='band')
                elif self.filter_type == 'Band-stop':
                    b, a = signal.butter(self.order, [lc / nyq, hc / nyq], btype='bandstop')
                    
                if b is not None:
                    # Use filtfilt for zero phase distortion
                    padlen = min(3 * max(len(a), len(b)), len(y) - 1)
                    if padlen > 0:
                        y = signal.filtfilt(b, a, y, padlen=padlen)
            except Exception as e:
                # If filter becomes unstable, just return current state
                pass
                
        return y
