#include "ChatHandler.h"

#include <drogon/drogon.h>

using namespace drogon;

namespace {
HttpResponsePtr makeGatewayErrorResponse(HttpStatusCode status, const std::string& message) {
    Json::Value result(Json::objectValue);
    result["code"] = static_cast<int>(status);
    result["message"] = message;
    result["data"] = Json::nullValue;

    auto resp = HttpResponse::newHttpJsonResponse(result);
    resp->setStatusCode(status);
    return resp;
}

const Json::Value& responseDataOrSelf(const Json::Value& json) {
    if (json.isObject() && json.isMember("data") && !json["data"].isNull()) {
        return json["data"];
    }
    return json;
}
}  // namespace

ChatService::ChatService(std::shared_ptr<PythonApiClient> pythonClient)
    : pythonClient_(std::move(pythonClient)) {}

void ChatService::createUserMessageAndSubmitChat(
    int sessionId,
    const Json::Value& body,
    std::function<void(const HttpResponsePtr&)>&& callback
) {
    // body 约定:
    // {
    //   "content": "这份文档讲了什么？",
    //   "top_k": 3,
    //   "doc_id": 11,          // optional: omitted means global READY documents
    //   "doc_ids": [11, 12]    // optional: explicit document scope
    // }
    auto sharedCallback =
        std::make_shared<std::function<void(const HttpResponsePtr&)>>(std::move(callback));

    Json::Value createMessageBody;
    createMessageBody["role"] = "user";
    createMessageBody["content"] = body.get("content", "").asString();
    createMessageBody["status"] = "PENDING";

    pythonClient_->forwardJsonPost(
        "/internal/sessions/" + std::to_string(sessionId) + "/messages",
        createMessageBody,
        [this, sharedCallback, sessionId, body](const HttpResponsePtr& msgResp) mutable {
            if (msgResp->statusCode() >= 400) {
                (*sharedCallback)(msgResp);
                return;
            }

            auto msgJsonPtr = msgResp->getJsonObject();
            if (!msgJsonPtr || !(*msgJsonPtr).isMember("data")) {
                (*sharedCallback)(makeGatewayErrorResponse(
                    k502BadGateway,
                    "invalid response while creating user message"
                ));
                return;
            }

            auto msgJson = *msgJsonPtr;
            int userMessageId = msgJson["data"]["message_id"].asInt();

            Json::Value chatJobBody;
            chatJobBody["session_id"] = sessionId;
            chatJobBody["user_message_id"] = userMessageId;
            chatJobBody["top_k"] = body.get("top_k", 3).asInt();
            if (body.isMember("doc_id") && body["doc_id"].isInt() && body["doc_id"].asInt() > 0) {
                chatJobBody["doc_id"] = body["doc_id"].asInt();
            }
            if (body.isMember("doc_ids") && body["doc_ids"].isArray()) {
                chatJobBody["doc_ids"] = body["doc_ids"];
            }

            pythonClient_->forwardJsonPost(
                "/internal/jobs/chat",
                chatJobBody,
                [this, sharedCallback, sessionId, userMessageId](const HttpResponsePtr& chatResp) mutable {
                    if (chatResp->statusCode() >= 400) {
                        Json::Value updateStatusBody;
                        updateStatusBody["status"] = "FAILURE";

                        pythonClient_->forwardJsonPost(
                            "/internal/sessions/" + std::to_string(sessionId)
                                + "/messages/" + std::to_string(userMessageId) + "/status",
                            updateStatusBody,
                            [sharedCallback, chatResp](const HttpResponsePtr&) mutable {
                                (*sharedCallback)(chatResp);
                            }
                        );
                        return;
                    }

                    auto chatJsonPtr = chatResp->getJsonObject();
                    if (!chatJsonPtr) {
                        Json::Value updateStatusBody;
                        updateStatusBody["status"] = "FAILURE";

                        auto errorResp = makeGatewayErrorResponse(
                            k502BadGateway,
                            "invalid response while submitting chat task"
                        );

                        pythonClient_->forwardJsonPost(
                            "/internal/sessions/" + std::to_string(sessionId)
                                + "/messages/" + std::to_string(userMessageId) + "/status",
                            updateStatusBody,
                            [sharedCallback, errorResp](const HttpResponsePtr&) mutable {
                                (*sharedCallback)(errorResp);
                            }
                        );
                        return;
                    }

                    auto chatJson = *chatJsonPtr;
                    const Json::Value& chatData = responseDataOrSelf(chatJson);

                    Json::Value result;
                    result["code"] = 0;
                    result["message"] = "ok";
                    result["data"]["message_id"] = userMessageId;
                    result["data"]["task_id"] = chatData["task_id"];
                    result["data"]["db_task_id"] = chatData["db_task_id"];
                    result["data"]["state"] = chatData["state"];
                    result["data"]["status_url"] = chatData["status_url"];

                    auto resp = HttpResponse::newHttpJsonResponse(result);
                    (*sharedCallback)(resp);
                }
            );
        }
    );
}
