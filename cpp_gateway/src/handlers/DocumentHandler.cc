#include "DocumentHandler.h"

#include <cstdlib>
#include <algorithm>
#include <cctype>
#include <chrono>
#include <drogon/drogon.h>
#include <drogon/utils/Utilities.h>

#include <filesystem>
#include <fstream>
#include <random>
#include <sstream>
#include <string>

using namespace drogon;

namespace fs = std::filesystem;

namespace {
std::string fileExtension(std::string name) {
    auto pos = name.rfind('.');
    if (pos == std::string::npos) {
        return "";
    }

    auto ext = name.substr(pos + 1);
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return ext;
}

bool isSupportedTextExtension(const std::string& ext) {
    return ext == "md" || ext == "txt" || ext == "json"
        || ext == "csv" || ext == "pdf" || ext == "docx";
}

std::string supportedDocumentTypesText() {
    return ".md, .txt, .json, .csv, .pdf, .docx";
}

std::string buildUniqueSuffix() {
    const auto now = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    std::random_device rd;
    std::mt19937_64 gen(rd());
    std::uniform_int_distribution<unsigned long long> dist;

    std::ostringstream oss;
    oss << std::hex << now << dist(gen);
    return oss.str();
}

fs::path getRepoRoot() {
    if (const char* envRepoRoot = std::getenv("REPO_ROOT"); envRepoRoot && envRepoRoot[0] != '\0') {
        return fs::path(envRepoRoot);
    }

    return fs::current_path().parent_path();
}

fs::path getUploadDir() {
    const char* envUploadDir = std::getenv("UPLOAD_DIR");
    fs::path uploadDir = (envUploadDir && envUploadDir[0] != '\0')
        ? fs::path(envUploadDir)
        : fs::path("./data/uploads");

    if (uploadDir.is_relative()) {
        uploadDir = getRepoRoot() / uploadDir;
    }

    return uploadDir.lexically_normal();
}

void tryDeleteFile(const std::string& storagePath) {
    try {
        if (!storagePath.empty()) {
            fs::remove(storagePath);
        }
    } catch (...) {
    }
}
}  // namespace

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

std::string DocumentService::buildStoredFileName(
    long long userId,
    const std::string& originalName,
    const std::string& sha256
) {
    const auto clean = sanitizeFileName(originalName);
    const auto ext = fs::path(clean).extension().string();
    const auto shaPrefix = sha256.substr(0, std::min<size_t>(sha256.size(), 16));
    return std::to_string(userId) + "_" + shaPrefix + "_" + buildUniqueSuffix() + ext;
}

std::string DocumentService::guessMime(const HttpFile& file) {
    const auto ext = fileExtension(file.getFileName());
    if (ext.empty()) {
        return "application/octet-stream";
    }

    if (ext == "md") return "text/markdown";
    if (ext == "txt") return "text/plain";
    if (ext == "json") return "application/json";
    if (ext == "csv") return "text/csv";
    if (ext == "pdf") return "application/pdf";
    if (ext == "docx") {
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    }
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
        fs::create_directories(getUploadDir());
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
    const std::string ext = fileExtension(originalName);
    if (!isSupportedTextExtension(ext)) {
        Json::Value json;
        json["code"] = 400;
        json["message"] =
            "unsupported file type; currently supported: " + supportedDocumentTypesText();
        auto resp = HttpResponse::newHttpJsonResponse(json);
        resp->setStatusCode(k400BadRequest);
        (*sharedCallback)(resp);
        return;
    }
    const std::string mime = guessMime(file);
    const std::string sha256 = sha256Hex(std::string(file.fileContent()));
    const auto sizeBytes = static_cast<long long>(file.fileContent().size());
    const std::string storedName = buildStoredFileName(userId, originalName, sha256);
    const std::string storagePath = (getUploadDir() / storedName).string();

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

    auto dbClient = app().getDbClient("default");
    dbClient->execSqlAsync(
        R"(
            INSERT INTO documents (
                user_id, filename, mime, sha256, size_bytes, storage_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        )",
        [this, dbClient, sharedCallback, originalName, storagePath]
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
                [dbClient, sharedCallback, docId, originalName, storagePath]
                (bool ok, const Json::Value& pythonJson, const std::string& err) mutable {
                    if (!ok) {
                        tryDeleteFile(storagePath);
                        dbClient->execSqlAsync(
                            "DELETE FROM documents WHERE id=?",
                            [sharedCallback, docId, err](const drogon::orm::Result&) mutable {
                                Json::Value json;
                                json["code"] = 502;
                                json["message"] = err;
                                json["doc_id"] = Json::Int64(docId);
                                json["rolled_back"] = true;
                                auto resp = HttpResponse::newHttpJsonResponse(json);
                                resp->setStatusCode(k502BadGateway);
                                (*sharedCallback)(resp);
                            },
                            [sharedCallback, docId, err](const drogon::orm::DrogonDbException& e) mutable {
                                Json::Value json;
                                json["code"] = 502;
                                json["message"] = err + "; rollback document cleanup failed: " + e.base().what();
                                json["doc_id"] = Json::Int64(docId);
                                json["rolled_back"] = false;
                                auto resp = HttpResponse::newHttpJsonResponse(json);
                                resp->setStatusCode(k502BadGateway);
                                (*sharedCallback)(resp);
                            },
                            docId
                        );
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
        [sharedCallback, storagePath](const drogon::orm::DrogonDbException& e) mutable {
            tryDeleteFile(storagePath);

            const std::string dbError = e.base().what();
            Json::Value json;
            json["code"] = dbError.find("Duplicate entry") != std::string::npos ? 409 : 500;
            json["message"] = dbError.find("Duplicate entry") != std::string::npos
                ? "document already exists for this user"
                : std::string("db insert document failed: ") + dbError;
            auto resp = HttpResponse::newHttpJsonResponse(json);
            resp->setStatusCode(
                dbError.find("Duplicate entry") != std::string::npos
                    ? k409Conflict
                    : k500InternalServerError
            );
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
