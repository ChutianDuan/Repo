import os
import uuid

from python_rag.config import REPO_ROOT, STORAGE_ROOT, UPLOAD_DIR


def ensure_storage_dirs():
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def build_upload_path(filename):
    ensure_storage_dirs()
    safe_name = filename.replace("/", "_").replace("\\", "_")
    unique_name = "{0}_{1}".format(uuid.uuid4().hex, safe_name)
    return os.path.join(UPLOAD_DIR, unique_name)


def save_bytes_to_path(content, path):
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def resolve_storage_path(path):
    if not path:
        return path

    if os.path.isabs(path):
        return path

    normalized_path = os.path.normpath(path)
    candidate_roots = (
        REPO_ROOT,
        os.path.join(REPO_ROOT, "cpp_gateway"),
    )

    for root in candidate_roots:
        candidate = os.path.abspath(os.path.join(root, normalized_path))
        if os.path.exists(candidate):
            return candidate

    return os.path.abspath(os.path.join(REPO_ROOT, normalized_path))
