#pragma once

#include <drogon/drogon.h>
#include <functional>
#include <memory>
#include <string>

class PythonApiClient {
public:
    explicit PythonApiClient(const std::string& baseUrl);

    void getInternalHealth(
        std::function<void(bool ok, const std::string& body, const std::string& err)> cb
    ) const;

    void proxyTaskStatus(
        const std::string& taskId,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    ) const;

    void submitIngestJob(
        long long docId,
        std::function<void(bool ok, const Json::Value& json, const std::string& err)> cb
    ) const;

    void forwardGet(
        const std::string& path,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

    void forwardJsonPost(
        const std::string& path,
        const Json::Value& body,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

    void forwardMultipartPost(
        const drogon::HttpRequestPtr& req,
        const std::string& path,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    );

private:
    std::string baseUrl_;
    drogon::HttpClientPtr client_;
};