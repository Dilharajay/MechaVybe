import os
import pandas as pd
from datetime import datetime

class DataLogger:
    def __init__(self):
        self.is_recording = False
        self.recorded_data = []

    def start_recording(self):
        self.recorded_data = []
        self.is_recording = True

    def stop_recording(self):
        self.is_recording = False

    def add_sample(self, packet_id, timestamp, ax, ay, az, gx, gy, gz, rpm=None, voltage=None, current=None):
        if self.is_recording:
            row = {
                'packet_id': packet_id,
                'timestamp': timestamp,
                'accel_x': ax, 'accel_y': ay, 'accel_z': az,
                'gyro_x': gx, 'gyro_y': gy, 'gyro_z': gz
            }
            if rpm is not None and rpm >= 0: row['rpm'] = rpm
            if voltage is not None and voltage >= 0: row['voltage'] = voltage
            if current is not None and current >= 0: row['current'] = current
            self.recorded_data.append(row)

    def get_sample_count(self):
        return len(self.recorded_data)

    def save_parquet(self, metadata=None):
        if not self.recorded_data:
            return None
            
        df = pd.DataFrame(self.recorded_data)
        
        if metadata:
            machine = metadata.get("machine_id", "machine_001")
            condition = metadata.get("condition", "unknown")
            session = metadata.get("session_id", f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # dataset/machine_001/healthy/run_001/
            base_dir = os.path.join("dataset", machine, condition, session)
        else:
            base_dir = os.path.join("dataset", "uncategorized", f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
        os.makedirs(base_dir, exist_ok=True)
        
        # Save Parquet
        parquet_path = os.path.join(base_dir, "data.parquet")
        df.to_parquet(parquet_path, engine='pyarrow')
        
        # Save Metadata
        if metadata:
            import json
            json_path = os.path.join(base_dir, "metadata.json")
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=4)
                
        count = len(df)
        self.recorded_data.clear()
        return parquet_path, count
