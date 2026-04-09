#include "PythonSSEClient.h"

#include <curl/curl.h>
#include <mutex>
#include <sstream>
#include <string>

namespace {
struct CurlWriteContext {
    PythonSSEClient::ChunkCallback onChunk;
    std::string localError;
};

size_t writeCallback(char* ptr, size_t size, size_t nmemb, void* userdata) {
    const size_t total = size * nmemb;
    if (total == 0 || userdata == nullptr) {
        return 0;
    }

    auto* ctx = static_cast<CurlWriteContext*>(userdata);
    std::string chunk(ptr, total);

    if (!ctx->onChunk) {
        ctx->localError = "missing onChunk callback";
        return 0;
    }

    const bool ok = ctx->onChunk(chunk);
    if (!ok) {
        ctx->localError = "downstream stream closed";
        return 0;  // 让 curl 停止读取
    }

    return total;
}

void ensureCurlGlobalInit() {
    static std::once_flag once;
    std::call_once(once, []() {
        curl_global_init(CURL_GLOBAL_DEFAULT);
    });
}
}  // namespace

PythonSSEClient::PythonSSEClient(std::string baseUrl)
    : baseUrl_(std::move(baseUrl)) {}

std::string PythonSSEClient::joinUrl(const std::string& baseUrl, const std::string& path) {
    if (baseUrl.empty()) {
        return path;
    }
    if (path.empty()) {
        return baseUrl;
    }

    const bool baseEndsWithSlash = baseUrl.back() == '/';
    const bool pathStartsWithSlash = path.front() == '/';

    if (baseEndsWithSlash && pathStartsWithSlash) {
        return baseUrl + path.substr(1);
    }
    if (!baseEndsWithSlash && !pathStartsWithSlash) {
        return baseUrl + "/" + path;
    }
    return baseUrl + path;
}

std::string PythonSSEClient::jsonToString(const Json::Value& value) {
    Json::StreamWriterBuilder builder;
    builder["indentation"] = "";
    return Json::writeString(builder, value);
}

void PythonSSEClient::postStream(
    const std::string& path,
    const Json::Value& body,
    const ChunkCallback& onChunk,
    const FinishCallback& onFinish
) const {
    ensureCurlGlobalInit();

    const std::string url = joinUrl(baseUrl_, path);
    const std::string bodyStr = jsonToString(body);

    CURL* curl = curl_easy_init();
    if (!curl) {
        if (onFinish) {
            onFinish(false, 0, "curl_easy_init failed");
        }
        return;
    }

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    headers = curl_slist_append(headers, "Accept: text/event-stream");
    headers = curl_slist_append(headers, "Cache-Control: no-cache");

    CurlWriteContext writeCtx{onChunk, ""};

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, bodyStr.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(bodyStr.size()));

    // SSE 常见设置
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &writeCtx);
    curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 1L);

    // 仅设置连接超时，不设总超时，避免长连接 SSE 被整体超时截断
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 10L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 0L);

    // 降低缓冲
    curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 1024L);

    CURLcode rc = curl_easy_perform(curl);

    long httpCode = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpCode);

    std::string errorMessage;
    bool ok = true;

    if (rc != CURLE_OK) {
        ok = false;
        if (!writeCtx.localError.empty()) {
            errorMessage = writeCtx.localError;
        } else {
            errorMessage = curl_easy_strerror(rc);
        }
    } else if (httpCode >= 400) {
        ok = false;
        std::ostringstream oss;
        oss << "upstream http error: " << httpCode;
        errorMessage = oss.str();
    }

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (onFinish) {
        onFinish(ok, httpCode, errorMessage);
    }
}