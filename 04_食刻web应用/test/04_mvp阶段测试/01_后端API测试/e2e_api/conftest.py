# -*- coding: utf-8 -*-
"""pytest 共享配置与 fixture。

环境变量：
- TEST_BASE_URL：API 根地址，默认 http://127.0.0.1:8000
- TEST_ENV=production：切换到公网 http://118.178.131.84
- TEST_HOME_URL：前端首页，默认与 API 同主机的 80 端口
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import requests

# e2e_api → 01_后端API测试 → 04_mvp阶段测试 → test → 04_食刻web应用
TESTS_DIR = Path(__file__).resolve().parent
API_TEST_ROOT = TESTS_DIR.parent
PROJECT_ROOT = API_TEST_ROOT.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FIXTURES_DIR = TESTS_DIR / "fixtures"
REPORTS_DIR = TESTS_DIR / "reports"


def _load_dotenv_file(env_path: Path) -> None:
    """加载单个 .env 文件（不覆盖已有环境变量）。"""
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _load_dotenv_test() -> None:
    """优先加载测试目录 .env.test，其次 backend/.env.test。"""
    _load_dotenv_file(API_TEST_ROOT / ".env.test")
    _load_dotenv_file(BACKEND_DIR / ".env.test")


_load_dotenv_test()


def pytest_configure(config: pytest.Config) -> None:
    """注册 marker，并确保报告目录存在。"""
    config.addinivalue_line("markers", "smoke: 冒烟测试（健康检查 + 基本功能）")
    config.addinivalue_line("markers", "full: 完整测试（含语义等较慢用例）")
    config.addinivalue_line("markers", "filter: 硬过滤相关")
    config.addinivalue_line("markers", "semantic: 语义检索相关")
    config.addinivalue_line("markers", "expand: 扩召回相关")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="覆盖 TEST_BASE_URL，例如 http://127.0.0.1:8000",
    )


@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
    """解析被测 API 根地址。"""
    cli = pytestconfig.getoption("--base-url")
    if cli:
        return str(cli).rstrip("/")
    if os.getenv("TEST_ENV", "").strip().lower() == "production":
        return os.getenv("TEST_BASE_URL", "http://118.178.131.84").rstrip("/")
    return os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def home_url(base_url: str) -> str:
    """前端首页地址。"""
    explicit = os.getenv("TEST_HOME_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    # 本地后端 8000 时，首页通常走 80；公网同主机 /
    if base_url.endswith(":8000"):
        return base_url.replace(":8000", "")
    return base_url


@pytest.fixture(scope="session")
def api_client(base_url: str) -> "ApiClient":
    """封装 requests 的共享 API 客户端。"""
    timeout = float(os.getenv("TEST_TIMEOUT", "30"))
    return ApiClient(base_url=base_url, timeout=timeout)


@pytest.fixture(scope="session")
def query_samples() -> list[dict[str, Any]]:
    path = FIXTURES_DIR / "query_samples.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """失败时把最近一次 API 调用详情写入 reports/。"""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    client = item.funcargs.get("api_client") if hasattr(item, "funcargs") else None
    if not isinstance(client, ApiClient):
        return
    client.dump_failure_log(test_name=item.nodeid, error=str(report.longrepr))


class ApiClient:
    """简单 HTTP 客户端，记录最近请求便于失败排查。"""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.last_call: dict[str, Any] | None = None

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        absolute: bool = False,
    ) -> requests.Response:
        url = path if absolute else f"{self.base_url}{path}"
        started = time.perf_counter()
        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                json=json_body,
                params=params,
                timeout=self.timeout,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            body_preview: Any
            try:
                body_preview = resp.json()
            except Exception:  # noqa: BLE001
                body_preview = (resp.text or "")[:2000]
            self.last_call = {
                "method": method.upper(),
                "url": url,
                "request_json": json_body,
                "params": params,
                "status_code": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "response": body_preview,
                "time": datetime.now(timezone.utc).isoformat(),
            }
            return resp
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self.last_call = {
                "method": method.upper(),
                "url": url,
                "request_json": json_body,
                "params": params,
                "status_code": None,
                "elapsed_ms": elapsed_ms,
                "response": None,
                "error": str(exc),
                "time": datetime.now(timezone.utc).isoformat(),
            }
            raise

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, json_body: dict[str, Any] | None = None, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, json_body=json_body, **kwargs)

    def recommend(
        self,
        query_text: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 3,
    ) -> tuple[requests.Response, dict[str, Any]]:
        payload = {
            "query_text": query_text,
            "filters": filters or {},
            "top_k": top_k,
        }
        resp = self.post("/api/recommend", json_body=payload)
        data: dict[str, Any] = {}
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            data = {}
        return resp, data

    def dump_failure_log(self, test_name: str, error: str) -> Path:
        """将失败请求详情写入 reports/。"""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        safe = (
            test_name.replace("/", "_")
            .replace("::", "__")
            .replace(" ", "_")
        )
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORTS_DIR / f"fail_{safe}_{stamp}.json"
        payload = {
            "test": test_name,
            "error": error,
            "last_call": self.last_call,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
