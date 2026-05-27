from python_rag.utils.http_client import should_bypass_proxy


def test_should_bypass_proxy_for_local_and_private_urls():
    assert should_bypass_proxy("http://127.0.0.1:9000/v1/chat/completions")
    assert should_bypass_proxy("http://0.0.0.0:9000/v1/chat/completions")
    assert should_bypass_proxy("http://localhost:9000/v1/chat/completions")
    assert should_bypass_proxy("http://192.168.1.10:9000/v1/chat/completions")
    assert should_bypass_proxy("http://10.0.0.5:9000/v1/chat/completions")


def test_should_not_bypass_proxy_for_public_urls():
    assert not should_bypass_proxy("https://api.openai.com/v1/chat/completions")
