#include <cstdlib>
#include <memory>
#include <string>

#include <drogon/drogon.h>

#include "DocumentService.h"
#include "HealthService.h"
#include "PythonApiClient.h"
#include "SessionService.h"
#include "ChatService.h"

using namespace drogon;

int main() {
    const char* pythonBase = std::getenv("PYTHON_INTERNAL_BASE_URL");
    std::string pythonBaseUrl = pythonBase ? pythonBase : "http://127.0.0.1:8000";

    auto pythonClient = std::make_shared<PythonApiClient>(pythonBaseUrl);
    auto healthService = std::make_shared<HealthService>(pythonClient);
    auto documentService = std::make_shared<DocumentService>(pythonClient);
    auto sessionService = std::make_shared<SessionService>(pythonClient);
    auto chatService = std::make_shared<ChatService>(pythonClient);

    app().registerHandler(
        "/health",
        [healthService](const HttpRequestPtr&,
                        std::function<void(const HttpResponsePtr&)>&& callback) {
            healthService->handle(std::move(callback));
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
        [documentService](const HttpRequestPtr& req,
                          std::function<void(const HttpResponsePtr&)>&& callback) {
            documentService->uploadAndSubmit(req, std::move(callback));
        },
        {Post}
    );

    app().registerHandler(
        "/v1/sessions",
        [sessionService](const HttpRequestPtr& req,
                         std::function<void(const HttpResponsePtr&)>&& callback) {
            auto json = req->getJsonObject();
            if (!json) {
                Json::Value body(Json::objectValue);
                body["ok"] = false;
                body["error"] = "invalid json";

                auto resp = HttpResponse::newHttpJsonResponse(body);
                resp->setStatusCode(k400BadRequest);
                callback(resp);
                return;
            }
            sessionService->createSession(*json, std::move(callback));
        },
        {Post}
    );

    app().registerHandler(
        "/v1/sessions/{1}/messages",
        [chatService](const HttpRequestPtr& req,
                      std::function<void(const HttpResponsePtr&)>&& callback,
                      int sessionId) {
            auto json = req->getJsonObject();
            if (!json) {
                Json::Value body(Json::objectValue);
                body["ok"] = false;
                body["error"] = "invalid json";

                auto resp = HttpResponse::newHttpJsonResponse(body);
                resp->setStatusCode(k400BadRequest);
                callback(resp);
                return;
            }
            chatService->createUserMessageAndSubmitChat(sessionId, *json, std::move(callback));
        },
        {Post}
    );

    app().registerHandler(
        "/v1/sessions/{1}/messages",
        [sessionService](const HttpRequestPtr&,
                         std::function<void(const HttpResponsePtr&)>&& callback,
                         int sessionId) {
            sessionService->listMessages(sessionId, std::move(callback));
        },
        {Get}
    );

    app().loadConfigFile("config.json");
    app().run();
    return 0;
}