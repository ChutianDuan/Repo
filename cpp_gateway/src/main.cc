#include <cstdlib>
#include <functional>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <drogon/drogon.h>

#include "clients/PythonApiClient.h"
#include "clients/PythonSSEClient.h"
#include "handlers/ChatHandler.h"
#include "handlers/DocumentHandler.h"
#include "handlers/HealthHandler.h"
#include "handlers/SessionHandler.h"
#include "handlers/StreamChatHandler.h"
#include "common/GatewaySecurity.h"

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

void applyCorsHeaders(const HttpRequestPtr& req, const HttpResponsePtr& resp) {
    if (!resp) {
        return;
    }

    const auto origin = req ? req->getHeader("Origin") : std::string();
    resp->addHeader("Access-Control-Allow-Origin", origin.empty() ? "*" : origin);
    resp->addHeader("Vary", "Origin");
    resp->addHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");

    const auto requestedHeaders = req ? req->getHeader("Access-Control-Request-Headers") : std::string();
    if (!requestedHeaders.empty()) {
        resp->addHeader("Access-Control-Allow-Headers", requestedHeaders);
    } else {
        resp->addHeader(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-API-Key, X-User-Id, X-Requested-With"
        );
    }

    resp->addHeader("Access-Control-Max-Age", "86400");
}

std::function<void(const HttpResponsePtr&)> makeCorsCallback(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback
) {
    return [req, callback = std::move(callback)](const HttpResponsePtr& resp) mutable {
        applyCorsHeaders(req, resp);
        callback(resp);
    };
}

HttpResponsePtr makeOptionsResponse(const HttpRequestPtr& req) {
    auto resp = HttpResponse::newHttpResponse();
    resp->setStatusCode(k204NoContent);
    resp->setBody("");
    applyCorsHeaders(req, resp);
    return resp;
}

