#include "DocumentHandler.h"

#include <drogon/drogon.h>
#include <drogon/utils/Utilities.h>

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

using namespace drogon;

namespace fs = std::filesystem;

DocumentService::DocumentService(std::shared_ptr<PythonApiClient> pythonClient)
    : pythonClient_(std::move(pythonClient)) {}

std::string DocumentService::sanitizeFileName(const std::string& name) {
    std::string out = name;
    for (auto& ch : out) {
        if (ch == '/' || ch == '\\' || ch == ':' || ch == '*' ||
            ch == '?' || ch == '"' || ch == '<' || ch == '>' || ch == '|') {
            ch = '_';
        }
    }
    if (out.empty()) {
        out = "upload.bin";
    }
    return out;
}

std::string DocumentService::buildStoredFileName(const std::string& originalName) {
    auto clean = sanitizeFileName(originalName);
    auto now = std::to_string(trantor::Date::now().microSecondsSinceEpoch());
    return now + "_" + clean;
}

std::string DocumentService::guessMime(const HttpFile& file) {
    auto name = file.getFileName();
    auto pos = name.rfind('.');
    if (pos == std::string::npos) {
        return "application/octet-stream";
    }

    auto ext = name.substr(pos + 1);
    if (ext == "md") return "text/markdown";
    if (ext == "txt") return "text/plain";
    if (ext == "json") return "application/json";
    if (ext == "pdf") return "application/pdf";
    return "application/octet-stream";
}

std::string DocumentService::sha256Hex(const std::string& data) {
    return utils::getSha256(data);
}

void DocumentService::uploadAndSubmit(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback
) const {
    auto sharedCallback =
        std::make_shared<std::function<void(const HttpResponsePtr&)>>(std::move(callback));

    MultiPartParser parser;
    if (parser.parse(req) != 0) {
        Json::Value json;
        json["code"] = 400;
        json["message"] = "invalid multipart form data";
        auto resp = HttpResponse::newHttpJsonResponse(json);
        resp->setStatusCode(k400BadRequest);
        (*sharedCallback)(resp);
        return;
    }

    const auto& files = parser.getFiles();
    if (files.size() != 1) {
        Json::Value json;
        json["code"] = 400;
        json["message"] = "exactly one file is required";
        auto resp = HttpResponse::newHttpJsonResponse(json);
        resp->setStatusCode(k400BadRequest);
        (*sharedCallback)(resp);
        return;
    }

    const auto& file = files[0];

    long long userId = 1;
    try {
        auto userIdStr = parser.getParameter<std::string>("user_id");
        if (!userIdStr.empty()) {
            userId = std::stoll(userIdStr);
        }
    } catch (...) {
        userId = 1;
    }

    if (userId <= 0) {
        Json::Value json;
        json["code"] = 400;
        json["message"] = "user_id must be positive";
        auto resp = HttpResponse::newHttpJsonResponse(json);
        resp->setStatusCode(k400BadRequest);
        (*sharedCallback)(resp);
        return;
    }

    try {
        fs::create_directories("./data/uploads");
    } catch (const std::exception& e) {
        Json::Value json;
        json["code"] = 500;
        json["message"] = std::string("failed to create upload dir: ") + e.what();
        auto resp = HttpResponse::newHttpJsonResponse(json);
        resp->setStatusCode(k500InternalServerError);
        (*sharedCallback)(resp);
        return;
    }

    const std::string originalName = sanitizeFileName(file.getFileName());
    const std::string storedName = buildStoredFileName(originalName);
    const std::string storagePath = "./data/uploads/" + storedName;

    // Drogon 官方文件上传示例里是 parse 后拿 HttpFile，再保存。这里为兼容我们自定义命名，
    // 直接把 file.fileContent() 写到目标路径。multipart 解析流程本身来自官方示例和 wiki。 :contentReference[oaicite:3]{index=3}
    try {
        std::ofstream ofs(storagePath, std::ios::binary);
        if (!ofs) {
            throw std::runtime_error("cannot open target file");
        }
        ofs.write(file.fileContent().data(), static_cast<std::streamsize>(file.fileContent().size()));
        ofs.close();
    } catch (const std::exception& e) {
        Json::Value json;
        json["code"] = 500;
        json["message"] = std::string("failed to save file: ") + e.what();
        auto resp = HttpResponse::newHttpJsonResponse(json);
        resp->setStatusCode(k500InternalServerError);
        (*sharedCallback)(resp);
        return;
    }

    const std::string mime = guessMime(file);
    const std::string sha256 = sha256Hex(std::string(file.fileContent()));
    const auto sizeBytes = static_cast<long long>(file.fileContent().size());

    auto dbClient = app().getDbClient("default");
    dbClient->execSqlAsync(
        R"(
            INSERT INTO documents (
                user_id, filename, mime, sha256, size_bytes, storage_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        )",
        [this, sharedCallback, originalName]
        (const drogon::orm::Result& r) mutable {
            long long docId = 0;
            try {
                docId = r.insertId();
            } catch (...) {
                Json::Value json;
                json["code"] = 500;
                json["message"] = "inserted document but failed to read doc_id";
                auto resp = HttpResponse::newHttpJsonResponse(json);
                resp->setStatusCode(k500InternalServerError);
                (*sharedCallback)(resp);
                return;
            }

            pythonClient_->submitIngestJob(
                docId,
                [sharedCallback, docId, originalName]
                (bool ok, const Json::Value& pythonJson, const std::string& err) mutable {
                    if (!ok) {
                        Json::Value json;
                        json["code"] = 502;
                        json["message"] = err;
                        json["doc_id"] = Json::Int64(docId);
                        auto resp = HttpResponse::newHttpJsonResponse(json);
                        resp->setStatusCode(k502BadGateway);
                        (*sharedCallback)(resp);
                        return;
                    }

                    Json::Value out;
                    out["doc_id"] = Json::Int64(docId);
                    out["filename"] = originalName;
                    out["task_id"] = pythonJson["task_id"];
                    out["db_task_id"] = pythonJson["db_task_id"];
                    out["state"] = pythonJson["state"];
                    out["status_url"] = "/v1/tasks/" + pythonJson["task_id"].asString();

                    auto resp = HttpResponse::newHttpJsonResponse(out);
                    resp->setStatusCode(k200OK);
                    (*sharedCallback)(resp);
                }
            );
        },
        [sharedCallback](const drogon::orm::DrogonDbException& e) mutable {
            Json::Value json;
            json["code"] = 500;
            json["message"] = std::string("db insert document failed: ") + e.base().what();
            auto resp = HttpResponse::newHttpJsonResponse(json);
            resp->setStatusCode(k500InternalServerError);
            (*sharedCallback)(resp);
        },
        userId,
        originalName,
        mime,
        sha256,
        sizeBytes,
        storagePath,
        "UPLOADED"
    );
}
