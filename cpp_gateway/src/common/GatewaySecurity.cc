#include "common/GatewaySecurity.h"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstdlib>
#include <exception>
#include <iomanip>
#include <memory>
#include <sstream>
#include <string>
#include <utility>

using namespace drogon;

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
    const char* value = std::getenv(name);
    if (!value) {
        return fallback;
    }
    auto trimmed = trim(value);
    return trimmed.empty() ? fallback : trimmed;
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

int getenvInt(const char* name, int fallback, int minValue) {
    const auto value = getenvString(name);
    if (value.empty()) {
        return fallback;
    }

    try {
        int parsed = std::stoi(value);
        return parsed < minValue ? fallback : parsed;
    } catch (...) {
        return fallback;
    }
}

std::vector<std::string> splitCommaSeparated(const std::string& value) {
    std::vector<std::string> parts;
    std::string current;
    std::stringstream stream(value);
    while (std::getline(stream, current, ',')) {
        current = trim(current);
        if (!current.empty()) {
            parts.push_back(current);
        }
    }
    return parts;
}

std::string fingerprint(const std::string& value) {
    uint64_t hash = 1469598103934665603ULL;
    for (unsigned char c : value) {
        hash ^= c;
        hash *= 1099511628211ULL;
    }

    std::ostringstream out;
    out << std::hex << hash;
    return out.str();
}

std::string sanitizeIdentity(const std::string& value) {
    std::string sanitized;
    sanitized.reserve(std::min<size_t>(value.size(), 80));

    for (char c : value) {
        if (sanitized.size() >= 80) {
            break;
        }

        const auto ch = static_cast<unsigned char>(c);
        if (std::isalnum(ch) || c == '-' || c == '_' || c == '.' || c == '@') {
            sanitized.push_back(c);
        } else {
            sanitized.push_back('_');
        }
    }

    return sanitized.empty() ? "unknown" : sanitized;
}

bool constantTimeEquals(const std::string& left, const std::string& right) {
    if (left.size() != right.size()) {
        return false;
    }

    unsigned char diff = 0;
    for (size_t i = 0; i < left.size(); ++i) {
        diff |= static_cast<unsigned char>(left[i] ^ right[i]);
    }
    return diff == 0;
}

std::string parseBearerToken(const std::string& authorization) {
    const std::string prefix = "Bearer ";
    if (authorization.size() < prefix.size()) {
        return "";
    }

    for (size_t i = 0; i < prefix.size(); ++i) {
        if (std::tolower(static_cast<unsigned char>(authorization[i])) !=
            std::tolower(static_cast<unsigned char>(prefix[i]))) {
            return "";
        }
    }

    return trim(authorization.substr(prefix.size()));
}

long long nowEpochSeconds() {
    return std::chrono::duration_cast<std::chrono::seconds>(
               std::chrono::system_clock::now().time_since_epoch()
    ).count();
}
}  // namespace

GatewaySecurityConfig GatewaySecurityConfig::fromEnv() {
    GatewaySecurityConfig config;

    const auto rawKeys = getenvString("GATEWAY_API_KEYS");
    for (const auto& entry : splitCommaSeparated(rawKeys)) {
        auto separator = entry.find('=');
        if (separator == std::string::npos) {
            separator = entry.find(':');
        }

        std::string principal;
        std::string secret;
        if (separator == std::string::npos) {
            secret = entry;
            principal = "key-" + fingerprint(secret);
        } else {
            principal = trim(entry.substr(0, separator));
            secret = trim(entry.substr(separator + 1));
            if (principal.empty()) {
                principal = "key-" + fingerprint(secret);
            }
        }

        if (!secret.empty()) {
            config.apiKeys.emplace(secret, sanitizeIdentity(principal));
        }
    }

    config.authEnabled = getenvBool("GATEWAY_AUTH_ENABLED", !config.apiKeys.empty());
    config.rateLimitEnabled = getenvBool("GATEWAY_RATE_LIMIT_ENABLED", true);
    config.rateLimitFailOpen = getenvBool("GATEWAY_RATE_LIMIT_FAIL_OPEN", false);
    config.trustForwardedFor = getenvBool("GATEWAY_TRUST_X_FORWARDED_FOR", false);
    config.windowSeconds = getenvInt("GATEWAY_RATE_LIMIT_WINDOW_SECONDS", 60, 1);
    config.ipLimit = getenvInt("GATEWAY_RATE_LIMIT_IP_LIMIT", 120, 1);
    config.userLimit = getenvInt("GATEWAY_RATE_LIMIT_USER_LIMIT", 60, 1);
    config.apiKeyHeader = getenvString("GATEWAY_API_KEY_HEADER", "X-API-Key");
    config.redisKeyPrefix = getenvString("GATEWAY_RATE_LIMIT_REDIS_PREFIX", "rag_gateway:rate_limit");

    return config;
}

