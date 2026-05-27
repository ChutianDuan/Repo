import asyncio
import aiohttp
import time
import statistics

# =========================
# vLLM OpenAI API Config
# =========================

BASE_URL = "http://127.0.0.1:9000/v1/chat/completions"

HEADERS = {
    "Authorization": "Bearer test-key-123",
    "Content-Type": "application/json"
}

PAYLOAD = {
    "model": "local-llm",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "请详细介绍一下 Transformer 的核心结构、Self-Attention 原理、KV Cache 的作用，以及它在大语言模型中的应用。"
        }
    ],
    "max_tokens": 256,
    "temperature": 0.7,
    "stream": False
}

# =========================
# Stress Test Config
# =========================

TOTAL_REQUESTS = 100
CONCURRENCY = 10
TIMEOUT = 300

# =========================
# Metrics
# =========================

latencies = []
success_count = 0
fail_count = 0

# =========================
# Worker
# =========================


async def worker(session, semaphore, request_id):

    global success_count
    global fail_count

    async with semaphore:

        start_time = time.perf_counter()

        try:

            async with session.post(
                BASE_URL,
                headers=HEADERS,
                json=PAYLOAD,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as response:

                response_text = await response.text()

                end_time = time.perf_counter()

                latency = end_time - start_time

                latencies.append(latency)

                if response.status == 200:
                    success_count += 1
                    print(
                        f"[SUCCESS] "
                        f"id={request_id} "
                        f"status={response.status} "
                        f"latency={latency:.2f}s"
                    )

                else:
                    fail_count += 1
                    print(
                        f"[FAILED] "
                        f"id={request_id} "
                        f"status={response.status} "
                        f"latency={latency:.2f}s"
                    )

                    print(response_text[:300])

        except Exception as e:

            fail_count += 1

            end_time = time.perf_counter()

            latency = end_time - start_time

            print(
                f"[ERROR] "
                f"id={request_id} "
                f"latency={latency:.2f}s "
                f"error={str(e)}"
            )


# =========================
# Main
# =========================

async def main():

    semaphore = asyncio.Semaphore(CONCURRENCY)

    connector = aiohttp.TCPConnector(limit=0)

    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        tasks = []

        global_start = time.perf_counter()

        for i in range(TOTAL_REQUESTS):

            task = asyncio.create_task(
                worker(session, semaphore, i)
            )

            tasks.append(task)

        await asyncio.gather(*tasks)

        global_end = time.perf_counter()

    # =========================
    # Statistics
    # =========================

    total_time = global_end - global_start

    print("\n")
    print("=" * 60)
    print("vLLM Stress Test Result")
    print("=" * 60)

    print(f"Total Requests      : {TOTAL_REQUESTS}")
    print(f"Concurrency         : {CONCURRENCY}")

    print(f"Success Requests    : {success_count}")
    print(f"Failed Requests     : {fail_count}")

    print(f"Total Time          : {total_time:.2f}s")

    if len(latencies) > 0:

        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        p50 = statistics.median(latencies)

        if len(latencies) >= 20:
            p95 = statistics.quantiles(latencies, n=100)[94]
            p99 = statistics.quantiles(latencies, n=100)[98]
        else:
            p95 = max_latency
            p99 = max_latency

        rps = TOTAL_REQUESTS / total_time

        print("\nLatency Statistics")
        print("-" * 60)

        print(f"Average Latency     : {avg_latency:.2f}s")
        print(f"Min Latency         : {min_latency:.2f}s")
        print(f"Max Latency         : {max_latency:.2f}s")

        print(f"P50 Latency         : {p50:.2f}s")
        print(f"P95 Latency         : {p95:.2f}s")
        print(f"P99 Latency         : {p99:.2f}s")

        print("\nThroughput")
        print("-" * 60)

        print(f"Requests/sec        : {rps:.2f}")

    print("=" * 60)


# =========================
# Entry
# =========================

if __name__ == "__main__":

    asyncio.run(main())