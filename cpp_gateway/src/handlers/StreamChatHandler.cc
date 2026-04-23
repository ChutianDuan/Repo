#include "StreamChatHandler.h"

#include <thread>
#include <utility>
#include <memory>

#include <json/json.h>

#include "clients/PythonApiClient.h"
#include "clients/PythonSSEClient.h"

using namespace drogon;

namespace {
std::string jsonToCompactString(const Json::Value& value) {
    Json::StreamWriterBuilder builder;
    builder["indentation"] = "";
    return Json::writeString(builder, value);
}
}  // namespace

StreamChatService::StreamChatService(
    std::shared_ptr<PythonSSEClient> pythonSSEClient,
    std::shared_ptr<PythonApiClient> pythonApiClient
)
    : pythonSSEClient_(std::move(pythonSSEClient)),
      pythonApiClient_(std::move(pythonApiClient)) {}

bool StreamChatService::validateRequestBody(const Json::Value& body, std::string& error) {
    if (!body.isObject()) {
        error = "request body must be a json object";
        return false;
    }

    if (!body.isMember("session_id") || !body["session_id"].isInt()) {
        error = "missing or invalid session_id";
        return false;
    }
    if (!body.isMember("doc_id") || !body["doc_id"].isInt()) {
        error = "missing or invalid doc_id";
        return false;
    }
    const bool hasUserMessageId = body.isMember("user_message_id") && body["user_message_id"].isInt();
    const bool hasContent = body.isMember("content") && body["content"].isString()
        && !body["content"].asString().empty();
    if (!hasUserMessageId && !hasContent) {
        error = "missing user_message_id or content";
        return false;
    }

    if (body.isMember("top_k") && !body["top_k"].isInt()) {
        error = "invalid top_k";
        return false;
    }

    return true;
}

std::string StreamChatService::buildSseErrorEvent(const std::string& message) {
    Json::Value root;
    root["type"] = "error";
    root["message"] = message;
    return "data: " + jsonToCompactString(root) + "\n\n";
}

HttpResponsePtr StreamChatService::buildJsonErrorResponse(int code, const std::string& message) {
    Json::Value root;
    root["code"] = code;
    root["message"] = message;
    root["data"] = Json::nullValue;

    auto resp = HttpResponse::newHttpJsonResponse(root);
    resp->setStatusCode(k400BadRequest);
    return resp;
}

void StreamChatService::startStreamResponse(
    const Json::Value& body,
    std::function<void(const HttpResponsePtr&)>&& callback
) {
    auto resp = HttpResponse::newAsyncStreamResponse(
        [client = pythonSSEClient_, body](ResponseStreamPtr stream) mutable {
            std::thread([client, body, stream = std::move(stream)]() mutable {
                auto sharedStream = std::shared_ptr<drogon::ResponseStream>(std::move(stream));

                client->postStream(
                    "/internal/chat/stream",
                    body,
                    [sharedStream](const std::string& chunk) -> bool {
                        return sharedStream->send(chunk);
                    },
                    [sharedStream](bool ok, long httpCode, const std::string& errorMessage) mutable {
                        if (!ok) {
                            const std::string msg = errorMessage.empty()
                                ? ("gateway upstream stream failed, http=" + std::to_string(httpCode))
                                : errorMessage;
                            sharedStream->send(buildSseErrorEvent(msg));
                        }
                        sharedStream->close();
                    }
                );
            }).detach();
        },
        true
    );

    resp->addHeader("Content-Type", "text/event-stream");
    resp->addHeader("Cache-Control", "no-cache");
    resp->addHeader("Connection", "keep-alive");
    resp->addHeader("X-Accel-Buffering", "no");
    resp->setExpiredTime(0);

    callback(resp);
}

void StreamChatService::handleStream(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback
) {
    auto jsonPtr = req->getJsonObject();
    if (!jsonPtr) {
        callback(buildJsonErrorResponse(4001, "request body must be valid json"));
        return;
    }

    Json::Value body = *jsonPtr;
    std::string error;
    if (!validateRequestBody(body, error)) {
        callback(buildJsonErrorResponse(4002, error));
        return;
    }

    if (body.isMember("user_message_id") && body["user_message_id"].isInt()) {
        startStreamResponse(body, std::move(callback));
        return;
    }

    auto sharedCallback =
        std::make_shared<std::function<void(const HttpResponsePtr&)>>(std::move(callback));

    Json::Value createMessageBody;
    createMessageBody["role"] = "user";
    createMessageBody["content"] = body["content"].asString();
    createMessageBody["status"] = "PENDING";

    const int sessionId = body["session_id"].asInt();
    pythonApiClient_->forwardJsonPost(
        "/internal/sessions/" + std::to_string(sessionId) + "/messages",
        createMessageBody,
        [this, sharedCallback, body](const HttpResponsePtr& msgResp) mutable {
            if (msgResp->statusCode() >= 400) {
                (*sharedCallback)(msgResp);
                return;
            }

            auto msgJsonPtr = msgResp->getJsonObject();
            if (!msgJsonPtr || !(*msgJsonPtr).isMember("data")) {
                (*sharedCallback)(buildJsonErrorResponse(
                    4003,
                    "invalid response while creating user message"
                ));
                return;
            }

            Json::Value nextBody = body;
            nextBody["user_message_id"] = (*msgJsonPtr)["data"]["message_id"].asInt();
            nextBody.removeMember("content");
            startStreamResponse(nextBody, std::move(*sharedCallback));
        }
    );
}
