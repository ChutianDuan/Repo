#include "PythonApiClient.h"

#include <json/json.h>

using namespace drogon;

namespace {
HttpResponsePtr buildForwardedJsonResponse(const HttpResponsePtr& resp) {
    auto out = HttpResponse::newHttpResponse();
    out->setStatusCode(resp->statusCode());
    out->setContentTypeCode(CT_APPLICATION_JSON);
    out->setBody(std::string(resp->body()));
    return out;
}

HttpResponsePtr buildGatewayErrorJsonResponse(HttpStatusCode status, const std::string& message) {
    Json::Value obj(Json::objectValue);
    obj["code"] = static_cast<int>(status);
    obj["message"] = message;
    obj["data"] = Json::nullValue;

    auto resp = HttpResponse::newHttpJsonResponse(obj);
    resp->setStatusCode(status);
    return resp;
}
}  // namespace

PythonApiClient::PythonApiClient(const std::string& baseUrl)
    : baseUrl_(baseUrl),
      client_(HttpClient::newHttpClient(baseUrl_)) {}

drogon::HttpClientPtr PythonApiClient::makeClient() const {
    return client_;
}

void PythonApiClient::getInternalHealth(
    std::function<void(bool ok, const std::string& body, const std::string& err)> cb
) const {
    auto client = makeClient();
    auto req = HttpRequest::newHttpRequest();
    req->setMethod(Get);
    req->setPath("/internal/health");

    client->sendRequest(req,
        [client, cb](ReqResult result, const HttpResponsePtr& resp) {
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
    auto client = makeClient();
    auto req = HttpRequest::newHttpRequest();
    req->setMethod(Get);
    req->setPath("/internal/tasks/" + taskId);

    client->sendRequest(req,
        [client, callback = std::move(callback)](ReqResult result, const HttpResponsePtr& resp) mutable {
            if (result != ReqResult::Ok || !resp) {
                callback(buildGatewayErrorJsonResponse(
                    k502BadGateway,
                    "gateway failed to request python task status"
                ));
                return;
            }

            callback(buildForwardedJsonResponse(resp));
        });
}

void PythonApiClient::submitIngestJob(
    long long docId,
    std::function<void(bool ok, const Json::Value& json, const std::string& err)> cb
) const {
    auto client = makeClient();
    Json::Value body;
    body["doc_id"] = Json::Int64(docId);

    auto req = HttpRequest::newHttpJsonRequest(body);
    req->setMethod(Post);
    req->setPath("/internal/jobs/ingest");

    client->sendRequest(req,
        [client, cb](ReqResult result, const HttpResponsePtr& resp) {
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

void PythonApiClient::forwardDelete(
    const std::string& path,
    std::function<void(const HttpResponsePtr&)>&& callback
) {
    auto client = makeClient();
    auto req = HttpRequest::newHttpRequest();
    req->setMethod(Delete);
    req->setPath(path);

    client->sendRequest(req, [client, callback = std::move(callback)](
        ReqResult result,
        const HttpResponsePtr& resp
    ) mutable {
        if (result != ReqResult::Ok || !resp) {
            callback(buildGatewayErrorJsonResponse(
                k502BadGateway,
                "python service unavailable"
            ));
            return;
        }
        callback(buildForwardedJsonResponse(resp));
    });
}

void PythonApiClient::forwardJsonPost(
    const std::string& path,
    const Json::Value& body,
    std::function<void(const HttpResponsePtr&)>&& callback
) {
    auto client = makeClient();
    auto req = HttpRequest::newHttpJsonRequest(body);
    req->setMethod(Post);
    req->setPath(path);

    client->sendRequest(req, [client, callback = std::move(callback)](
        ReqResult result,
        const HttpResponsePtr& resp
    ) {
        if (result != ReqResult::Ok || !resp) {
            callback(buildGatewayErrorJsonResponse(
                k502BadGateway,
                "python service unavailable"
            ));
            return;
        }
        callback(buildForwardedJsonResponse(resp));
    });
}

void PythonApiClient::forwardGet(
    const std::string& path,
    std::function<void(const HttpResponsePtr&)>&& callback
) {
    auto client = makeClient();
    auto req = HttpRequest::newHttpRequest();
    req->setMethod(Get);
    req->setPath(path);

    client->sendRequest(
        req,
        [client, callback = std::move(callback)](
            ReqResult result,
            const HttpResponsePtr& resp
        ) mutable {
            if (result != ReqResult::Ok || !resp) {
                callback(buildGatewayErrorJsonResponse(
                    k502BadGateway,
                    "python service unavailable"
                ));
                return;
            }

            callback(buildForwardedJsonResponse(resp));
        }
    );
}
