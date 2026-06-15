#include "common/GatewayConfig.h"

#include <cctype>
#include <cstdlib>
#include <initializer_list>
#include <string>

namespace {
std::string trim(const std::string& value) {
    auto begin = value.begin();
    while (begin != value.end() && std::isspace(static_cast<unsigned char>(*begin))) {
        ++begin;
    }

    auto end = value.end();
    while (end != begin && std::isspace(static_cast<unsigned char>(*(end - 1)))) {
        --end;
    }

    return std::string(begin, end);
}

std::string getenvString(const char* name, const std::string& fallback = "") {
    const char* raw = std::getenv(name);
    if (!raw) {
        return fallback;
    }

    auto value = trim(raw);
    return value.empty() ? fallback : value;
}

std::string getenvFirstString(
    std::initializer_list<const char*> names,
    const std::string& fallback = ""
) {
    for (const char* name : names) {
        auto value = getenvString(name);
        if (!value.empty()) {
            return value;
        }
    }
    return fallback;
}

bool parseBool(const std::string& value, bool fallback) {
    if (value.empty()) {
        return fallback;
    }

    std::string normalized;
    normalized.reserve(value.size());
    for (char c : value) {
        normalized.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }

    if (normalized == "1" || normalized == "true" || normalized == "yes" || normalized == "on") {
        return true;
    }
    if (normalized == "0" || normalized == "false" || normalized == "no" || normalized == "off") {
        return false;
    }
    return fallback;
}

bool getenvBool(const char* name, bool fallback) {
    return parseBool(getenvString(name), fallback);
}

int parseInt(const std::string& value, int fallback, int minValue) {
    if (value.empty()) {
        return fallback;
    }

    try {
        const int parsed = std::stoi(value);
        return parsed < minValue ? fallback : parsed;
    } catch (...) {
        return fallback;
    }
}

int getenvInt(const char* name, int fallback, int minValue) {
    return parseInt(getenvString(name), fallback, minValue);
}

int getenvFirstInt(
    std::initializer_list<const char*> names,
    int fallback,
    int minValue
) {
    for (const char* name : names) {
        const auto value = getenvString(name);
        if (!value.empty()) {
            return parseInt(value, fallback, minValue);
        }
    }
    return fallback;
}

long parseLong(const std::string& value, long fallback, long minValue) {
    if (value.empty()) {
        return fallback;
    }

    try {
        const long parsed = std::stol(value);
        return parsed < minValue ? fallback : parsed;
    } catch (...) {
        return fallback;
    }
}

long getenvLong(const char* name, long fallback, long minValue) {
    return parseLong(getenvString(name), fallback, minValue);
}

double getenvDouble(const char* name, double fallback) {
    const auto value = getenvString(name);
    if (value.empty()) {
        return fallback;
    }

    try {
        return std::stod(value);
    } catch (...) {
        return fallback;
    }
}

Json::Value makeDrogonMysqlClient(const GatewayMysqlConfig& config) {
    Json::Value client(Json::objectValue);
    client["name"] = "default";
    client["rdbms"] = "mysql";
    client["host"] = config.host;
    client["port"] = config.port;
    client["dbname"] = config.database;
    client["user"] = config.user;
    client["passwd"] = config.password;
    client["connection_number"] = config.connectionNumber;
    client["is_fast"] = config.isFast;
    client["timeout"] = config.timeout;
    return client;
}

Json::Value makeDrogonRedisClient(const GatewayRedisConfig& config) {
    Json::Value client(Json::objectValue);
    client["name"] = "default";
    client["host"] = config.host;
    client["port"] = config.port;
    client["passwd"] = config.password;
    client["db"] = config.db;
    client["is_fast"] = config.isFast;
    client["number_of_connections"] = config.connectionNumber;
    client["timeout"] = config.timeout;
    return client;
}
}  // namespace

