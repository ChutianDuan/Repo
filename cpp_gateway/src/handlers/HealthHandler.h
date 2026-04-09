#pragma once

#include "clients/PythonApiClient.h"
#include <drogon/drogon.h>
#include <memory>

class HealthService {
public:
    explicit HealthService(std::shared_ptr<PythonApiClient> pythonClient);

    void handle(
        std::function<void(const drogon::HttpResponsePtr&)>&& callback
    ) const;

private:
    std::shared_ptr<PythonApiClient> pythonClient_;
};