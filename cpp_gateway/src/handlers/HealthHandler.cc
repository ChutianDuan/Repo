#include "HealthHandler.h"

#include <json/json.h>
#include <atomic>
#include <exception>
#include <memory>
#include <mutex>
#include <string>
#include <functional>

using namespace drogon;

namespace {
struct ProbeState {
    std::atomic<int> pending{3};

    bool mysqlOk{false};
    bool redisOk{false};
    bool pythonOk{false};

    std::string mysqlErr;
    std::string redisErr;
    std::string pythonErr;

    std::mutex mu;
};
}  // namespace

HealthService::HealthService(std::shared_ptr<PythonApiClient> pythonClient)
    : pythonClient_(std::move(pythonClient)) {}

void HealthService::handle(
    std::function<void(const HttpResponsePtr&)>&& callback
) const {
    auto state = std::make_shared<ProbeState>();

    auto finalize = std::make_shared<std::function<void()>>();
    *finalize = [state, callback = std::move(callback)]() mutable {
        if (--state->pending != 0) {
            return;
        }

        Json::Value json;
        json["ok"] = state->mysqlOk && state->redisOk && state->pythonOk;

        json["mysql"]["ok"] = state->mysqlOk;
        json["mysql"]["error"] = state->mysqlErr;

        json["redis"]["ok"] = state->redisOk;
        json["redis"]["error"] = state->redisErr;

        json["python"]["ok"] = state->pythonOk;
        json["python"]["error"] = state->pythonErr;

        auto resp = HttpResponse::newHttpJsonResponse(json);
        resp->setStatusCode(json["ok"].asBool() ? k200OK : k503ServiceUnavailable);
        callback(resp);
    };

    // 1) MySQL
    try {
        auto dbClient = app().getDbClient("default");
        dbClient->execSqlAsync(
            "select 1",
            [state, finalize](const drogon::orm::Result&) {
                {
                    std::lock_guard<std::mutex> lock(state->mu);
                    state->mysqlOk = true;
                }
                (*finalize)();
            },
            [state, finalize](const drogon::orm::DrogonDbException& e) {
                {
                    std::lock_guard<std::mutex> lock(state->mu);
                    state->mysqlOk = false;
                    state->mysqlErr = e.base().what();
                }
                (*finalize)();
            }
        );
    } catch (const std::exception& e) {
        {
            std::lock_guard<std::mutex> lock(state->mu);
            state->mysqlOk = false;
            state->mysqlErr = e.what();
        }
        (*finalize)();
    }

    // 2) Redis
    try {
        auto redisClient = app().getRedisClient("default");
        redisClient->execCommandAsync(
            [state, finalize](const drogon::nosql::RedisResult& r) {
                {
                    std::lock_guard<std::mutex> lock(state->mu);

                    // 对 health check 来说，成功回调已足够说明 Redis 可用
                    state->redisOk = true;
                    state->redisErr.clear();

                    // 可选：保留调试信息
                    // try {
                    //     auto pong = r.asString();
                    //     if (pong != "PONG") {
                    //         state->redisErr = "redis responded but payload was: " + pong;
                    //     }
                    // } catch (...) {
                    //     // 忽略类型差异，health 仍视为成功
                    // }
                }
                (*finalize)();
            },
            [state, finalize](const std::exception& e) {
                {
                    std::lock_guard<std::mutex> lock(state->mu);
                    state->redisOk = false;
                    state->redisErr = e.what();
                }
                (*finalize)();
            },
            "PING"
        );
    } catch (const std::exception& e) {
        {
            std::lock_guard<std::mutex> lock(state->mu);
            state->redisOk = false;
            state->redisErr = e.what();
        }
        (*finalize)();
    }

    // 3) Python internal
    pythonClient_->getInternalHealth(
        [state, finalize](bool ok, const std::string&, const std::string& err) {
            {
                std::lock_guard<std::mutex> lock(state->mu);
                state->pythonOk = ok;
                state->pythonErr = err;
            }
            (*finalize)();
        }
    );
}