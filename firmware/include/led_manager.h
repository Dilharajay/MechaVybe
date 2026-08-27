#pragma once
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

class LedManager {
public:
    LedManager();
    
    /**
     * @brief Initializes the addressable RGB LED.
     */
    void begin();
    
    /**
     * @brief Sets the RGB LED color (0-255 for each channel).
     */
    void setColor(uint8_t r, uint8_t g, uint8_t b);
    
    // Quick status helpers
    void setWifiConnecting();
    void setWifiConnected();
    void setWifiError();
    void setMqttError();
    void setOtaUpdating();
    void setPcConnected();
    void setInferenceHealthy();
    void setInferenceAnomaly();
    void setDataCollection();
    void setModeSwitching();
    void turnOff();

private:
    Adafruit_NeoPixel pixels;
};
