import ipaddress
from urllib.parse import urlparse

import requests


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def should_bypass_proxy(url: str) -> bool:
    host = (urlparse(url or "").hostname or "").strip().lower()
    if not host:
        return False
    if host in _LOCAL_HOSTS:
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return ip.is_loopback or ip.is_private or ip.is_link_local


def request(method: str, url: str, **kwargs) -> requests.Response:
    if should_bypass_proxy(url):
        session = requests.Session()
        session.trust_env = False
        return session.request(method, url, **kwargs)

    return requests.request(method, url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request("POST", url, **kwargs)