GatewayConfig GatewayConfig::fromEnv() {
    GatewayConfig config;

    const int appPort = getenvInt("APP_PORT", 8000, 1);
    config.pythonInternalBaseUrl = getenvFirstString(
        {"PYTHON_INTERNAL_BASE_URL", "PYTHON_BASE_URL"},
        "http://127.0.0.1:" + std::to_string(appPort)
    );

    config.listen.address = getenvFirstString(
        {"GATEWAY_LISTEN_HOST", "GATEWAY_HOST"},
        config.listen.address
    );
    config.listen.port = getenvFirstInt(
        {"GATEWAY_LISTEN_PORT", "GATEWAY_PORT", "PORT"},
        config.listen.port,
        1
    );
    config.listen.https = getenvBool("GATEWAY_HTTPS", config.listen.https);

    config.mysql.host = getenvString("MYSQL_HOST", config.mysql.host);
    config.mysql.port = getenvInt("MYSQL_PORT", config.mysql.port, 1);
    config.mysql.database = getenvString("MYSQL_DATABASE", config.mysql.database);
    config.mysql.user = getenvString("MYSQL_USER", config.mysql.user);
    config.mysql.password = getenvString("MYSQL_PASSWORD", config.mysql.password);
    config.mysql.connectionNumber = getenvInt(
        "GATEWAY_MYSQL_CONNECTIONS",
        config.mysql.connectionNumber,
        1
    );
    config.mysql.timeout = getenvDouble("GATEWAY_MYSQL_TIMEOUT_SECONDS", config.mysql.timeout);

    config.redis.host = getenvString("REDIS_HOST", config.redis.host);
    config.redis.port = getenvInt("REDIS_PORT", config.redis.port, 1);
    config.redis.password = getenvString("REDIS_PASSWORD", config.redis.password);
    config.redis.db = getenvInt("REDIS_DB", config.redis.db, 0);
    config.redis.connectionNumber = getenvInt(
        "GATEWAY_REDIS_CONNECTIONS",
        config.redis.connectionNumber,
        1
    );
    config.redis.timeout = getenvDouble("GATEWAY_REDIS_TIMEOUT_SECONDS", config.redis.timeout);

    config.app.threadsNum = getenvInt("GATEWAY_THREADS", config.app.threadsNum, 1);
    config.app.clientMaxBodySize = getenvFirstString(
        {"GATEWAY_CLIENT_MAX_BODY_SIZE", "MAX_DOCUMENT_SIZE_BYTES"},
        config.app.clientMaxBodySize
    );

    config.log.logPath = getenvString("GATEWAY_LOG_PATH", config.log.logPath);
    config.log.logfileBaseName = getenvString(
        "GATEWAY_LOG_FILE_BASE_NAME",
        config.log.logfileBaseName
    );
    config.log.logSizeLimit = getenvInt(
        "GATEWAY_LOG_SIZE_LIMIT",
        config.log.logSizeLimit,
        1
    );
    config.log.maxFiles = getenvInt("GATEWAY_LOG_MAX_FILES", config.log.maxFiles, 1);

    config.sse.maxConcurrentStreams = getenvInt(
        "GATEWAY_MAX_STREAMS",
        config.sse.maxConcurrentStreams,
        1
    );
    config.sse.connectTimeoutSeconds = getenvLong(
        "GATEWAY_SSE_CONNECT_TIMEOUT_SECONDS",
        config.sse.connectTimeoutSeconds,
        1
    );
    config.sse.upstreamIdleTimeoutSeconds = getenvLong(
        "GATEWAY_SSE_UPSTREAM_IDLE_TIMEOUT_SECONDS",
        config.sse.upstreamIdleTimeoutSeconds,
        1
    );
    config.sse.upstreamLowSpeedLimitBytesPerSecond = getenvLong(
        "GATEWAY_SSE_UPSTREAM_LOW_SPEED_BYTES",
        config.sse.upstreamLowSpeedLimitBytesPerSecond,
        1
    );
    config.sse.curlBufferSizeBytes = getenvLong(
        "GATEWAY_SSE_CURL_BUFFER_BYTES",
        config.sse.curlBufferSizeBytes,
        1
    );
    config.sse.emitGatewayMetrics = getenvBool(
        "GATEWAY_SSE_EMIT_GATEWAY_METRICS",
        config.sse.emitGatewayMetrics
    );

    config.security = GatewaySecurityConfig::fromEnv();
    return config;
}

Json::Value GatewayConfig::toDrogonConfigJson() const {
    Json::Value root(Json::objectValue);

    Json::Value listeners(Json::arrayValue);
    Json::Value listener(Json::objectValue);
    listener["address"] = listen.address;
    listener["port"] = listen.port;
    listener["https"] = listen.https;
    listeners.append(listener);
    root["listeners"] = listeners;

    Json::Value appJson(Json::objectValue);
    appJson["threads_num"] = app.threadsNum;
    appJson["enable_session"] = app.enableSession;
    appJson["document_root"] = app.documentRoot;
    appJson["client_max_body_size"] = app.clientMaxBodySize;
    root["app"] = appJson;

    Json::Value dbClients(Json::arrayValue);
    dbClients.append(makeDrogonMysqlClient(mysql));
    root["db_clients"] = dbClients;

    Json::Value redisClients(Json::arrayValue);
    redisClients.append(makeDrogonRedisClient(redis));
    root["redis_clients"] = redisClients;

    Json::Value logJson(Json::objectValue);
    logJson["log_path"] = log.logPath;
    logJson["logfile_base_name"] = log.logfileBaseName;
    logJson["log_size_limit"] = log.logSizeLimit;
    logJson["max_files"] = log.maxFiles;
    logJson["display_local_time"] = log.displayLocalTime;
    root["log"] = logJson;

    return root;
}
