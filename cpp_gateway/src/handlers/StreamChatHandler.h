#pragma once

#include <atomic>
#include <memory>
#include <string>

#include <drogon/drogon.h>

class PythonSSEClient;
class PythonApiClient;

class StreamChatService {
public:
    StreamChatService(
        std::shared_ptr<PythonSSEClient> pythonSSEClient,
        std::shared_ptr<PythonApiClient> pythonApiClient
    );

    void handleStream(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

    void handleAgentStream(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

private:
    struct StreamSlotLease;

    std::shared_ptr<PythonSSEClient> pythonSSEClient_;
    std::shared_ptr<PythonApiClient> pythonApiClient_;
    int maxConcurrentStreams_{64};
    std::shared_ptr<std::atomic<int>> activeStreams_;

    static bool validateRequestBody(const Json::Value& body, std::string& error);
    static bool validateAgentRequestBody(const Json::Value& body, std::string& error);
    static std::string buildSseErrorEvent(const std::string& message);
    static drogon::HttpResponsePtr buildJsonErrorResponse(
        int code,
        const std::string& message,
        drogon::HttpStatusCode status
    );
    std::shared_ptr<StreamSlotLease> acquireStreamSlot() const;
    void startStreamResponse(
        const Json::Value& body,
        std::string upstreamPath,
        std::shared_ptr<StreamSlotLease> streamSlot,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );
};
