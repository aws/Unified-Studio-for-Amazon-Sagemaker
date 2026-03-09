"""
Mock API handlers for Account Pool Factory UI.
Called by mock-server.py to handle /api/* routes.
"""

import json
import time
from data import PROFILES, IDC_USERS, ACCOUNTS, PORTAL_URL, create_project, get_project_status


def handle(method, path, body):
    """Route a request and return (status_code, response_dict)."""

    # ── Project Creator endpoints ────────────────────────────────────────────

    if method == "GET" and path == "/api/projects/profiles":
        pool_profiles = [p for p in PROFILES if p["hasPool"]]
        return 200, {"profiles": pool_profiles}

    if method == "GET" and path.startswith("/api/projects/owners"):
        q = path.split("search=")[-1].lower() if "search=" in path else ""
        results = [
            u for u in IDC_USERS
            if not q or q in u["name"].lower() or (u["email"] and q in u["email"].lower())
        ]
        return 200, {"owners": results[:8]}

    if method == "POST" and path == "/api/projects":
        data = body or {}
        project_id = create_project(
            data.get("name", "unnamed"),
            data.get("region", "us-east-2"),
            data.get("ownerId", ""),
            data.get("profileId", ""),
        )
        return 200, {"projectId": project_id, "portalUrl": PORTAL_URL}

    if method == "GET" and path.startswith("/api/projects/") and "/status" in path:
        project_id = path.split("/api/projects/")[1].replace("/status", "")
        project = get_project_status(project_id)
        if not project:
            return 404, {"error": "Project not found"}
        return 200, project

    # ── Pool Console endpoints ───────────────────────────────────────────────

    if method == "GET" and path == "/api/pool/summary":
        summary = {}
        for acc in ACCOUNTS:
            pool = acc["poolName"]
            state = acc["state"]
            if pool not in summary:
                summary[pool] = {"AVAILABLE": 0, "ASSIGNED": 0, "SETTING_UP": 0,
                                 "CLEANING": 0, "FAILED": 0, "ORPHANED": 0}
            summary[pool][state] = summary[pool].get(state, 0) + 1
        pools = [{"poolName": k, "counts": v} for k, v in summary.items()]
        return 200, {"pools": pools, "lastReconciled": "2026-03-09T10:00:00Z"}

    if method == "GET" and (path == "/api/pool/accounts" or path.startswith("/api/pool/accounts?")):
        params = {}
        if "?" in path:
            for kv in path.split("?")[1].split("&"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    params[k] = v
        results = list(ACCOUNTS)
        if params.get("state"):
            results = [a for a in results if a["state"] == params["state"]]
        if params.get("poolName"):
            results = [a for a in results if a["poolName"] == params["poolName"]]
        if params.get("search"):
            q = params["search"].lower()
            results = [a for a in results
                       if q in a["accountId"]
                       or q in a.get("projectId", "").lower()
                       or q in a["accountName"].lower()
                       or q in a.get("projectName", "").lower()]
        return 200, {"accounts": results, "total": len(results)}

    if method == "GET" and path.startswith("/api/pool/accounts/"):
        account_id = path.split("/api/pool/accounts/")[1].split("?")[0]
        acc = next((a for a in ACCOUNTS if a["accountId"] == account_id), None)
        if not acc:
            return 404, {"error": "Account not found"}
        return 200, acc

    if method == "POST" and path == "/api/pool/replenish":
        data = body or {}
        pool = data.get("poolName", "all pools")
        return 200, {"status": "triggered", "message": f"Replenishment triggered for {pool}",
                     "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    if method == "POST" and path == "/api/pool/reconcile":
        data = body or {}
        dry = data.get("dryRun", True)
        return 200, {"status": "SUCCESS", "dryRun": dry,
                     "summary": {"totalScanned": 8, "healthy": 6, "markedFailed": 1, "orphaned": 0},
                     "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    if method == "POST" and path.startswith("/api/pool/accounts/") and path.endswith("/recycle"):
        account_id = path.split("/api/pool/accounts/")[1].replace("/recycle", "")
        return 200, {"status": "triggered", "accountId": account_id,
                     "message": f"Recycler triggered for {account_id}"}

    if method == "DELETE" and path.startswith("/api/pool/accounts/"):
        account_id = path.split("/api/pool/accounts/")[1]
        return 200, {"status": "removed", "accountId": account_id}

    # ── Configuration endpoints ──────────────────────────────────────────────

    if method == "GET" and path == "/api/pool/config":
        return 200, {"pools": [
            {"poolName": "analytics", "minSize": 5, "targetSize": 10,
             "maxConcurrentSetups": 3, "reclaimStrategy": "DELETE"},
            {"poolName": "ml-training", "minSize": 3, "targetSize": 8,
             "maxConcurrentSetups": 2, "reclaimStrategy": "REUSE"},
        ]}

    if method == "PUT" and path.startswith("/api/pool/config/"):
        pool_name = path.split("/api/pool/config/")[1]
        return 200, {"status": "saved", "poolName": pool_name,
                     "message": f"Configuration for '{pool_name}' saved to SSM"}

    return 404, {"error": f"Unknown route: {method} {path}"}
