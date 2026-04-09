#pragma once

#include <memory>
#include <string>

#include <drogon/drogon.h>

class PythonSSEClient;

class StreamChatService {
public:
    explicit StreamChatService(std::shared_ptr<PythonSSEClient> pythonSSEClient);

    void handleStream(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

private:
    std::shared_ptr<PythonSSEClient> pythonSSEClient_;

    static bool validateRequestBody(const Json::Value& body, std::string& error);
    static std::string buildSseErrorEvent(const std::string& message);
    static drogon::HttpResponsePtr buildJsonErrorResponse(int code, const std::string& message);
};