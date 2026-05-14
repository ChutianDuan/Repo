#include "StreamChatHandler.h"

#include <cstdlib>
#include <thread>
#include <utility>
#include <memory>

#include <json/json.h>

#include "clients/PythonApiClient.h"
#include "clients/PythonSSEClient.h"

using namespace drogon;

namespace {
int parseMaxConcurrentStreams() {
    const char* raw = std::getenv("GATEWAY_MAX_STREAMS");
    if (!raw || raw[0] == '\0') {
        return 64;
    }

    try {
        const int parsed = std::stoi(raw);
        return parsed > 0 ? parsed : 64;
    } catch (...) {
        return 64;
    }
}

std::string jsonToCompactString(const Json::Value& value) {
    Json::StreamWriterBuilder builder;
    builder["indentation"] = "";
    return Json::writeString(builder, value);
}
}  // namespace

struct StreamChatService::StreamSlotLease {
    explicit StreamSlotLease(std::shared_ptr<std::atomic<int>> activeStreams)
        : activeStreams_(std::move(activeStreams)) {}

    ~StreamSlotLease() {
        if (!activeStreams_) {
            return;
        }

        const int previous = activeStreams_->fetch_sub(1);
        if (previous <= 0) {
            activeStreams_->store(0);
        }
    }

private:
    std::shared_ptr<std::atomic<int>> activeStreams_;
};

StreamChatService::StreamChatService(
    std::shared_ptr<PythonSSEClient> pythonSSEClient,
    std::shared_ptr<PythonApiClient> pythonApiClient
)
    : pythonSSEClient_(std::move(pythonSSEClient)),
      pythonApiClient_(std::move(pythonApiClient)),
      maxConcurrentStreams_(parseMaxConcurrentStreams()),
      activeStreams_(std::make_shared<std::atomic<int>>(0)) {}

bool StreamChatService::validateRequestBody(const Json::Value& body, std::string& error) {
    if (!body.isObject()) {
        error = "request body must be a json object";
        return false;
    }

    if (!body.isMember("session_id") || !body["session_id"].isInt()) {
        error = "missing or invalid session_id";
        return false;
    }
    if (body.isMember("doc_id") && (!body["doc_id"].isInt() || body["doc_id"].asInt() <= 0)) {
        error = "invalid doc_id";
        return false;
    }
    if (body.isMember("doc_ids") && !body["doc_ids"].isArray()) {
        error = "invalid doc_ids";
        return false;
    }
    if (body.isMember("doc_ids") && body["doc_ids"].isArray()) {
        for (const auto& item : body["doc_ids"]) {
            if (!item.isInt() || item.asInt() <= 0) {
                error = "doc_ids must contain positive integers";
                return false;
            }
        }
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

HttpResponsePtr StreamChatService::buildJsonErrorResponse(
    int code,
    const std::string& message,
    HttpStatusCode status
) {
    Json::Value root;
    root["code"] = code;
    root["message"] = message;
    root["data"] = Json::nullValue;

    auto resp = HttpResponse::newHttpJsonResponse(root);
    resp->setStatusCode(status);
    return resp;
}

std::shared_ptr<StreamChatService::StreamSlotLease> StreamChatService::acquireStreamSlot() const {
    int current = activeStreams_->load();
    while (current < maxConcurrentStreams_) {
        if (activeStreams_->compare_exchange_weak(current, current + 1)) {
            return std::make_shared<StreamSlotLease>(activeStreams_);
        }
    }

    return nullptr;
}

void StreamChatService::startStreamResponse(
    const Json::Value& body,
    std::shared_ptr<StreamSlotLease> streamSlot,
    std::function<void(const HttpResponsePtr&)>&& callback
) {
    auto resp = HttpResponse::newAsyncStreamResponse(
        [client = pythonSSEClient_, body, streamSlot = std::move(streamSlot)](
            ResponseStreamPtr stream
        ) mutable {
            std::thread([
                client,
                body,
                stream = std::move(stream),
                streamSlot = std::move(streamSlot)
            ]() mutable {
                (void)streamSlot;
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
        callback(buildJsonErrorResponse(
            4001,
            "request body must be valid json",
            k400BadRequest
        ));
        return;
    }

    Json::Value body = *jsonPtr;
    std::string error;
    if (!validateRequestBody(body, error)) {
        callback(buildJsonErrorResponse(4002, error, k400BadRequest));
        return;
    }

    auto streamSlot = acquireStreamSlot();
    if (!streamSlot) {
        callback(buildJsonErrorResponse(
            4290,
            "too many active streams",
            k429TooManyRequests
        ));
        return;
    }

    if (body.isMember("user_message_id") && body["user_message_id"].isInt()) {
        startStreamResponse(body, std::move(streamSlot), std::move(callback));
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
        [this, sharedCallback, body, streamSlot = std::move(streamSlot)](
            const HttpResponsePtr& msgResp
        ) mutable {
            if (msgResp->statusCode() >= 400) {
                (*sharedCallback)(msgResp);
                return;
            }

            auto msgJsonPtr = msgResp->getJsonObject();
            if (!msgJsonPtr || !(*msgJsonPtr).isMember("data")) {
                (*sharedCallback)(buildJsonErrorResponse(
                    4003,
                    "invalid response while creating user message",
                    k400BadRequest
                ));
                return;
            }

            Json::Value nextBody = body;
            nextBody["user_message_id"] = (*msgJsonPtr)["data"]["message_id"].asInt();
            nextBody.removeMember("content");
            startStreamResponse(nextBody, std::move(streamSlot), std::move(*sharedCallback));
        }
    );
}
