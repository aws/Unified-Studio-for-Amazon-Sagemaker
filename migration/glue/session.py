"""AWS clients using the caller's configured boto3 credentials."""
from __future__ import annotations

import boto3

def build_session(profile: str | None = None, region: str = "us-east-2") -> boto3.Session:
    """Resolve credentials via boto3's default chain (optionally a named profile)."""
    return boto3.Session(profile_name=profile, region_name=region)


def glue_client(session: boto3.Session):
    return session.client("glue")


def s3_client(session: boto3.Session):
    return session.client("s3")


def sts_client(session: boto3.Session):
    return session.client("sts")


def datazone_client(session: boto3.Session, region: str = "us-east-2"):
    """Build a DataZone client in the domain's region using SDK endpoint resolution."""
    return session.client("datazone", region_name=region)
