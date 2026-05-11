import sys
import types


try:
    import dotenv  # noqa: F401
except ModuleNotFoundError:
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = fake_dotenv


try:
    import pymysql  # noqa: F401
except ModuleNotFoundError:
    fake_pymysql = types.ModuleType("pymysql")
    fake_pymysql.cursors = types.SimpleNamespace(DictCursor=object)

    def _connect(*args, **kwargs):
        raise RuntimeError("fake pymysql connection is not available in tests")

    fake_pymysql.connect = _connect
    sys.modules["pymysql"] = fake_pymysql


try:
    import faiss  # noqa: F401
except ModuleNotFoundError:
    fake_faiss = types.ModuleType("faiss")

    class _FakeIndexFlatIP:
        def __init__(self, dim):
            self.dim = dim

        def add(self, vectors):
            self.vectors = vectors

        def search(self, query, top_k):
            raise RuntimeError("fake faiss search is not implemented in tests")

    def _read_index(*args, **kwargs):
        raise RuntimeError("fake faiss read_index is not implemented in tests")

    fake_faiss.IndexFlatIP = _FakeIndexFlatIP
    fake_faiss.read_index = _read_index
    fake_faiss.write_index = lambda *args, **kwargs: None
    sys.modules["faiss"] = fake_faiss
