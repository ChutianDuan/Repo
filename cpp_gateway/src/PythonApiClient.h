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

private:
    std::string baseUrl_;
    drogon::HttpClientPtr client_;
};