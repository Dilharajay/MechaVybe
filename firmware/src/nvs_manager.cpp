#include "nvs_manager.h"
#include <Preferences.h>
#include "logger.h"

static Preferences prefs;
static const char* PREF_NAMESPACE = "esp32s3_app";

void NvsManager::begin() {
    prefs.begin(PREF_NAMESPACE, false);
    Logger::info("NVS Manager initialized.");
}

String NvsManager::getWifiSsid() {
    return prefs.getString("wifi_ssid", "");
}

String NvsManager::getWifiPassword() {
    return prefs.getString("wifi_pwd", "");
}

void NvsManager::setWifiCredentials(const String& ssid, const String& password) {
    prefs.putString("wifi_ssid", ssid);
    prefs.putString("wifi_pwd", password);
}

String NvsManager::getDeviceId() {
    return prefs.getString("device_id", "ESP32-IMU-01");
}

void NvsManager::setDeviceId(const String& id) {
    prefs.putString("device_id", id);
}

String NvsManager::getSensorType() {
    return prefs.getString("sensor", "MPU6050");
}

void NvsManager::setSensorType(const String& type) {
    prefs.putString("sensor", type);
}

int NvsManager::getSampleRate() {
    return prefs.getInt("sample_rate", 1000); // default 1000Hz
}

void NvsManager::setSampleRate(int rate_hz) {
    if (rate_hz < 1) rate_hz = 1;
    if (rate_hz > 4000) rate_hz = 4000;
    prefs.putInt("sample_rate", rate_hz);
}

int NvsManager::getAccelRange() {
    return prefs.getInt("accel_range", 8); // default 8g
}

void NvsManager::setAccelRange(int range) {
    prefs.putInt("accel_range", range);
}

int NvsManager::getGyroRange() {
    return prefs.getInt("gyro_range", 500); // default 500 deg/s
}

void NvsManager::setGyroRange(int range) {
    prefs.putInt("gyro_range", range);
}

void NvsManager::getCalibration(float& ax, float& ay, float& az, float& gx, float& gy, float& gz) {
    ax = prefs.getFloat("cal_ax", 0.0f);
    ay = prefs.getFloat("cal_ay", 0.0f);
    az = prefs.getFloat("cal_az", 0.0f);
    gx = prefs.getFloat("cal_gx", 0.0f);
    gy = prefs.getFloat("cal_gy", 0.0f);
    gz = prefs.getFloat("cal_gz", 0.0f);
}

void NvsManager::setCalibration(float ax, float ay, float az, float gx, float gy, float gz) {
    prefs.putFloat("cal_ax", ax);
    prefs.putFloat("cal_ay", ay);
    prefs.putFloat("cal_az", az);
    prefs.putFloat("cal_gx", gx);
    prefs.putFloat("cal_gy", gy);
    prefs.putFloat("cal_gz", gz);
}

void NvsManager::getAccelScale(float& sx, float& sy, float& sz) {
    sx = prefs.getFloat("scl_ax", 1.0f);
    sy = prefs.getFloat("scl_ay", 1.0f);
    sz = prefs.getFloat("scl_az", 1.0f);
}

void NvsManager::setAccelScale(float sx, float sy, float sz) {
    prefs.putFloat("scl_ax", sx);
    prefs.putFloat("scl_ay", sy);
    prefs.putFloat("scl_az", sz);
}
