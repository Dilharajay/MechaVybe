import numpy as np
import scipy.signal

class FftManager:
    def __init__(self, size=1024):
        self.size = size
        self.buffer_x = np.zeros(size)
        self.buffer_y = np.zeros(size)
        self.buffer_z = np.zeros(size)
        self.ptr = 0
        self.is_full = False

    def set_size(self, size):
        if size != self.size:
            self.size = size
            self.buffer_x = np.zeros(size)
            self.buffer_y = np.zeros(size)
            self.buffer_z = np.zeros(size)
            self.ptr = 0
            self.is_full = False

    def clear(self):
        self.ptr = 0
        self.is_full = False

    def add_data(self, ax, ay, az):
        self.buffer_x[self.ptr] = ax
        self.buffer_y[self.ptr] = ay
        self.buffer_z[self.ptr] = az
        self.ptr += 1
        if self.ptr >= self.size:
            self.ptr = 0
            self.is_full = True

    def compute_fft(self, axis='z', fs=1000.0, window_type='Hanning', mode='Magnitude', filter_mgr=None):
        if not self.is_full and self.ptr == 0:
            return None, None, {}
            
        if self.is_full:
            data = np.concatenate((self.buffer_z[self.ptr:], self.buffer_z[:self.ptr])) if axis == 'z' else \
                   np.concatenate((self.buffer_y[self.ptr:], self.buffer_y[:self.ptr])) if axis == 'y' else \
                   np.concatenate((self.buffer_x[self.ptr:], self.buffer_x[:self.ptr]))
        else:
            data = self.buffer_z[:self.ptr] if axis == 'z' else \
                   self.buffer_y[:self.ptr] if axis == 'y' else \
                   self.buffer_x[:self.ptr]
                   
        N = len(data)
        if N < 2: return None, None, {}

        # Apply DSP Filters if provided
        if filter_mgr:
            data = filter_mgr.apply(data, fs)

        # Remove DC offset (Mean) - always good for FFT to avoid huge zero-bin
        data = data - np.mean(data)
        
        # Apply window
        if window_type == 'Hanning':
            window = np.hanning(N)
            amp_correction = 2.0
        elif window_type == 'Hamming':
            window = np.hamming(N)
            amp_correction = 1.85
        elif window_type == 'Blackman':
            window = np.blackman(N)
            amp_correction = 2.38
        else: # Rectangular
            window = np.ones(N)
            amp_correction = 1.0
            
        data_win = data * window
        
        # Compute FFT
        yf = np.fft.rfft(data_win)
        xf = np.fft.rfftfreq(N, 1.0 / fs)
        
        if mode == 'Magnitude':
            y_out = (2.0 / N) * np.abs(yf) * amp_correction
        else: # PSD (Power Spectral Density)
            f, Pxx = scipy.signal.welch(data, fs=fs, window=window_type.lower() if window_type != 'Rectangular' else 'boxcar', nperseg=N)
            xf = f
            y_out = Pxx
        
        # Metrics Calculation
        metrics = {}
        if len(y_out) > 1:
            peak_idx = np.argmax(y_out[1:]) + 1 # Ignore DC bin
            peak_freq = xf[peak_idx]
            peak_amp = y_out[peak_idx]
            
            harm_2 = 2 * peak_freq
            harm_3 = 3 * peak_freq
            
            spectral_centroid = np.sum(xf * y_out) / np.sum(y_out) if np.sum(y_out) > 0 else 0
            
            if mode == 'PSD':
                band_power = np.trapz(y_out, xf)
            else:
                band_power = np.sum(y_out**2)
            
            metrics = {
                'resolution': fs / N,
                'peak_freq': peak_freq,
                'peak_amp': peak_amp,
                'harm_2': harm_2,
                'harm_3': harm_3,
                'centroid': spectral_centroid,
                'band_power': band_power
            }

        return xf, y_out, metrics

    def compute_time_metrics(self, axis='z', fs=1000.0, filter_mgr=None):
        if not self.is_full and self.ptr == 0:
            return {}
            
        if self.is_full:
            data = np.concatenate((self.buffer_z[self.ptr:], self.buffer_z[:self.ptr])) if axis == 'z' else \
                   np.concatenate((self.buffer_y[self.ptr:], self.buffer_y[:self.ptr])) if axis == 'y' else \
                   np.concatenate((self.buffer_x[self.ptr:], self.buffer_x[:self.ptr]))
        else:
            data = self.buffer_z[:self.ptr] if axis == 'z' else \
                   self.buffer_y[:self.ptr] if axis == 'y' else \
                   self.buffer_x[:self.ptr]
                   
        if len(data) < 2:
            return {}
            
        # Apply DSP Filters if provided
        if filter_mgr:
            data = filter_mgr.apply(data, fs)
            
        # AC-couple the data (remove gravity / DC offset) for accurate vibration severity
        data_ac = data - np.mean(data)
        
        rms = np.sqrt(np.mean(data_ac**2))
        peak = np.max(np.abs(data_ac))
        p2p = np.max(data_ac) - np.min(data_ac)
        crest = peak / rms if rms > 0 else 0.0
        
        return {
            'rms': rms,
            'peak': peak,
            'p2p': p2p,
            'crest': crest
        }
