import hashlib


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()