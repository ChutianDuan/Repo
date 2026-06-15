#pragma once

#include <string>

#include <json/json.h>

#include "common/GatewaySecurity.h"

struct GatewayListenConfig {
    std::string address{"0.0.0.0"};
    int port{8080};
    bool https{false};
};

struct GatewayMysqlConfig {
    std::string host{"127.0.0.1"};
    int port{3306};
    std::string database{"ai_app"};
    std::string user{"ai_user"};
    std::string password{"ai_password"};
    int connectionNumber{1};
    bool isFast{false};
    double timeout{-1.0};
};

struct GatewayRedisConfig {
    std::string host{"127.0.0.1"};
    int port{6379};
    std::string password;
    int db{0};
    int connectionNumber{1};
    bool isFast{false};
    double timeout{-1.0};
};

struct GatewayAppConfig {
    int threadsNum{4};
    bool enableSession{false};
    std::string documentRoot{"./"};
    std::string clientMaxBodySize{"100M"};
};

struct GatewayLogConfig {
    std::string logPath{"./logs"};
    std::string logfileBaseName{"cpp_gateway"};
    int logSizeLimit{100000000};
    int maxFiles{10};
    bool displayLocalTime{true};
};

struct GatewaySseProxyConfig {
    int maxConcurrentStreams{64};
    long connectTimeoutSeconds{10};
    long upstreamIdleTimeoutSeconds{120};
    long upstreamLowSpeedLimitBytesPerSecond{1};
    long curlBufferSizeBytes{1024};
    bool emitGatewayMetrics{true};
};

struct GatewayConfig {
    std::string pythonInternalBaseUrl{"http://127.0.0.1:8000"};
    GatewayListenConfig listen;
    GatewayMysqlConfig mysql;
    GatewayRedisConfig redis;
    GatewayAppConfig app;
    GatewayLogConfig log;
    GatewaySseProxyConfig sse;
    GatewaySecurityConfig security;

    static GatewayConfig fromEnv();
    Json::Value toDrogonConfigJson() const;
};
