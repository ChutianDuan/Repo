#include "ChatHandler.h"

#include <drogon/drogon.h>

using namespace drogon;

namespace {
HttpResponsePtr makeGatewayErrorResponse(HttpStatusCode status, const std::string& message) {
    Json::Value result(Json::objectValue);
    result["code"] = static_cast<int>(status);
    result["message"] = message;

    auto resp = HttpResponse::newHttpJsonResponse(result);
    resp->setStatusCode(status);
    return resp;
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
    //   "doc_id": 11,
    //   "content": "这份文档讲了什么？",
    //   "top_k": 3
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
            chatJobBody["doc_id"] = body.get("doc_id", 0).asInt();
            chatJobBody["user_message_id"] = userMessageId;
            chatJobBody["top_k"] = body.get("top_k", 3).asInt();

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

                    Json::Value result;
                    result["code"] = 0;
                    result["message"] = "ok";
                    result["data"]["message_id"] = userMessageId;
                    result["data"]["task_id"] = chatJson["task_id"];
                    result["data"]["db_task_id"] = chatJson["db_task_id"];
                    result["data"]["state"] = chatJson["state"];
                    result["data"]["status_url"] = chatJson["status_url"];

                    auto resp = HttpResponse::newHttpJsonResponse(result);
                    (*sharedCallback)(resp);
                }
            );
        }
    );
}
