#include <cstdlib>
#include <memory>
#include <string>

#include <drogon/drogon.h>

#include "DocumentService.h"
#include "HealthService.h"
#include "PythonApiClient.h"

using namespace drogon;

int main() {
    const char* pythonBase = std::getenv("PYTHON_INTERNAL_BASE_URL");
    std::string pythonBaseUrl = pythonBase ? pythonBase : "http://127.0.0.1:8000";

    auto pythonClient = std::make_shared<PythonApiClient>(pythonBaseUrl);
    auto healthService = std::make_shared<HealthService>(pythonClient);
    auto documentService = std::make_shared<DocumentService>(pythonClient);

    app().registerHandler(
        "/health",
        [healthService](const HttpRequestPtr&,
                        std::function<void(const HttpResponsePtr&)>&& callback) {
            healthService->handle(std::move(callback));
        },
        {Get}
    );

    app().registerHandler(
        "/v1/tasks/{1}",
        [pythonClient](const HttpRequestPtr&,
                       std::function<void(const HttpResponsePtr&)>&& callback,
                       const std::string& taskId) {
            pythonClient->proxyTaskStatus(taskId, std::move(callback));
        },
        {Get}
    );

    app().registerHandler(
        "/v1/documents",
        [documentService](const HttpRequestPtr& req,
                          std::function<void(const HttpResponsePtr&)>&& callback) {
            documentService->uploadAndSubmit(req, std::move(callback));
        },
        {Post}
    );

    app().loadConfigFile("config.json");
    app().run();
    return 0;
}