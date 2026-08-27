import collections

class PlotManager:
    def __init__(self, max_points=500):
        self.max_points = max_points
        self.timestamps = collections.deque(maxlen=max_points)
        self.accel_data = {'x': collections.deque(maxlen=max_points), 'y': collections.deque(maxlen=max_points), 'z': collections.deque(maxlen=max_points)}
        self.gyro_data = {'x': collections.deque(maxlen=max_points), 'y': collections.deque(maxlen=max_points), 'z': collections.deque(maxlen=max_points)}

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

    def update_curves(self, curves, filter_mgr=None, fs=1000.0):
        if len(self.timestamps) > 0:
            # Convert deques to numpy arrays for plotting
            import numpy as np
            ts_arr = np.array(self.timestamps)
            if filter_mgr and filter_mgr.enabled:
                ax = filter_mgr.apply(np.array(self.accel_data['x']), fs)
                ay = filter_mgr.apply(np.array(self.accel_data['y']), fs)
                az = filter_mgr.apply(np.array(self.accel_data['z']), fs)
                gx = filter_mgr.apply(np.array(self.gyro_data['x']), fs)
                gy = filter_mgr.apply(np.array(self.gyro_data['y']), fs)
                gz = filter_mgr.apply(np.array(self.gyro_data['z']), fs)
            else:
                ax = np.array(self.accel_data['x'])
                ay = np.array(self.accel_data['y'])
                az = np.array(self.accel_data['z'])
                gx = np.array(self.gyro_data['x'])
                gy = np.array(self.gyro_data['y'])
                gz = np.array(self.gyro_data['z'])

            curves['ax'].setData(ts_arr, ax)
            curves['ay'].setData(ts_arr, ay)
            curves['az'].setData(ts_arr, az)
            curves['gx'].setData(ts_arr, gx)
            curves['gy'].setData(ts_arr, gy)
            curves['gz'].setData(ts_arr, gz)
