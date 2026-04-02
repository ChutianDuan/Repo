from python_rag.services.llm_service import generate_from_messages

messages = [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "只回复：你好"},
]

print(generate_from_messages(messages))