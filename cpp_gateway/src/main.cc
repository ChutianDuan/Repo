#include <cstdlib>
#include <functional>
#include <memory>
#include <string>

#include <drogon/drogon.h>

#include "clients/PythonApiClient.h"
#include "clients/PythonSSEClient.h"
#include "handlers/ChatHandler.h"
#include "handlers/DocumentHandler.h"
#include "handlers/HealthHandler.h"
#include "handlers/SessionHandler.h"
#include "handlers/StreamChatHandler.h"

using namespace drogon;

namespace {
HttpResponsePtr makeBadRequestResponse(const std::string& error) {
    Json::Value body(Json::objectValue);
    body["ok"] = false;
    body["error"] = error;

    auto resp = HttpResponse::newHttpJsonResponse(body);
    resp->setStatusCode(k400BadRequest);
    return resp;
}
}  // namespace

int main() {
    const char* pythonBase = std::getenv("PYTHON_INTERNAL_BASE_URL");
    std::string pythonBaseUrl = pythonBase ? pythonBase : "http://127.0.0.1:8000";

    auto pythonClient = std::make_shared<PythonApiClient>(pythonBaseUrl);
    auto pythonSSEClient = std::make_shared<PythonSSEClient>(pythonBaseUrl);

    auto healthHandler = std::make_shared<HealthService>(pythonClient);
    auto documentHandler = std::make_shared<DocumentService>(pythonClient);
    auto sessionHandler = std::make_shared<SessionService>(pythonClient);
    auto chatHandler = std::make_shared<ChatService>(pythonClient);
    auto streamChatHandler = std::make_shared<StreamChatService>(pythonSSEClient);

    app().registerHandler(
        "/health",
        [healthHandler](const HttpRequestPtr&,
                        std::function<void(const HttpResponsePtr&)>&& callback) {
            healthHandler->handle(std::move(callback));
        },
        {Get}
    );

    app().registerHandler(
        "/v1/tasks/{1}",
        [pythonClient](const HttpRequestPtr&,
                       std::function<void(const HttpResponsePtr&)>&& callback,
                       const std::string& taskId) {
            pythonClient->proxyTaskStatus(taskId, std::move(callback));
        },
        {Get}
    );

    app().registerHandler(
        "/v1/documents",
        [documentHandler](const HttpRequestPtr& req,
                          std::function<void(const HttpResponsePtr&)>&& callback) {
            documentHandler->uploadAndSubmit(req, std::move(callback));
        },
        {Post}
    );

    app().registerHandler(
        "/v1/sessions",
        [sessionHandler](const HttpRequestPtr& req,
                         std::function<void(const HttpResponsePtr&)>&& callback) {
            auto json = req->getJsonObject();
            if (!json) {
                callback(makeBadRequestResponse("invalid json"));
                return;
            }
            sessionHandler->createSession(*json, std::move(callback));
        },
        {Post}
    );

    app().registerHandler(
        "/v1/sessions/{1}/messages",
        [chatHandler](const HttpRequestPtr& req,
                      std::function<void(const HttpResponsePtr&)>&& callback,
                      int sessionId) {
            auto json = req->getJsonObject();
            if (!json) {
                callback(makeBadRequestResponse("invalid json"));
                return;
            }
            chatHandler->createUserMessageAndSubmitChat(sessionId, *json, std::move(callback));
        },
        {Post}
    );

    app().registerHandler(
        "/v1/sessions/{1}/messages",
        [sessionHandler](const HttpRequestPtr&,
                         std::function<void(const HttpResponsePtr&)>&& callback,
                         int sessionId) {
            sessionHandler->listMessages(sessionId, std::move(callback));
        },
        {Get}
    );

    app().registerHandler(
        "/v1/chat/stream",
        [streamChatHandler](const HttpRequestPtr& req,
                            std::function<void(const HttpResponsePtr&)>&& callback) {
            streamChatHandler->handleStream(req, std::move(callback));
        },
        {Post}
    );

    app().loadConfigFile("config.json");
    app().run();
    return 0;
}