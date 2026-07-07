"""Mock CyberdyneAuth (JWKS) + GitHub API server for local BDD runs.

Runs a real HTTP server so the Mnemosyne stack under test (API + worker
subprocesses) talks to controlled fixtures instead of the internet.
"""

import base64
import threading
import time
from typing import Any

import jwt
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Response

KID = "bdd-key"


def _b64uint(n: int) -> str:
    data = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class MockServices:
    """One FastAPI app hosting /.well-known/jwks.json and /github/* fixtures."""

    def __init__(self, port: int = 8765):
        self.port = port
        self.issuer = f"http://127.0.0.1:{port}"
        self.github_base = f"{self.issuer}/github"
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.fixture: dict[str, Any] = {}
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    # -- tokens ---------------------------------------------------------------

    def mint_token(
        self,
        subject: str = "bdd-user",
        *,
        entitlements: list[str] | None = None,
        is_admin: bool = False,
        scopes: str = "openid",
    ) -> str:
        pem = self._key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return jwt.encode(
            {
                "iss": self.issuer,
                "sub": subject,
                "exp": int(time.time()) + 3600,
                "scope": scopes,
                "is_admin": is_admin,
                "entitlements": entitlements if entitlements is not None else ["mnemosyne"],
            },
            pem,
            algorithm="RS256",
            headers={"kid": KID},
        )

    # -- app ------------------------------------------------------------------

    def build_app(self) -> FastAPI:
        app = FastAPI()
        numbers = self._key.public_key().public_numbers()

        @app.get("/.well-known/jwks.json")
        def jwks() -> dict:
            return {
                "keys": [
                    {
                        "kty": "RSA",
                        "kid": KID,
                        "use": "sig",
                        "alg": "RS256",
                        "n": _b64uint(numbers.n),
                        "e": _b64uint(numbers.e),
                    }
                ]
            }

        gh = self.fixture  # mutable: scenarios adjust it

        @app.get("/github/user")
        def user() -> dict:
            return {"login": gh.get("owner", "cyberdyne"), "type": "Organization"}

        @app.get("/github/user/repos")
        def user_repos() -> list:
            return gh.get("repos", [])

        @app.get("/github/issues")
        def probe_issues() -> list:
            return []

        @app.get("/github/rate_limit")
        def rate_limit() -> dict:
            return {"resources": {"core": {"limit": 5000, "remaining": 4999}}}

        @app.get("/github/repos/{owner}/{name}")
        def repo(owner: str, name: str) -> Any:
            for r in gh.get("repos", []):
                if r["full_name"] == f"{owner}/{name}":
                    return r
            return Response(status_code=404)

        @app.get("/github/repos/{owner}/{name}/git/trees/{branch}")
        def tree(owner: str, name: str, branch: str) -> dict:
            return {"tree": gh.get("tree", [])}

        @app.get("/github/repos/{owner}/{name}/contents/{path:path}")
        def contents(owner: str, name: str, path: str) -> Any:
            files = gh.get("files", {})
            if path not in files:
                return Response(status_code=404)
            encoded = base64.b64encode(files[path].encode()).decode()
            return {"encoding": "base64", "content": encoded}

        @app.get("/github/repos/{owner}/{name}/issues")
        def issues(owner: str, name: str) -> list:
            return gh.get("issues", [])

        @app.get("/github/repos/{owner}/{name}/pulls")
        def pulls(owner: str, name: str) -> list:
            return gh.get("pulls", [])

        @app.get("/github/repos/{owner}/{name}/pulls/{number}/reviews")
        def reviews(owner: str, name: str, number: int) -> list:
            return gh.get("reviews", {}).get(number, [])

        return app

    # -- lifecycle --------------------------------------------------------------

    def start(self) -> None:
        config = uvicorn.Config(
            self.build_app(), host="127.0.0.1", port=self.port, log_level="warning"
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        deadline = time.time() + 10
        while not self._server.started:
            if time.time() > deadline:
                raise RuntimeError("mock services failed to start")
            time.sleep(0.05)

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)


DEMO_REPO = "cyberdyne/matforge"

DEMO_FIXTURE: dict[str, Any] = {
    "owner": "cyberdyne",
    "repos": [
        {
            "id": 4242,
            "full_name": DEMO_REPO,
            "description": "MATLAB LLVM compiler",
            "visibility": "private",
            "default_branch": "main",
            "language": "C++",
            "archived": False,
            "updated_at": "2026-07-01T00:00:00Z",
        }
    ],
    "tree": [
        {"type": "blob", "path": "README.md", "sha": "r1", "size": 40},
        {"type": "blob", "path": "docs/gpu-backend.md", "sha": "d1", "size": 60},
        {"type": "blob", "path": "openspec/changes/add-gpu-backend/proposal.md", "sha": "o1", "size": 20},
        {"type": "blob", "path": "openspec/changes/add-gpu-backend/tasks.md", "sha": "o2", "size": 20},
        {"type": "blob", "path": "pyproject.toml", "sha": "p1", "size": 10},
        {"type": "blob", "path": "src/main.cpp", "sha": "c1", "size": 100},
    ],
    "files": {
        "README.md": "# Matforge\n\nA MATLAB LLVM compiler with GPU backends.",
        "docs/gpu-backend.md": "# GPU backend\n\nCUDA and Metal backends dispatch kernels.",
        "openspec/changes/add-gpu-backend/proposal.md": "# Proposal: add-gpu-backend",
        "openspec/changes/add-gpu-backend/tasks.md": "- [ ] 1.1 Add OpenCL device discovery",
    },
    "issues": [
        {
            "id": 1, "number": 42, "title": "Add OpenCL backend", "state": "closed",
            "user": {"login": "alice"}, "labels": [{"name": "feature"}], "assignees": [],
            "comments": 3, "created_at": "2026-06-01T00:00:00Z",
            "updated_at": "2026-06-05T00:00:00Z", "closed_at": "2026-06-05T00:00:00Z",
        },
        {
            "id": 2, "number": 57, "title": "Support GPUArray", "state": "open",
            "user": {"login": "bob"}, "labels": [{"name": "feature"}], "assignees": [],
            "comments": 0, "created_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:00Z",
        },
    ],
    "pulls": [
        {
            "id": 10, "number": 61, "title": "Refactor GPU backend abstraction",
            "state": "closed", "user": {"login": "bob"},
            "created_at": "2026-06-02T00:00:00Z", "merged_at": "2026-06-04T00:00:00Z",
            "closed_at": "2026-06-04T00:00:00Z",
        }
    ],
    "reviews": {
        61: [
            {"user": {"login": "carol"}, "state": "APPROVED",
             "submitted_at": "2026-06-03T00:00:00Z"}
        ]
    },
}
