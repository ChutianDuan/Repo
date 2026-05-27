import asyncio
import aiohttp
import json
import time
import statistics

# =========================================
# Config
# =========================================

URL = "http://127.0.0.1:9000/v1/chat/completions"

HEADERS = {
    "Authorization": "Bearer test-key-123",
    "Content-Type": "application/json"
}

PAYLOAD = {
    "model": "local-llm",
    "messages": [
        {
            "role": "user",
            "content": "请详细介绍 Transformer、Self-Attention、KV Cache 和 MoE。"
        }
    ],
    "max_tokens": 256,
    "temperature": 0.7,
    "stream": True
}

TOTAL_REQUESTS = 20
CONCURRENCY = 5

# =========================================
# Metrics
# =========================================

ttft_list = []
e2e_list = []
tokens_per_sec_list = []

success_count = 0
fail_count = 0

# =========================================
# Worker
# =========================================


async def worker(session, semaphore, idx):

    global success_count
    global fail_count

    async with semaphore:

        start_time = time.perf_counter()

        first_token_time = None

        generated_tokens = 0

        try:

            async with session.post(
                URL,
                headers=HEADERS,
                json=PAYLOAD
            ) as response:

                async for line in response.content:

                    now = time.perf_counter()

                    decoded = line.decode("utf-8").strip()

                    if not decoded:
                        continue

                    if decoded.startswith("data: "):

                        data_str = decoded[6:]

                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)

                            delta = (
                                data["choices"][0]
                                .get("delta", {})
                                .get("content", "")
                            )

                            if delta:

                                generated_tokens += 1

                                if first_token_time is None:
                                    first_token_time = now

                        except Exception:
                            pass

            end_time = time.perf_counter()

            # ==========================
            # Metrics
            # ==========================

            e2e_latency = end_time - start_time

            if first_token_time is not None:

                ttft = first_token_time - start_time

                decode_time = end_time - first_token_time

                if decode_time > 0:
                    tokens_per_sec = (
                        generated_tokens / decode_time
                    )
                else:
                    tokens_per_sec = 0

                ttft_list.append(ttft)

                tokens_per_sec_list.append(tokens_per_sec)

                print(
                    f"[{idx}] "
                    f"TTFT={ttft:.2f}s "
                    f"E2E={e2e_latency:.2f}s "
                    f"Tokens={generated_tokens} "
                    f"Tok/s={tokens_per_sec:.2f}"
                )

            e2e_list.append(e2e_latency)

            success_count += 1

        except Exception as e:

            fail_count += 1

            print(f"[ERROR] {idx} {e}")


# =========================================
# Main
# =========================================

async def main():

    semaphore = asyncio.Semaphore(CONCURRENCY)

    connector = aiohttp.TCPConnector(limit=0)

    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        tasks = []

        total_start = time.perf_counter()

        for i in range(TOTAL_REQUESTS):

            tasks.append(
                asyncio.create_task(
                    worker(session, semaphore, i)
                )
            )

        await asyncio.gather(*tasks)

        total_end = time.perf_counter()

    # =====================================
    # Summary
    # =====================================

    total_time = total_end - total_start

    print("\n")
    print("=" * 60)
    print("vLLM TTFT Benchmark")
    print("=" * 60)

    print(f"Total Requests     : {TOTAL_REQUESTS}")
    print(f"Concurrency        : {CONCURRENCY}")

    print(f"Success             : {success_count}")
    print(f"Failed              : {fail_count}")

    print(f"Total Time          : {total_time:.2f}s")

    if ttft_list:

        print("\nTTFT")
        print("-" * 60)

        print(
            f"Avg TTFT           : "
            f"{statistics.mean(ttft_list):.2f}s"
        )

        print(
            f"P95 TTFT           : "
            f"{statistics.quantiles(ttft_list, n=100)[94]:.2f}s"
        )

    if e2e_list:

        print("\nE2E Latency")
        print("-" * 60)

        print(
            f"Avg E2E            : "
            f"{statistics.mean(e2e_list):.2f}s"
        )

    if tokens_per_sec_list:

        print("\nDecode Throughput")
        print("-" * 60)

        print(
            f"Avg Tokens/s       : "
            f"{statistics.mean(tokens_per_sec_list):.2f}"
        )

    print("=" * 60)


# =========================================
# Entry
# =========================================

if __name__ == "__main__":

    asyncio.run(main())