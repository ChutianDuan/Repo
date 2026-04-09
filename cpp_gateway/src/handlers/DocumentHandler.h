#pragma once

#include "clients/PythonApiClient.h"

#include <drogon/drogon.h>
#include <memory>
#include <string>

class DocumentService {
public:
    explicit DocumentService(std::shared_ptr<PythonApiClient> pythonClient);

    void uploadAndSubmit(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    ) const;

private:
    std::shared_ptr<PythonApiClient> pythonClient_;

    static std::string sanitizeFileName(const std::string& name);
    static std::string buildStoredFileName(const std::string& originalName);
    static std::string guessMime(const drogon::HttpFile& file);
    static std::string sha256Hex(const std::string& data);
};