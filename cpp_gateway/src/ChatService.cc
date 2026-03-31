#include "ChatService.h"
#include <drogon/drogon.h>

using namespace drogon;

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

    Json::Value createMessageBody;
    createMessageBody["role"] = "user";
    createMessageBody["content"] = body.get("content", "").asString();
    createMessageBody["status"] = "SUCCESS";

    pythonClient_->forwardJsonPost(
        "/internal/sessions/" + std::to_string(sessionId) + "/messages",
        createMessageBody,
        [this, callback = std::move(callback), sessionId, body](const HttpResponsePtr& msgResp) mutable {
            if (msgResp->statusCode() >= 400) {
                callback(msgResp);
                return;
            }

            auto msgJson = *msgResp->getJsonObject();
            int userMessageId = msgJson["data"]["message_id"].asInt();

            Json::Value chatJobBody;
            chatJobBody["session_id"] = sessionId;
            chatJobBody["doc_id"] = body.get("doc_id", 0).asInt();
            chatJobBody["user_message_id"] = userMessageId;
            chatJobBody["top_k"] = body.get("top_k", 3).asInt();

            pythonClient_->forwardJsonPost(
                "/internal/jobs/chat",
                chatJobBody,
                [callback = std::move(callback), userMessageId](const HttpResponsePtr& chatResp) mutable {
                    if (chatResp->statusCode() >= 400) {
                        callback(chatResp);
                        return;
                    }

                    auto chatJson = *chatResp->getJsonObject();

                    Json::Value result;
                    result["code"] = 0;
                    result["message"] = "ok";
                    result["data"]["message_id"] = userMessageId;
                    result["data"]["task_id"] = chatJson["task_id"];
                    result["data"]["db_task_id"] = chatJson["db_task_id"];
                    result["data"]["state"] = chatJson["state"];
                    result["data"]["status_url"] = chatJson["status_url"];

                    auto resp = HttpResponse::newHttpJsonResponse(result);
                    callback(resp);
                }
            );
        }
    );
}