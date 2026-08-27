#include "ota_manager.h"
#include "config.h"
#include "logger.h"
#include "led_manager.h"
#include <WiFi.h>
#include <ArduinoOTA.h>

OtaManager::OtaManager() {
}

void OtaManager::begin(const char* ssid, const char* password, const char* hostname, LedManager* led) {
    Logger::info("Booting OTA Manager...");
    
    if (led) {
        led->setWifiConnecting();
    }

    // Connect to Wi-Fi
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    Logger::info("Connecting to WiFi");
    
    // Wait for connection, but don't block forever without updating LED
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 200) { // 200 * 50ms = 10s
        if (led) led->update();
        delay(50);
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        if (led) led->setWifiConnected();
        Logger::info("");
        Logger::info("Connected to %s", ssid);
        Logger::info("IP address: %s", WiFi.localIP().toString().c_str());
    } else {
        if (led) led->turnOff();
        Logger::warn("WiFi Connection Failed! Proceeding offline.");
    }

    // Setup OTA
    ArduinoOTA.setHostname(hostname);

    ArduinoOTA.onStart([led]() {
        if (led) led->setOtaUpdating();
        String type;
        if (ArduinoOTA.getCommand() == U_FLASH) {
            type = "sketch";
        } else { // U_SPIFFS
            type = "filesystem";
        }
        Logger::info("Start updating %s", type.c_str());
    });

    ArduinoOTA.onEnd([led]() {
        if (led) led->setWifiConnected();
        Logger::info("\nEnd");
    });

    ArduinoOTA.onProgress([led](unsigned int progress, unsigned int total) {
        if (led) led->update();
        Logger::info("Progress: %u%%\r", (progress / (total / 100)));
    });

    ArduinoOTA.onError([](ota_error_t error) {
        Logger::error("Error[%u]: ", error);
        if (error == OTA_AUTH_ERROR) {
            Logger::error("Auth Failed");
        } else if (error == OTA_BEGIN_ERROR) {
            Logger::error("Begin Failed");
        } else if (error == OTA_CONNECT_ERROR) {
            Logger::error("Connect Failed");
        } else if (error == OTA_RECEIVE_ERROR) {
            Logger::error("Receive Failed");
        } else if (error == OTA_END_ERROR) {
            Logger::error("End Failed");
        }
    });

    ArduinoOTA.begin();
    Logger::info("OTA Ready");
}

void OtaManager::handle() {
    ArduinoOTA.handle();
}