void runSecured(
    const std::shared_ptr<GatewaySecurity>& security,
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback,
    GatewaySecurity::Next&& next
) {
    security->authorize(req, makeCorsCallback(req, std::move(callback)), std::move(next));
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
    auto streamChatHandler = std::make_shared<StreamChatService>(pythonSSEClient, pythonClient);
    auto gatewaySecurity = std::make_shared<GatewaySecurity>(GatewaySecurityConfig::fromEnv());

    app().registerHandler(
        "/health",
        [healthHandler](const HttpRequestPtr& req,
                        std::function<void(const HttpResponsePtr&)>&& callback) {
            healthHandler->handle(makeCorsCallback(req, std::move(callback)));
        },
        {Get}
    );

    app().registerHandler(
        "/health",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/tasks/{1}",
        [gatewaySecurity, pythonClient](const HttpRequestPtr& req,
                                        std::function<void(const HttpResponsePtr&)>&& callback,
                                        const std::string& taskId) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [pythonClient, taskId](GatewaySecurity::ResponseCallback&& secureCallback) {
                    pythonClient->proxyTaskStatus(taskId, std::move(secureCallback));
                }
            );
        },
        {Get}
    );

    app().registerHandler(
        "/v1/tasks/{1}",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback,
           const std::string&) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/tasks",
        [gatewaySecurity, pythonClient](const HttpRequestPtr& req,
                                        std::function<void(const HttpResponsePtr&)>&& callback) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [pythonClient, req](GatewaySecurity::ResponseCallback&& secureCallback) {
                    std::string path = "/internal/tasks";
                    std::vector<std::string> params;
                    const auto limit = req->getParameter("limit");
                    const auto state = req->getParameter("state");
                    if (!limit.empty()) {
                        params.push_back("limit=" + limit);
                    }
                    if (!state.empty()) {
                        params.push_back("state=" + state);
                    }
                    if (!params.empty()) {
                        path += "?";
                        for (size_t i = 0; i < params.size(); ++i) {
                            if (i > 0) {
                                path += "&";
                            }
                            path += params[i];
                        }
                    }
                    pythonClient->forwardGet(path, std::move(secureCallback));
                }
            );
        },
        {Get}
    );

    app().registerHandler(
        "/v1/tasks",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/documents",
        [gatewaySecurity, documentHandler](const HttpRequestPtr& req,
                                           std::function<void(const HttpResponsePtr&)>&& callback) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [documentHandler, req](GatewaySecurity::ResponseCallback&& secureCallback) {
                    documentHandler->uploadAndSubmit(req, std::move(secureCallback));
                }
            );
        },
        {Post}
    );

    app().registerHandler(
        "/v1/documents",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/documents/{1}",
        [gatewaySecurity, pythonClient](const HttpRequestPtr& req,
                                        std::function<void(const HttpResponsePtr&)>&& callback,
                                        int docId) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [pythonClient, docId](GatewaySecurity::ResponseCallback&& secureCallback) {
                    pythonClient->forwardGet(
                        "/internal/documents/" + std::to_string(docId),
                        std::move(secureCallback)
                    );
                }
            );
        },
        {Get}
    );

    app().registerHandler(
        "/v1/documents/{1}",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback,
           int) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/users",
        [gatewaySecurity, pythonClient](const HttpRequestPtr& req,
                                        std::function<void(const HttpResponsePtr&)>&& callback) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [pythonClient, req](GatewaySecurity::ResponseCallback&& secureCallback) {
                    auto json = req->getJsonObject();
                    if (!json) {
                        secureCallback(makeBadRequestResponse("invalid json"));
                        return;
                    }
                    pythonClient->forwardJsonPost("/internal/users", *json, std::move(secureCallback));
                }
            );
        },
        {Post}
    );

    app().registerHandler(
        "/v1/users",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/users/latest",
        [gatewaySecurity, pythonClient](const HttpRequestPtr& req,
                                        std::function<void(const HttpResponsePtr&)>&& callback) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [pythonClient, req](GatewaySecurity::ResponseCallback&& secureCallback) {
                    std::string path = "/internal/users/latest";
                    const auto limit = req->getParameter("limit");
                    if (!limit.empty()) {
                        path += "?limit=" + limit;
                    }
                    pythonClient->forwardGet(path, std::move(secureCallback));
                }
            );
        },
        {Get}
    );

    app().registerHandler(
        "/v1/users/latest",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/sessions",
        [gatewaySecurity, sessionHandler](const HttpRequestPtr& req,
                                          std::function<void(const HttpResponsePtr&)>&& callback) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [sessionHandler, req](GatewaySecurity::ResponseCallback&& secureCallback) {
                    auto json = req->getJsonObject();
                    if (!json) {
                        secureCallback(makeBadRequestResponse("invalid json"));
                        return;
                    }
                    sessionHandler->createSession(*json, std::move(secureCallback));
                }
            );
        },
        {Post}
    );

    app().registerHandler(
        "/v1/sessions",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/sessions/{1}/messages",
        [gatewaySecurity, chatHandler](const HttpRequestPtr& req,
                                       std::function<void(const HttpResponsePtr&)>&& callback,
                                       int sessionId) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [chatHandler, req, sessionId](GatewaySecurity::ResponseCallback&& secureCallback) {
                    auto json = req->getJsonObject();
                    if (!json) {
                        secureCallback(makeBadRequestResponse("invalid json"));
                        return;
                    }
                    chatHandler->createUserMessageAndSubmitChat(
                        sessionId,
                        *json,
                        std::move(secureCallback)
                    );
                }
            );
        },
        {Post}
    );

    app().registerHandler(
        "/v1/sessions/{1}/messages",
        [gatewaySecurity, sessionHandler](const HttpRequestPtr& req,
                                          std::function<void(const HttpResponsePtr&)>&& callback,
                                          int sessionId) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [sessionHandler, sessionId](GatewaySecurity::ResponseCallback&& secureCallback) {
                    sessionHandler->listMessages(sessionId, std::move(secureCallback));
                }
            );
        },
        {Get}
    );

    app().registerHandler(
        "/v1/sessions/{1}/messages",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback,
           int) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/chat/stream",
        [gatewaySecurity, streamChatHandler](const HttpRequestPtr& req,
                                             std::function<void(const HttpResponsePtr&)>&& callback) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [streamChatHandler, req](GatewaySecurity::ResponseCallback&& secureCallback) {
                    streamChatHandler->handleStream(req, std::move(secureCallback));
                }
            );
        },
        {Post}
    );

    app().registerHandler(
        "/v1/chat/stream",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().registerHandler(
        "/v1/monitor/overview",
        [gatewaySecurity, pythonClient](const HttpRequestPtr& req,
                                        std::function<void(const HttpResponsePtr&)>&& callback) {
            runSecured(
                gatewaySecurity,
                req,
                std::move(callback),
                [pythonClient](GatewaySecurity::ResponseCallback&& secureCallback) {
                    pythonClient->forwardGet(
                        "/internal/monitor/overview",
                        std::move(secureCallback)
                    );
                }
            );
        },
        {Get}
    );

    app().registerHandler(
        "/v1/monitor/overview",
        [](const HttpRequestPtr& req,
           std::function<void(const HttpResponsePtr&)>&& callback) {
            callback(makeOptionsResponse(req));
        },
        {Options}
    );

    app().loadConfigFile("config.json");
    app().run();
    return 0;
}
