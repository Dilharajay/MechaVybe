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

    def update_curves(self, curves):
        if len(self.timestamps) > 0:
            curves['ax'].setData(self.timestamps, self.accel_data['x'])
            curves['ay'].setData(self.timestamps, self.accel_data['y'])
            curves['az'].setData(self.timestamps, self.accel_data['z'])
            curves['gx'].setData(self.timestamps, self.gyro_data['x'])
            curves['gy'].setData(self.timestamps, self.gyro_data['y'])
            curves['gz'].setData(self.timestamps, self.gyro_data['z'])
