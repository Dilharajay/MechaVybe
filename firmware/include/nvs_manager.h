#pragma once
#include <Arduino.h>

class NvsManager {
public:
    void begin();
    
    String getWifiSsid();
    String getWifiPassword();
    void setWifiCredentials(const String& ssid, const String& password);

    String getDeviceId();
    void setDeviceId(const String& id);
    
    String getSensorType();
    void setSensorType(const String& type);

    int getSampleRate();
    void setSampleRate(int rate_hz);

    int getAccelRange(); // Returns 2, 4, 8, or 16
    void setAccelRange(int range);

    int getGyroRange(); // Returns 250, 500, 1000, or 2000
    void setGyroRange(int range);

    // Calibration Offsets (ax, ay, az, gx, gy, gz)
    void getCalibration(float& ax, float& ay, float& az, float& gx, float& gy, float& gz);
    void setCalibration(float ax, float ay, float az, float gx, float gy, float gz);
    
    // Accelerometer Scales
    void getAccelScale(float& sx, float& sy, float& sz);
    void setAccelScale(float sx, float sy, float sz);
};
