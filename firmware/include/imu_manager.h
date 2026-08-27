#pragma once
#include <Arduino.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_ADXL345_U.h>
#include <Wire.h>

class ImuManager {
public:
    ImuManager();
    
    /**
     * @brief Initializes the selected sensor
     * @param sensorType "MPU6050" or "ADXL345"
     * @return true if successful, false otherwise.
     */
    bool begin(String sensorType);
    
    /**
     * @brief Check if there is new data available via the interrupt pin.
     * @return true if new data was read, false otherwise.
     */
    bool handle();

    // Configuration
    void setSampleRate(int rate_hz);
    void setRanges(int accelRange, int gyroRange);
    void calibrate();

    // Latest sensor readings
    float accelX, accelY, accelZ;
    float gyroX, gyroY, gyroZ;
    float temp;
    
    // Calibration Offsets
    float offsetAx = 0, offsetAy = 0, offsetAz = 0;
    float offsetGx = 0, offsetGy = 0, offsetGz = 0;
    
    // Calibration Scales
    float scaleAx = 1.0f, scaleAy = 1.0f, scaleAz = 1.0f;

private:
    String activeSensor = "MPU6050";
    Adafruit_MPU6050 mpu;
    Adafruit_ADXL345_Unified adxl;
    uint32_t sampleDelayUs = 20000; // Default 50Hz
    void readData();
};
