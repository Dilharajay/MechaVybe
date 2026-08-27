#pragma once

#include <Arduino.h>

class LedManager;

class OtaManager {
public:
    OtaManager();
    
    /**
     * @brief Initializes Wi-Fi and the OTA update facility.
     * 
     * @param ssid WiFi SSID
     * @param password WiFi Password
     * @param hostname OTA Hostname
     * @param led Pointer to an LedManager to indicate status (optional)
     */
    void begin(const char* ssid, const char* password, const char* hostname, LedManager* led = nullptr);
    
    /**
     * @brief Handles OTA updates. Must be called in the main loop().
     */
    void handle();
};
