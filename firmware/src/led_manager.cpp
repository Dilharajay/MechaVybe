#include "led_manager.h"
#include "config.h"

LedManager::LedManager() 
    : pixels(Config::WS2812_NUM_LEDS, Config::WS2812_PIN, NEO_GRB + NEO_KHZ800) {
}

void LedManager::begin() {
    pixels.begin();
    pixels.setBrightness(50); // Set to a reasonable default brightness (0-255)
    turnOff();
}

void LedManager::setColor(uint8_t r, uint8_t g, uint8_t b) {
    for(int i = 0; i < Config::WS2812_NUM_LEDS; i++) {
        pixels.setPixelColor(i, pixels.Color(r, g, b));
    }
    pixels.show();
}

void LedManager::setWifiConnecting() {
    // Yellow for connecting
    setColor(255, 128, 0);
}

void LedManager::setWifiConnected() {
    // Green for connected
    setColor(0, 255, 0);
}

void LedManager::setWifiError() {
    // Red for error
    setColor(255, 0, 0);
}

void LedManager::setOtaUpdating() {
    // Blue for OTA updating
    setColor(0, 0, 255);
}

void LedManager::setPcConnected() {
    setColor(0, 255, 255); // Cyan
}

void LedManager::turnOff() {
    setColor(0, 0, 0);
}
