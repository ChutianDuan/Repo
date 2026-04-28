#pragma once

#include <drogon/drogon.h>

#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

struct GatewaySecurityConfig {
    bool authEnabled{false};
    bool rateLimitEnabled{true};
    bool rateLimitFailOpen{false};
    bool trustForwardedFor{false};
    int windowSeconds{60};
    int ipLimit{120};
    int userLimit{60};
    std::string apiKeyHeader{"X-API-Key"};
    std::string redisKeyPrefix{"rag_gateway:rate_limit"};
    std::unordered_map<std::string, std::string> apiKeys;

    static GatewaySecurityConfig fromEnv();
};

class GatewaySecurity {
public:
    using ResponseCallback = std::function<void(const drogon::HttpResponsePtr&)>;
    using Next = std::function<void(ResponseCallback&&)>;

    explicit GatewaySecurity(GatewaySecurityConfig config);

    void authorize(
        const drogon::HttpRequestPtr& req,
        ResponseCallback&& callback,
        Next&& next
    ) const;

private:
    struct AuthResult {
        bool ok{false};
        std::string principal;
        std::string error;
    };

    struct RateLimitResult {
        bool allowed{false};
        bool redisError{false};
        std::string scope;
        int limit{0};
        long long count{0};
        int retryAfterSeconds{0};
        std::string error;
    };

    struct RateLimitHeaderSet {
        std::string scope;
        int limit{0};
        long long remaining{0};
        long long resetEpochSeconds{0};
    };

    using RateLimitCallback = std::function<void(RateLimitResult)>;

    AuthResult authenticate(const drogon::HttpRequestPtr& req) const;
    void checkLimit(
        std::string scope,
        std::string identity,
        int limit,
        RateLimitCallback&& callback
    ) const;

    std::string clientIp(const drogon::HttpRequestPtr& req) const;
    std::string userIdentity(
        const drogon::HttpRequestPtr& req,
        const std::string& principal
    ) const;
    drogon::HttpResponsePtr makeErrorResponse(
        drogon::HttpStatusCode status,
        const std::string& code,
        const std::string& message
    ) const;
    void addRateLimitHeaders(
        const drogon::HttpResponsePtr& resp,
        const std::vector<RateLimitHeaderSet>& headers
    ) const;

    GatewaySecurityConfig config_;
};