GatewaySecurity::GatewaySecurity(GatewaySecurityConfig config)
    : config_(std::move(config)) {}

void GatewaySecurity::authorize(
    const HttpRequestPtr& req,
    ResponseCallback&& callback,
    Next&& next
) const {
    auto auth = authenticate(req);
    if (!auth.ok) {
        auto resp = makeErrorResponse(k401Unauthorized, "UNAUTHORIZED", auth.error);
        resp->addHeader("WWW-Authenticate", "Bearer");
        callback(resp);
        return;
    }

    if (!config_.rateLimitEnabled) {
        next(std::move(callback));
        return;
    }

    auto user = userIdentity(req, auth.principal);
    struct FlowState {
        HttpRequestPtr req;
        ResponseCallback callback;
        Next next;
        std::string userIdentity;
        std::vector<RateLimitHeaderSet> headers;
    };

    auto flow = std::make_shared<FlowState>();
    flow->req = req;
    flow->callback = std::move(callback);
    flow->next = std::move(next);
    flow->userIdentity = std::move(user);

    auto appendHeaders = [this, flow](const RateLimitResult& result) {
        if (result.redisError) {
            return;
        }

        flow->headers.push_back({
            result.scope,
            result.limit,
            std::max<long long>(0, result.limit - result.count),
            nowEpochSeconds() + result.retryAfterSeconds
        });
    };

    auto finish = [this, flow]() mutable {
        auto callback = std::move(flow->callback);
        auto next = std::move(flow->next);
        auto headers = flow->headers;

        ResponseCallback wrapped = [this, callback = std::move(callback), headers](
                                       const HttpResponsePtr& resp
                                   ) mutable {
            addRateLimitHeaders(resp, headers);
            callback(resp);
        };
        next(std::move(wrapped));
    };

    auto reject = [this, flow](const RateLimitResult& result) {
        const auto status = result.redisError ? k503ServiceUnavailable : k429TooManyRequests;
        const auto code = result.redisError ? "RATE_LIMIT_UNAVAILABLE" : "RATE_LIMITED";
        const auto message = result.redisError
            ? "gateway rate limit is unavailable"
            : "rate limit exceeded for " + result.scope;

        auto resp = makeErrorResponse(status, code, message);
        if (!result.redisError) {
            addRateLimitHeaders(resp, flow->headers);
            resp->addHeader("Retry-After", std::to_string(result.retryAfterSeconds));
        }
        flow->callback(resp);
    };

    auto checkUser = [this, flow, appendHeaders, finish, reject]() mutable {
        if (flow->userIdentity.empty()) {
            finish();
            return;
        }

        checkLimit(
            "User",
            flow->userIdentity,
            config_.userLimit,
            [this, flow, appendHeaders, finish, reject](RateLimitResult result) mutable {
                if (result.redisError) {
                    if (config_.rateLimitFailOpen) {
                        LOG_WARN << "Gateway user rate limit failed open: " << result.error;
                        finish();
                        return;
                    }
                    reject(result);
                    return;
                }

                appendHeaders(result);
                if (!result.allowed) {
                    reject(result);
                    return;
                }

                finish();
            }
        );
    };

    checkLimit(
        "IP",
        clientIp(req),
        config_.ipLimit,
        [this, flow, appendHeaders, checkUser, reject](RateLimitResult result) mutable {
            if (result.redisError) {
                if (config_.rateLimitFailOpen) {
                    LOG_WARN << "Gateway IP rate limit failed open: " << result.error;
                    checkUser();
                    return;
                }
                reject(result);
                return;
            }

            appendHeaders(result);
            if (!result.allowed) {
                reject(result);
                return;
            }

            checkUser();
        }
    );
}

