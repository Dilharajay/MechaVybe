#include "imu_manager.h"
#include "config.h"
#include "logger.h"
#include <Wire.h>

ImuManager::ImuManager() : adxl(12345), accelX(0), accelY(0), accelZ(0), gyroX(0), gyroY(0), gyroZ(0), temp(0) {}

bool ImuManager::begin(String sensorType) {
    activeSensor = sensorType;
    Wire.begin(Config::I2C_SDA_PIN, Config::I2C_SCL_PIN);
    Wire.setClock(400000); // CRITICAL: 400kHz Fast Mode is required to achieve 2000Hz sample rate
    
    if (activeSensor == "ADXL345") {
        if (!adxl.begin()) {
            Logger::error("Failed to find ADXL345 chip");
            return false;
        }
        Logger::info("ADXL345 Found!");
        
        // Maximize hardware data rate to prevent sample duplication smoothing. 
        // NOTE: 3200Hz and 1600Hz are SPI ONLY! I2C maximum is 800Hz.
        adxl.setDataRate(ADXL345_DATARATE_800_HZ);
        
        return true;
    } else {
        // Default to MPU6050
        if (!mpu.begin(0x68, &Wire)) {
            Logger::error("Failed to find MPU6050 chip");
            return false;
        }
        Logger::info("MPU6050 Found!");
        
        // MPU6050_BAND_260_HZ (DLPF disabled) causes some clone chips to freeze and output static values.
        // MPU6050_BAND_184_HZ is the maximum safe bandwidth that keeps DLPF active.
        mpu.setFilterBandwidth(MPU6050_BAND_184_HZ);
        
        return true;
    }
}

void ImuManager::setSampleRate(int rate_hz) {
    if (rate_hz <= 0) return;
    sampleDelayUs = 1000000 / rate_hz;
}

void ImuManager::setRanges(int accelRange, int gyroRange) {
    if (activeSensor == "ADXL345") {
        switch (accelRange) {
            case 2: adxl.setRange(ADXL345_RANGE_2_G); break;
            case 4: adxl.setRange(ADXL345_RANGE_4_G); break;
            case 8: adxl.setRange(ADXL345_RANGE_8_G); break;
            case 16: adxl.setRange(ADXL345_RANGE_16_G); break;
            default: adxl.setRange(ADXL345_RANGE_8_G); break;
        }
        return;
    }
    
    switch (accelRange) {
        case 2: mpu.setAccelerometerRange(MPU6050_RANGE_2_G); break;
        case 4: mpu.setAccelerometerRange(MPU6050_RANGE_4_G); break;
        case 8: mpu.setAccelerometerRange(MPU6050_RANGE_8_G); break;
        case 16: mpu.setAccelerometerRange(MPU6050_RANGE_16_G); break;
        default: mpu.setAccelerometerRange(MPU6050_RANGE_8_G); break;
    }

    switch (gyroRange) {
        case 250: mpu.setGyroRange(MPU6050_RANGE_250_DEG); break;
        case 500: mpu.setGyroRange(MPU6050_RANGE_500_DEG); break;
        case 1000: mpu.setGyroRange(MPU6050_RANGE_1000_DEG); break;
        case 2000: mpu.setGyroRange(MPU6050_RANGE_2000_DEG); break;
        default: mpu.setGyroRange(MPU6050_RANGE_500_DEG); break;
    }
}

void ImuManager::calibrate() {
    Logger::info("Calibrating %s... Keep it still!", activeSensor.c_str());
    float sumAx = 0, sumAy = 0, sumAz = 0;
    float sumGx = 0, sumGy = 0, sumGz = 0;
    
    for (int i = 0; i < 100; i++) {
        if (activeSensor == "ADXL345") {
            sensors_event_t event;
            adxl.getEvent(&event);
            sumAx += event.acceleration.x;
            sumAy += event.acceleration.y;
            sumAz += (event.acceleration.z - 9.80665f); // Remove gravity on Z
        } else {
            sensors_event_t a, g, t;
            mpu.getEvent(&a, &g, &t);
            sumAx += a.acceleration.x;
            sumAy += a.acceleration.y;
            sumAz += (a.acceleration.z - 9.80665f); // Remove gravity on Z
            sumGx += g.gyro.x;
            sumGy += g.gyro.y;
            sumGz += g.gyro.z;
        }
        delay(10);
    }
    
    offsetAx = sumAx / 100.0f;
    offsetAy = sumAy / 100.0f;
    offsetAz = sumAz / 100.0f;
    offsetGx = sumGx / 100.0f;
    offsetGy = sumGy / 100.0f;
    offsetGz = sumGz / 100.0f;
    Logger::info("Calibration complete!");
}

void ImuManager::readData() {
    if (activeSensor == "ADXL345") {
        sensors_event_t event;
        adxl.getEvent(&event);
        
        accelX = (event.acceleration.x - offsetAx) * scaleAx;
        accelY = (event.acceleration.y - offsetAy) * scaleAy;
        accelZ = (event.acceleration.z - offsetAz) * scaleAz;
        
        gyroX = 0;
        gyroY = 0;
        gyroZ = 0;
        temp = 25.0; // dummy
    } else {
        sensors_event_t a, g, t;
        mpu.getEvent(&a, &g, &t);
        
        accelX = (a.acceleration.x - offsetAx) * scaleAx;
        accelY = (a.acceleration.y - offsetAy) * scaleAy;
        accelZ = (a.acceleration.z - offsetAz) * scaleAz;
        
        gyroX = g.gyro.x - offsetGx;
        gyroY = g.gyro.y - offsetGy;
        gyroZ = g.gyro.z - offsetGz;
        
        temp = t.temperature;
    }
}

bool ImuManager::handle() {
    static uint32_t lastReadTime = 0;
    if (micros() - lastReadTime >= sampleDelayUs) {
        lastReadTime = micros();
        readData();
        return true;
    }
    return false;
}
