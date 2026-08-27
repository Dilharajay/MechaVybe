class PlotManager:
    def __init__(self, max_points=500):
        self.max_points = max_points
        self.timestamps = []
        self.accel_data = {'x': [], 'y': [], 'z': []}
        self.gyro_data = {'x': [], 'y': [], 'z': []}

    def clear(self):
        self.timestamps.clear()
        for k in self.accel_data: self.accel_data[k].clear()
        for k in self.gyro_data: self.gyro_data[k].clear()

    def add_data(self, timestamp, ax, ay, az, gx, gy, gz):
        self.timestamps.append(timestamp)
        self.accel_data['x'].append(ax)
        self.accel_data['y'].append(ay)
        self.accel_data['z'].append(az)
        self.gyro_data['x'].append(gx)
        self.gyro_data['y'].append(gy)
        self.gyro_data['z'].append(gz)
        
        if len(self.timestamps) > self.max_points:
            self.timestamps.pop(0)
            for k in self.accel_data: self.accel_data[k].pop(0)
            for k in self.gyro_data: self.gyro_data[k].pop(0)

    def update_curves(self, curves, filter_mgr=None, fs=1000.0):
        if len(self.timestamps) > 0:
            if filter_mgr and filter_mgr.enabled:
                import numpy as np
                ax = filter_mgr.apply(np.array(self.accel_data['x']), fs)
                ay = filter_mgr.apply(np.array(self.accel_data['y']), fs)
                az = filter_mgr.apply(np.array(self.accel_data['z']), fs)
                gx = filter_mgr.apply(np.array(self.gyro_data['x']), fs)
                gy = filter_mgr.apply(np.array(self.gyro_data['y']), fs)
                gz = filter_mgr.apply(np.array(self.gyro_data['z']), fs)
            else:
                ax = self.accel_data['x']
                ay = self.accel_data['y']
                az = self.accel_data['z']
                gx = self.gyro_data['x']
                gy = self.gyro_data['y']
                gz = self.gyro_data['z']

            curves['ax'].setData(self.timestamps, ax)
            curves['ay'].setData(self.timestamps, ay)
            curves['az'].setData(self.timestamps, az)
            curves['gx'].setData(self.timestamps, gx)
            curves['gy'].setData(self.timestamps, gy)
            curves['gz'].setData(self.timestamps, gz)