GatewaySecurity::AuthResult GatewaySecurity::authenticate(const HttpRequestPtr& req) const {
    if (!config_.authEnabled) {
        return {true, "", ""};
    }

    if (config_.apiKeys.empty()) {
        return {false, "", "gateway auth is enabled but no API key is configured"};
    }

    auto apiKey = trim(req->getHeader(config_.apiKeyHeader));
    if (apiKey.empty()) {
        apiKey = parseBearerToken(req->getHeader("Authorization"));
    }

    if (apiKey.empty()) {
        return {false, "", "missing API key"};
    }

    for (const auto& item : config_.apiKeys) {
        if (constantTimeEquals(apiKey, item.first)) {
            return {true, item.second, ""};
        }
    }

    return {false, "", "invalid API key"};
}

void GatewaySecurity::checkLimit(
    std::string scope,
    std::string identity,
    int limit,
    RateLimitCallback&& callback
) const {
    auto key = config_.redisKeyPrefix + ":" + sanitizeIdentity(scope) + ":" + sanitizeIdentity(identity);
    auto callbackPtr = std::make_shared<RateLimitCallback>(std::move(callback));
    try {
        auto redisClient = app().getRedisClient("default");
        redisClient->execCommandAsync(
            [this, scope, limit, key, callbackPtr](
                const drogon::nosql::RedisResult& result
            ) {
                long long count = 0;
                try {
                    count = result.asInteger();
                } catch (const std::exception& e) {
                    (*callbackPtr)({false, true, scope, limit, 0, config_.windowSeconds, e.what()});
                    return;
                }

                if (count == 1) {
                    try {
                        auto redisClient = app().getRedisClient("default");
                        redisClient->execCommandAsync(
                            [](const drogon::nosql::RedisResult&) {},
                            [](const std::exception& e) {
                                LOG_WARN << "Failed to set rate limit key expiry: " << e.what();
                            },
                            "EXPIRE %s %d",
                            key.c_str(),
                            config_.windowSeconds
                        );
                    } catch (const std::exception& e) {
                        LOG_WARN << "Failed to schedule rate limit key expiry: " << e.what();
                    }
                }

                (*callbackPtr)({
                    count <= limit,
                    false,
                    scope,
                    limit,
                    count,
                    config_.windowSeconds,
                    ""
                });
            },
            [this, scope, limit, callbackPtr](
                const std::exception& e
            ) {
                (*callbackPtr)({false, true, scope, limit, 0, config_.windowSeconds, e.what()});
            },
            "INCR %s",
            key.c_str()
        );
    } catch (const std::exception& e) {
        (*callbackPtr)({false, true, scope, limit, 0, config_.windowSeconds, e.what()});
    }
}

std::string GatewaySecurity::clientIp(const HttpRequestPtr& req) const {
    if (config_.trustForwardedFor) {
        auto forwardedFor = req->getHeader("X-Forwarded-For");
        if (!forwardedFor.empty()) {
            auto comma = forwardedFor.find(',');
            auto first = comma == std::string::npos ? forwardedFor : forwardedFor.substr(0, comma);
            first = trim(first);
            if (!first.empty()) {
                return first;
            }
        }

        auto realIp = trim(req->getHeader("X-Real-IP"));
        if (!realIp.empty()) {
            return realIp;
        }
    }

    return req->getPeerAddr().toIp();
}

std::string GatewaySecurity::userIdentity(
    const HttpRequestPtr& req,
    const std::string& principal
) const {
    auto userId = trim(req->getHeader("X-User-Id"));
    if (!userId.empty()) {
        return userId;
    }
    return principal;
}

HttpResponsePtr GatewaySecurity::makeErrorResponse(
    HttpStatusCode status,
    const std::string& code,
    const std::string& message
) const {
    Json::Value body(Json::objectValue);
    body["ok"] = false;
    body["code"] = code;
    body["message"] = message;

    auto resp = HttpResponse::newHttpJsonResponse(body);
    resp->setStatusCode(status);
    return resp;
}

void GatewaySecurity::addRateLimitHeaders(
    const HttpResponsePtr& resp,
    const std::vector<RateLimitHeaderSet>& headers
) const {
    if (!resp) {
        return;
    }

    for (const auto& item : headers) {
        const auto prefix = std::string("X-RateLimit-") + item.scope + "-";
        resp->addHeader(prefix + "Limit", std::to_string(item.limit));
        resp->addHeader(prefix + "Remaining", std::to_string(item.remaining));
        resp->addHeader(prefix + "Reset", std::to_string(item.resetEpochSeconds));
    }
}
