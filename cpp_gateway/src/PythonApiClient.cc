#include "PythonApiClient.h"

#include <json/json.h>

using namespace drogon;

PythonApiClient::PythonApiClient(const std::string& baseUrl)
    : baseUrl_(baseUrl),
      client_(HttpClient::newHttpClient(baseUrl)) {}

void PythonApiClient::getInternalHealth(
    std::function<void(bool ok, const std::string& body, const std::string& err)> cb
) const {
    auto req = HttpRequest::newHttpRequest();
    req->setMethod(Get);
    req->setPath("/internal/health");

    client_->sendRequest(req,
        [cb](ReqResult result, const HttpResponsePtr& resp) {
            if (result != ReqResult::Ok || !resp) {
                cb(false, "", "python health request failed");
                return;
            }

            const bool ok = (resp->statusCode() == k200OK);
            cb(ok, std::string(resp->body()), "");
        });
}

void PythonApiClient::proxyTaskStatus(
    const std::string& taskId,
    std::function<void(const HttpResponsePtr&)>&& callback
) const {
    auto req = HttpRequest::newHttpRequest();
    req->setMethod(Get);
    req->setPath("/internal/tasks/" + taskId);

    client_->sendRequest(req,
        [callback = std::move(callback)](ReqResult result, const HttpResponsePtr& resp) mutable {
            if (result != ReqResult::Ok || !resp) {
                Json::Value json;
                json["code"] = 502;
                json["message"] = "gateway failed to request python task status";
                auto out = HttpResponse::newHttpJsonResponse(json);
                out->setStatusCode(k502BadGateway);
                callback(out);
                return;
            }

            auto out = HttpResponse::newHttpResponse();
            out->setStatusCode(resp->statusCode());
            out->setContentTypeCode(CT_APPLICATION_JSON);
            out->setBody(std::string(resp->body()));
            callback(out);
        });
}

void PythonApiClient::submitIngestJob(
    long long docId,
    std::function<void(bool ok, const Json::Value& json, const std::string& err)> cb
) const {
    Json::Value body;
    body["doc_id"] = Json::Int64(docId);

    auto req = HttpRequest::newHttpJsonRequest(body);
    req->setMethod(Post);
    req->setPath("/internal/jobs/ingest");

    client_->sendRequest(req,
        [cb](ReqResult result, const HttpResponsePtr& resp) {
            if (result != ReqResult::Ok || !resp) {
                cb(false, Json::Value(), "python ingest request failed");
                return;
            }

            auto jsonPtr = resp->getJsonObject();
            if (!jsonPtr) {
                cb(false, Json::Value(), "python ingest response is not valid json");
                return;
            }

            const bool ok = (resp->statusCode() == k200OK);
            cb(ok, *jsonPtr, ok ? "" : "python ingest returned non-200");
        });
}