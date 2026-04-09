#pragma once

#include <memory>
#include "clients/PythonApiClient.h"

class SessionService {
public:
    explicit SessionService(std::shared_ptr<PythonApiClient> pythonClient);

    void createSession(
        const Json::Value& body,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

    void listMessages(
        int sessionId,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

private:
    std::shared_ptr<PythonApiClient> pythonClient_;
};