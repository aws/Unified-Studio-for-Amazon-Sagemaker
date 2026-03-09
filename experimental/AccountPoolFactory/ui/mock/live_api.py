"""
Live API handlers — real boto3 calls to AWS.
Used by mock-server.py --live mode.
"""

import boto3
import json
import os

_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
_table  = "AccountPoolFactory-AccountState"

def _dynamo():
    return boto3.client("dynamodb", region_name=_region)

def _ssm():
    return boto3.client("ssm", region_name=_region)

def _lambda():
    return boto3.client("lambda", region_name=_region)

def _datazone():
    return boto3.client("datazone", region_name=_region)

def _identitystore(store_id):
    return boto3.client("identitystore", region_name=_region)


def _unmarshal(item):
    """Convert DynamoDB item to plain dict."""
    out = {}
    for k, v in item.items():
        if "S" in v:   out[k] = v["S"]
        elif "N" in v: out[k] = v["N"]
        elif "L" in v: out[k] = [x.get("S", x) for x in v["L"]]
        elif "BOOL" in v: out[k] = v["BOOL"]
        else: out[k] = str(v)
    return out


def handle(method, path, body, config):
    region = config.get("region", _region)
    domain_id = config.get("domainId", "")
    table = config.get("dynamoTable", _table)
    identity_store_id = config.get("identityStoreId", "")

    ddb = boto3.client("dynamodb", region_name=region)
    ssm_client = boto3.client("ssm", region_name=region)
    lam = boto3.client("lambda", region_name=region)
    dz  = boto3.client("datazone", region_name=region)

    # ── Project profiles ──────────────────────────────────────────────────────
    if method == "GET" and path == "/api/projects/profiles":
        if not domain_id:
            return 400, {"error": "domainId not configured"}
        try:
            resp = dz.list_project_profiles(domainIdentifier=domain_id)
            profiles = []
            for p in resp.get("items", []):
                # Check if profile has pool-backed environment configs
                try:
                    detail = dz.get_project_profile(
                        domainIdentifier=domain_id,
                        identifier=p["id"]
                    )
                    env_configs = detail.get("environmentConfigurations", [])
                    has_pool = any(
                        cfg.get("accountPools") or cfg.get("awsAccountIdPath")
                        for cfg in env_configs
                    )
                    if has_pool:
                        profiles.append({
                            "id": p["id"],
                            "name": p["name"],
                            "description": p.get("description", ""),
                            "hasPool": True,
                            "allowedRegions": [{"value": region, "label": region}]
                        })
                except Exception:
                    pass
            return 200, {"profiles": profiles}
        except Exception as e:
            return 500, {"error": str(e)}

    # ── Owner search ──────────────────────────────────────────────────────────
    if method == "GET" and path.startswith("/api/projects/owners"):
        if not identity_store_id:
            return 200, {"owners": []}
        params = {}
        if "?" in path:
            for kv in path.split("?")[1].split("&"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    from urllib.parse import unquote_plus
                    params[k] = unquote_plus(v)
        q = params.get("search", "").strip().lower()
        if not q:
            return 200, {"owners": []}
        try:
            idc = boto3.client("identitystore", region_name=region)
            owners = []

            # Fetch all users and filter client-side (IDC filter is exact-match only)
            paginator = idc.get_paginator("list_users")
            for page in paginator.paginate(IdentityStoreId=identity_store_id):
                for u in page.get("Users", []):
                    username = u.get("UserName", "").lower()
                    display = u.get("DisplayName", "").lower()
                    given = u.get("Name", {}).get("GivenName", "").lower()
                    family = u.get("Name", {}).get("FamilyName", "").lower()
                    email = next((e["Value"] for e in u.get("Emails", []) if e.get("Primary")), "")
                    if q in username or q in display or q in given or q in family or q in email.lower():
                        name = u.get("DisplayName") or f"{u.get('Name',{}).get('GivenName','')} {u.get('Name',{}).get('FamilyName','')}".strip() or username
                        owners.append({"id": u["UserId"], "name": name, "email": email, "type": "USER"})

            # Fetch all groups and filter client-side
            paginator = idc.get_paginator("list_groups")
            for page in paginator.paginate(IdentityStoreId=identity_store_id):
                for g in page.get("Groups", []):
                    name = g.get("DisplayName", "")
                    if q in name.lower():
                        owners.append({"id": g["GroupId"], "name": name, "email": None, "type": "GROUP"})

            return 200, {"owners": owners[:10]}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return 500, {"error": str(e)}

    # ── Create project ────────────────────────────────────────────────────────
    if method == "POST" and path == "/api/projects":
        if not domain_id:
            return 400, {"error": "domainId not configured"}
        data = body or {}
        try:
            # Get account pool
            pools_resp = dz.list_account_pools(domainIdentifier=domain_id)
            pool_id = pools_resp.get("items", [{}])[0].get("id", "")
            if not pool_id:
                return 400, {"error": "No account pool found"}

            # Resolve account
            accts = dz.list_accounts_in_account_pool(
                domainIdentifier=domain_id, identifier=pool_id
            )
            account_id = accts.get("items", [{}])[0].get("awsAccountId", "")
            if not account_id:
                return 400, {"error": "No available accounts in pool"}

            # Get profile env configs
            profile_detail = dz.get_project_profile(
                domainIdentifier=domain_id, identifier=data["profileId"]
            )
            env_configs = profile_detail.get("environmentConfigurations", [])
            user_params = [
                {
                    "environmentConfigurationName": cfg["name"],
                    "environmentResolvedAccount": {
                        "awsAccountId": account_id,
                        "regionName": data.get("region", region),
                        "sourceAccountPoolId": pool_id
                    }
                }
                for cfg in env_configs
            ]

            create_kwargs = dict(
                domainIdentifier=domain_id,
                name=data["name"],
                projectProfileId=data["profileId"],
                userParameters=user_params,
            )
            if data.get("ownerId"):
                create_kwargs["ownerIdentifier"] = data["ownerId"]

            proj = dz.create_project(**create_kwargs)
            portal_url = config.get("portalUrl", "")
            return 200, {
                "projectId": proj["id"],
                "resolvedAccountId": account_id,
                "portalUrl": portal_url
            }
        except Exception as e:
            return 500, {"error": str(e)}

    # ── Project status ────────────────────────────────────────────────────────
    if method == "GET" and path.startswith("/api/projects/") and "/status" in path:
        project_id = path.split("/api/projects/")[1].replace("/status", "")
        if not domain_id:
            return 400, {"error": "domainId not configured"}
        try:
            proj = dz.get_project(domainIdentifier=domain_id, identifier=project_id)
            deploy = proj.get("environmentDeploymentDetails", {})
            envs_resp = dz.list_environments(domainIdentifier=domain_id, projectIdentifier=project_id)
            envs = [{"name": e.get("name", ""), "status": e.get("status", "")}
                    for e in envs_resp.get("items", [])]
            return 200, {
                "id": project_id,
                "projectStatus": proj.get("projectStatus", ""),
                "overallDeploymentStatus": deploy.get("overallDeploymentStatus", "IN_PROGRESS"),
                "environments": envs,
                "resolvedAccountId": None,
            }
        except Exception as e:
            return 500, {"error": str(e)}
    if method == "GET" and path == "/api/pool/summary":
        states = ["AVAILABLE", "ASSIGNED", "SETTING_UP", "CLEANING", "FAILED", "ORPHANED"]
        all_items = []
        last_key = None
        while True:
            kwargs = {"TableName": table, "ProjectionExpression": "#s, poolName",
                      "ExpressionAttributeNames": {"#s": "state"}}
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            resp = ddb.scan(**kwargs)
            all_items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break

        summary = {}
        for item in all_items:
            pool = item.get("poolName", {}).get("S", "")
            if not pool:
                continue  # skip accounts with no pool name in summary
            state = item.get("state", {}).get("S", "UNKNOWN")
            if pool not in summary:
                summary[pool] = {s: 0 for s in states}
            summary[pool][state] = summary[pool].get(state, 0) + 1

        pools = [{"poolName": k, "counts": v} for k, v in summary.items()]
        return 200, {"pools": pools, "lastReconciled": None}

    # ── Accounts list ─────────────────────────────────────────────────────────
    if method == "GET" and (path == "/api/pool/accounts" or path.startswith("/api/pool/accounts?")):
        params = {}
        if "?" in path:
            for kv in path.split("?")[1].split("&"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    from urllib.parse import unquote_plus
                    params[k] = unquote_plus(v)

        state   = params.get("state", "")
        pool    = params.get("poolName", "")
        search  = params.get("search", "").lower()

        # Use StateIndex GSI if filtering by state
        if state:
            resp = ddb.query(
                TableName=table,
                IndexName="StateIndex",
                KeyConditionExpression="#s = :s",
                ExpressionAttributeNames={"#s": "state"},
                ExpressionAttributeValues={":s": {"S": state}},
                Limit=200
            )
            items = resp.get("Items", [])
        else:
            resp = ddb.scan(TableName=table, Limit=200)
            items = resp.get("Items", [])

        accounts = [_unmarshal(i) for i in items]

        if pool:
            accounts = [a for a in accounts if a.get("poolName") == pool]
        if search:
            accounts = [a for a in accounts if
                search in a.get("accountId", "").lower() or
                search in a.get("accountName", "").lower() or
                search in a.get("projectId", "").lower()]

        return 200, {"accounts": accounts, "total": len(accounts)}

    # ── Account detail & StackSets ────────────────────────────────────────────
    if method == "GET" and path.startswith("/api/pool/accounts/"):
        parts = path.split("/api/pool/accounts/")[1].split("/")
        account_id = parts[0].split("?")[0]

        # StackSet status sub-resource
        if len(parts) > 1 and parts[1] == "stacksets":
            resp = ddb.query(
                TableName=table,
                KeyConditionExpression="accountId = :a",
                ExpressionAttributeValues={":a": {"S": account_id}},
                ScanIndexForward=False, Limit=1
            )
            items = resp.get("Items", [])
            if not items:
                return 404, {"error": "Account not found"}
            acc = _unmarshal(items[0])
            deployed = acc.get("deployedStackSets", [])
            if isinstance(deployed, str):
                try: deployed = json.loads(deployed)
                except: deployed = [deployed]

            stacksets = []
            try:
                # Get org admin role ARN from CF stack outputs
                org_role_arn = None
                try:
                    cf_local = boto3.client("cloudformation", region_name=region)
                    cf_resp = cf_local.describe_stacks(StackName="AccountPoolFactory-OrgAdmin")
                    for out in cf_resp["Stacks"][0].get("Outputs", []):
                        if out["OutputKey"] == "AccountCreationRoleArn":
                            org_role_arn = out["OutputValue"]
                            break
                except Exception:
                    pass

                if org_role_arn:
                    sts_client = boto3.client("sts", region_name=region)
                    assumed = sts_client.assume_role(
                        RoleArn=org_role_arn,
                        RoleSessionName="UI-StackSetCheck",
                        ExternalId=f"AccountPoolFactory-{config.get('accountId','')}"
                    )
                    creds = assumed["Credentials"]
                    cf_org = boto3.client(
                        "cloudformation", region_name=region,
                        aws_access_key_id=creds["AccessKeyId"],
                        aws_secret_access_key=creds["SecretAccessKey"],
                        aws_session_token=creds["SessionToken"]
                    )
                    for ss_name in deployed:
                        try:
                            inst = cf_org.describe_stack_instance(
                                StackSetName=ss_name,
                                StackInstanceAccount=account_id,
                                StackInstanceRegion=region
                            )
                            si = inst["StackInstance"]
                            stacksets.append({
                                "name": ss_name,
                                "status": si.get("Status", "UNKNOWN"),
                                "statusReason": si.get("StatusReason", ""),
                                "stackId": si.get("StackId", ""),
                            })
                        except Exception as e:
                            stacksets.append({
                                "name": ss_name,
                                "status": "NOT_FOUND",
                                "statusReason": str(e),
                                "stackId": "",
                            })
                else:
                    stacksets = [{"name": s, "status": "UNKNOWN", "statusReason": "Org role not found", "stackId": ""} for s in deployed]
            except Exception as e:
                stacksets = [{"name": s, "status": "ERROR", "statusReason": str(e), "stackId": ""} for s in deployed]

            return 200, {"accountId": account_id, "stacksets": stacksets}

        # Plain account detail
        resp = ddb.query(
            TableName=table,
            KeyConditionExpression="accountId = :a",
            ExpressionAttributeValues={":a": {"S": account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        items = resp.get("Items", [])
        if not items:
            return 404, {"error": "Account not found"}
        return 200, _unmarshal(items[0])

    # ── Replenish ─────────────────────────────────────────────────────────────
    if method == "POST" and path == "/api/pool/replenish":
        pool_name = (body or {}).get("poolName", "")
        payload = {"action": "force_replenishment"}
        if pool_name:
            payload["poolName"] = pool_name
        lam.invoke(
            FunctionName="PoolManager",
            InvocationType="Event",
            Payload=json.dumps(payload).encode()
        )
        return 200, {"status": "triggered", "message": f"Replenishment triggered{' for ' + pool_name if pool_name else ''}"}

    # ── Reconcile ─────────────────────────────────────────────────────────────
    if method == "POST" and path == "/api/pool/reconcile":
        data = body or {}
        resp = lam.invoke(
            FunctionName="AccountReconciler",
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "source": "ui",
                "dryRun": data.get("dryRun", True),
                "autoRecycle": data.get("autoRecycle", False),
                "autoReplenish": data.get("autoReplenish", False),
            }).encode()
        )
        result = json.loads(resp["Payload"].read())
        return 200, result

    # ── Recycle account ───────────────────────────────────────────────────────
    if method == "POST" and path.endswith("/recycle"):
        account_id = path.split("/api/pool/accounts/")[1].replace("/recycle", "")
        lam.invoke(
            FunctionName="AccountRecycler",
            InvocationType="Event",
            Payload=json.dumps({"accountId": account_id}).encode()
        )
        return 200, {"status": "triggered", "accountId": account_id}

    # ── Delete account ────────────────────────────────────────────────────────
    if method == "DELETE" and path.startswith("/api/pool/accounts/"):
        account_id = path.split("/api/pool/accounts/")[1]
        resp = lam.invoke(
            FunctionName="PoolManager",
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "delete_failed_account", "accountId": account_id}).encode()
        )
        result = json.loads(resp["Payload"].read())
        return 200, result

    # ── Config read ───────────────────────────────────────────────────────────
    if method == "GET" and path == "/api/pool/config":
        try:
            resp = ssm_client.get_parameters_by_path(
                Path="/AccountPoolFactory/Pools/",
                Recursive=True,
                WithDecryption=False
            )
            params = {}
            for p in resp.get("Parameters", []):
                parts = p["Name"].split("/")
                if len(parts) >= 5:
                    pool_name = parts[3]
                    key = parts[4]
                    if pool_name not in params:
                        params[pool_name] = {"poolName": pool_name}
                    params[pool_name][key] = p["Value"]

            pools = []
            for pool_name, cfg in params.items():
                pools.append({
                    "poolName": pool_name,
                    "minSize": int(cfg.get("MinimumPoolSize", 5)),
                    "targetSize": int(cfg.get("TargetPoolSize", 10)),
                    "maxConcurrentSetups": int(cfg.get("MaxConcurrentSetups", 3)),
                    "reclaimStrategy": cfg.get("ReclaimStrategy", "DELETE"),
                })
            return 200, {"pools": pools}
        except Exception as e:
            return 500, {"error": str(e)}

    # ── Config write ──────────────────────────────────────────────────────────
    if method == "PUT" and path.startswith("/api/pool/config/"):
        pool_name = path.split("/api/pool/config/")[1]
        data = body or {}
        prefix = f"/AccountPoolFactory/Pools/{pool_name}"
        mapping = {
            "minSize":             ("MinimumPoolSize", str),
            "targetSize":          ("TargetPoolSize", str),
            "maxConcurrentSetups": ("MaxConcurrentSetups", str),
            "reclaimStrategy":     ("ReclaimStrategy", str),
        }
        for js_key, (ssm_key, cast) in mapping.items():
            if js_key in data:
                ssm_client.put_parameter(
                    Name=f"{prefix}/{ssm_key}",
                    Value=cast(data[js_key]),
                    Type="String",
                    Overwrite=True
                )
        return 200, {"status": "saved", "poolName": pool_name}

    return 404, {"error": f"Unknown route: {method} {path}"}
