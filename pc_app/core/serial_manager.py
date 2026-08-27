import serial
import serial.tools.list_ports
import struct
import time

class SerialManager:
    def __init__(self):
        self.port = None
        self.byte_buffer = bytearray()

    @staticmethod
    def get_ports():
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect(self, port_name, baud_rate=921600):
        self.port = serial.Serial(port_name, baud_rate, timeout=0.01)
        self.port.reset_input_buffer()
        self.byte_buffer = bytearray()

    def disconnect(self):
        if self.port and self.port.is_open:
            self.port.close()
            self.port = None
        self.byte_buffer = bytearray()

    def is_connected(self):
        return self.port is not None and self.port.is_open

    def send_wifi_config(self, ssid, pwd):
        if self.is_connected():
            command = f"WIFI:{ssid}:{pwd}\n"
            self.port.write(command.encode('utf-8'))
            return True
        return False

    def send_mode(self, mode_idx):
        if self.is_connected():
            command = f"MODE:{mode_idx}\n"
            self.port.write(command.encode('utf-8'))
            return True
        return False

    def send_ping(self):
        if self.is_connected():
            self.port.write(b"PING\n")
            return True
        return False

    def read_events(self):
        events = []
        if self.is_connected():
            try:
                if self.port.in_waiting:
                    self.byte_buffer.extend(self.port.read(self.port.in_waiting))
                
                while len(self.byte_buffer) > 0:
                    if len(self.byte_buffer) >= 2 and self.byte_buffer[0] == 0xAA and self.byte_buffer[1] == 0xBB:
                        # Might be binary packet
                        if len(self.byte_buffer) >= 23:
                            header, seq, ts_us, rpm, voltage, current, count = struct.unpack('<HIIfffB', self.byte_buffer[:23])
                            packet_len = 23 + (count * 24) + 2
                            if len(self.byte_buffer) >= packet_len:
                                # Extract packet
                                samples_data = self.byte_buffer[23:23+(count*24)]
                                crc = struct.unpack('<H', self.byte_buffer[23+(count*24):packet_len])[0]
                                
                                # Validate CRC (Simple XOR of bytes before CRC)
                                calc_crc = 0
                                for b in self.byte_buffer[:packet_len-2]:
                                    calc_crc ^= b
                                    
                                if crc == calc_crc:
                                    # Causal timestamp interpolation mapping gap size to sequence drops
                                    if getattr(self, 'last_batch_ts', None) is None:
                                        self.last_batch_ts = ts_us - int(count * 1000) # Guess 1000Hz
                                        self.last_batch_seq = seq - count
                                        
                                    seq_delta = seq - getattr(self, 'last_batch_seq', seq - count)
                                    if seq_delta <= 0:
                                        seq_delta = count # Fallback for sequence reset/duplicates
                                        
                                    batch_duration = ts_us - self.last_batch_ts
                                    if batch_duration <= 0 or batch_duration > 5_000_000:
                                        sample_interval = 500 # Fallback 2kHz
                                    else:
                                        sample_interval = batch_duration / seq_delta
                                        
                                    self.last_batch_ts = ts_us
                                    self.last_batch_seq = seq
                                    
                                    # Extract samples
                                    sample_fmt = f'<{count*6}f'
                                    unpacked = struct.unpack(sample_fmt, samples_data)
                                    
                                    for i in range(count):
                                        ax, ay, az, gx, gy, gz = unpacked[i*6:(i+1)*6]
                                        interp_ts = ts_us + int(i * sample_interval)
                                        events.append(("IMU", (seq + i, interp_ts, ax, ay, az, gx, gy, gz, rpm, voltage, current)))
                                else:
                                    print("CRC Mismatch in binary packet!")
                                    
                                self.byte_buffer = self.byte_buffer[packet_len:]
                            else:
                                break # Wait for more binary data
                        else:
                            break # Wait for 23 bytes
                            
                    else:
                        # Try parsing as text
                        try:
                            newline_idx = self.byte_buffer.index(b'\n')
                            line = self.byte_buffer[:newline_idx].decode('utf-8', errors='ignore').strip()
                            if line:
                                events.append(("TEXT", line))
                            self.byte_buffer = self.byte_buffer[newline_idx+1:]
                        except ValueError:
                            if len(self.byte_buffer) > 2048:
                                self.byte_buffer.pop(0) # Drop a byte to resync
                            break
            except Exception as e:
                pass
        return events
