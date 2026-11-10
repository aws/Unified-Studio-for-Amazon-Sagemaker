"""Domain APIs can live in a different region from project resources."""
from urllib.parse import urlparse

import boto3
import pytest

from migration.glue import cli, cli_connections, connmigrate


@pytest.mark.parametrize("entrypoint,source,operation,error", [
    (cli.main, ["--job-name", "job"], "GetJob", None),
    (cli_connections.main, ["--connection-name", "connection"],
     "GetConnection", connmigrate.SourceConnectionNotFound),
])
def test_cli_contacts_domain_region_while_resources_stay_in_us_east_1(
        monkeypatch, entrypoint, source, operation, error):
    import botocore.endpoint

    requests = []

    def send(endpoint, operation, request_dict):
        requests.append((operation.name, urlparse(request_dict["url"]).netloc,
                         request_dict["context"]["client_region"]))
        if operation.name == "GetJob":
            payload = {"Job": {
                "Name": "job", "Role": "arn:aws:iam::123456789012:role/job",
                "Command": {"Name": "glueetl", "ScriptLocation": "s3://source/job.py"},
            }}
        elif operation.name == "GetCallerIdentity":
            payload = {"Account": "123456789012"}
        elif operation.name == "GetTags":
            payload = {"Tags": {}}
        elif operation.name == "ListConnections":
            payload = {"items": [{"connectionId": "iam1", "name": "project.iam"}]}
        elif operation.name == "GetConnection" and urlparse(request_dict["url"]).netloc.startswith("datazone."):
            payload = {"connectionId": "iam1", "environmentId": "environment",
                       "environmentUserRole": "arn:aws:iam::123456789012:role/project"}
        elif operation.name == "GetRolePolicy":
            return type("Response", (), {"status_code": 404})(), {
                "Error": {"Code": "NoSuchEntity", "Message": "No grant yet"}}
        elif operation.name == "ListEnvironments":
            payload = {"items": [{"id": "environment"}]}
        elif operation.name == "GetEnvironment":
            payload = {"provisionedResources": [
                {"name": "s3BucketPath", "value": "s3://project-bucket/"},
                {"name": "userRoleArn", "value": "arn:aws:iam::123456789012:role/project"}]}
        else:
            assert operation.name in ("GetJob", "GetConnection")
            return type("Response", (), {"status_code": 400})(), {
                "Error": {"Code": "EntityNotFoundException", "Message": "Fixture source absent"}}
        return type("Response", (), {"status_code": 200})(), payload

    monkeypatch.setattr(botocore.endpoint.Endpoint, "make_request", send)
    monkeypatch.setattr(cli.session_mod, "build_session", lambda **kw:
                        boto3.Session(aws_access_key_id="test", aws_secret_access_key="test",
                                      region_name=kw["region"]))
    args = [*source, "--domain-id", "dzd-123", "--project-id", "project",
            "--region", "us-east-1", "--domain-region", "us-east-2"]
    if error:
        with pytest.raises(error):
            entrypoint(args)
    else:
        assert entrypoint(args) == 0
    domain_operations = (
        ["ListConnections", "GetConnection", "GetEnvironment"] if entrypoint is cli.main
        else ["ListEnvironments", "GetEnvironment"]
    )
    if entrypoint is cli.main:
        assert [(op, host, region) for op, host, region in requests
                if op != "GetCallerIdentity"] == [
            ("GetJob", "glue.us-east-1.amazonaws.com", "us-east-1"),
            ("GetTags", "glue.us-east-1.amazonaws.com", "us-east-1"),
            *[(op, "datazone.us-east-2.api.aws", "us-east-2")
              for op in ["ListConnections", "GetConnection"]],
            ("GetRolePolicy", "iam.amazonaws.com", "aws-global"),
            *[(op, "datazone.us-east-2.api.aws", "us-east-2") for op in domain_operations],
        ]
    else:
        assert requests == [
            *[(op, "datazone.us-east-2.api.aws", "us-east-2") for op in domain_operations],
            (operation, "glue.us-east-1.amazonaws.com", "us-east-1")]
