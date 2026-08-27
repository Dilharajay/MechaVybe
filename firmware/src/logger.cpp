#include "logger.h"
#include "config.h"

// Initialize static member
LogLevel Logger::_level = static_cast<LogLevel>(Config::DEFAULT_LOG_LEVEL);

void Logger::begin() {
    Serial.begin(Config::SERIAL_BAUD_RATE);
}

void Logger::setLevel(LogLevel level) {
    _level = level;
}

void Logger::log(const char* levelStr, const char* format, va_list args) {
    // Print the log level prefix
    Serial.printf("[%s] ", levelStr);
    
    // Format the actual message
    char buffer[256];
    vsnprintf(buffer, sizeof(buffer), format, args);
    
    // Print the message with a newline
    Serial.println(buffer);
}

void Logger::debug(const char* format, ...) {
    if (_level > LOG_LEVEL_DEBUG) return;
    va_list args;
    va_start(args, format);
    log("DEBUG", format, args);
    va_end(args);
}

void Logger::info(const char* format, ...) {
    if (_level > LOG_LEVEL_INFO) return;
    va_list args;
    va_start(args, format);
    log("INFO ", format, args);
    va_end(args);
}

void Logger::warn(const char* format, ...) {
    if (_level > LOG_LEVEL_WARN) return;
    va_list args;
    va_start(args, format);
    log("WARN ", format, args);
    va_end(args);
}

void Logger::error(const char* format, ...) {
    if (_level > LOG_LEVEL_ERROR) return;
    va_list args;
    va_start(args, format);
    log("ERROR", format, args);
    va_end(args);
}
