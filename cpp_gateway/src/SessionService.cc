#include "SessionService.h"

SessionService::SessionService(std::shared_ptr<PythonApiClient> pythonClient)
    : pythonClient_(std::move(pythonClient)) {}

void SessionService::createSession(
    const Json::Value& body,
    std::function<void(const drogon::HttpResponsePtr&)>&& callback
) {
    pythonClient_->forwardJsonPost(
        "/internal/sessions",
        body,
        std::move(callback)
    );
}

void SessionService::listMessages(
    int sessionId,
    std::function<void(const drogon::HttpResponsePtr&)>&& callback
) {
    pythonClient_->forwardGet(
        "/internal/sessions/" + std::to_string(sessionId) + "/messages",
        std::move(callback)
    );
}