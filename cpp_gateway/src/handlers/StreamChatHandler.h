#pragma once

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

private:
    std::shared_ptr<PythonSSEClient> pythonSSEClient_;
    std::shared_ptr<PythonApiClient> pythonApiClient_;

    static bool validateRequestBody(const Json::Value& body, std::string& error);
    static std::string buildSseErrorEvent(const std::string& message);
    static drogon::HttpResponsePtr buildJsonErrorResponse(int code, const std::string& message);
    void startStreamResponse(
        const Json::Value& body,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );
};
