#pragma once

#include <functional>
#include <memory>
#include <string>

#include <json/json.h>

class PythonSSEClient {
public:
    using ChunkCallback = std::function<bool(const std::string&)>;
    using FinishCallback = std::function<void(bool ok, long httpCode, const std::string& errorMessage)>;

    explicit PythonSSEClient(std::string baseUrl);

    // 同步阻塞调用：建议在独立线程里执行
    void postStream(
        const std::string& path,
        const Json::Value& body,
        const ChunkCallback& onChunk,
        const FinishCallback& onFinish
    ) const;

private:
    std::string baseUrl_;

    static std::string joinUrl(const std::string& baseUrl, const std::string& path);
    static std::string jsonToString(const Json::Value& value);
};