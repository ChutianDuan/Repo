#pragma once

#include <memory>
#include "PythonApiClient.h"

class ChatService {
public:
    explicit ChatService(std::shared_ptr<PythonApiClient> pythonClient);

    void createUserMessageAndSubmitChat(
        int sessionId,
        const Json::Value& body,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

private:
    std::shared_ptr<PythonApiClient> pythonClient_;
};