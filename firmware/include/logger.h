#pragma once
#include <Arduino.h>

enum LogLevel {
    LOG_LEVEL_DEBUG = 0,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARN,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_NONE
};

class Logger {
public:
    /**
     * @brief Initializes the Serial interface using Config settings.
     */
    static void begin();
    
    /**
     * @brief Changes the current log level at runtime.
     */
    static void setLevel(LogLevel level);
    
    // Logging functions
    static void debug(const char* format, ...);
    static void info(const char* format, ...);
    static void warn(const char* format, ...);
    static void error(const char* format, ...);
    
private:
    static LogLevel _level;
    static void log(const char* levelStr, const char* format, va_list args);
};
