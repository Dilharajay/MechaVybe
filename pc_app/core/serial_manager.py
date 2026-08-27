import serial
import serial.tools.list_ports
import struct
import time
import socket

class SerialManager:
    def __init__(self):
        self.port = None
        self.udp_sock = None
        self.byte_buffer = bytearray()
        self.is_udp = False

    @staticmethod
    def get_ports():
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect(self, port_name, baud_rate=921600):
        self.disconnect()
        if port_name.startswith("UDP"):
            self.is_udp = True
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_sock.bind(('0.0.0.0', 4242)) # Listen for any ESP32 replying, but we broadcast to 4242
            self.udp_sock.settimeout(0.01)
            
            # Send START_STREAM broadcast
            self.udp_sock.sendto(b"START_STREAM", ('<broadcast>', 4242))
        else:
            self.is_udp = False
            self.port = serial.Serial(port_name, baud_rate, timeout=0.01)
            self.port.reset_input_buffer()
        self.byte_buffer = bytearray()

    def disconnect(self):
        if self.is_udp:
            if self.udp_sock:
                try:
                    self.udp_sock.sendto(b"STOP_STREAM", ('<broadcast>', 4242))
                    self.udp_sock.close()
                except:
                    pass
                self.udp_sock = None
        else:
            if self.port and self.port.is_open:
                self.port.close()
                self.port = None
        self.byte_buffer = bytearray()

    def is_connected(self):
        if self.is_udp:
            return self.udp_sock is not None
        return self.port is not None and self.port.is_open

    def _write_data(self, data):
        if self.is_udp and self.udp_sock:
            self.udp_sock.sendto(data, ('<broadcast>', 4242))
            return True
        elif not self.is_udp and self.is_connected():
            self.port.write(data)
            return True
        return False

    def send_wifi_config(self, ssid, pwd):
        command = f"WIFI:{ssid}:{pwd}\n"
        return self._write_data(command.encode('utf-8'))

    def send_mode(self, mode_idx):
        command = f"MODE:{mode_idx}\n"
        return self._write_data(command.encode('utf-8'))

    def send_ping(self):
        return self._write_data(b"PING\n")

    def send_cmd(self, cmd_str):
        if not cmd_str.endswith('\n'):
            cmd_str += '\n'
        return self._write_data(cmd_str.encode('utf-8'))

    def read_events(self):
        events = []
        if self.is_udp and self.udp_sock:
            try:
                while True:
                    data, addr = self.udp_sock.recvfrom(2048)
                    
                    if len(data) >= 2 and data[0] == 0xAA and data[1] == 0xBB:
                        if len(data) >= 23:
                            header, seq, ts_us, rpm, voltage, current, count = struct.unpack('<HIIfffB', data[:23])
                            packet_len = 23 + (count * 24) + 2
                            if len(data) >= packet_len:
                                samples_data = data[23:23+(count*24)]
                                crc = struct.unpack('<H', data[23+(count*24):packet_len])[0]
                                
                                calc_crc = 0
                                for b in data[:packet_len-2]:
                                    calc_crc ^= b
                                    
                                if crc == calc_crc:
                                    if getattr(self, 'last_batch_ts', None) is None:
                                        self.last_batch_ts = ts_us - int(count * 1000)
                                        self.last_batch_seq = seq - count
                                        
                                    seq_delta = seq - getattr(self, 'last_batch_seq', seq - count)
                                    if seq_delta <= 0:
                                        seq_delta = count
                                        
                                    batch_duration = ts_us - self.last_batch_ts
                                    if batch_duration <= 0 or batch_duration > 5_000_000:
                                        sample_interval = 500
                                    else:
                                        sample_interval = batch_duration / seq_delta
                                        
                                    self.last_batch_ts = ts_us
                                    self.last_batch_seq = seq
                                    
                                    sample_fmt = f'<{count*6}f'
                                    unpacked = struct.unpack(sample_fmt, samples_data)
                                    
                                    for i in range(count):
                                        ax, ay, az, gx, gy, gz = unpacked[i*6:(i+1)*6]
                                        interp_ts = ts_us + int(i * sample_interval)
                                        events.append(("IMU", (seq + i, interp_ts, ax, ay, az, gx, gy, gz, rpm, voltage, current)))
                    else:
                        try:
                            line = data.decode('utf-8', errors='ignore').strip()
                            if line:
                                events.append(("TEXT", line))
                        except:
                            pass
            except socket.timeout:
                pass
            except BlockingIOError:
                pass
            except Exception as e:
                print(f"UDP Error: {e}")
            return events

        if not self.is_udp and self.is_connected():
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
