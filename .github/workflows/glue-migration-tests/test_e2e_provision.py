"""Regional bucket requests for the live MySQL fixture."""
import boto3
from botocore.stub import Stubber
import pytest

from e2e import provision_mysql


@pytest.mark.parametrize("region,expected", [
    ("us-east-1", {"Bucket": "e2e-gs-smus-123456789012-us-east-1"}),
    ("us-east-2", {"Bucket": "e2e-gs-smus-123456789012-us-east-2",
                   "CreateBucketConfiguration": {"LocationConstraint": "us-east-2"}}),
])
def test_fixture_bucket_creation_uses_valid_regional_request(region, expected):
    session = boto3.Session(aws_access_key_id="test", aws_secret_access_key="test",
                            region_name=region)
    s3 = session.client("s3")
    with Stubber(s3) as stub:
        stub.add_client_error("head_bucket", service_error_code="404",
                              http_status_code=404, expected_params={"Bucket": expected["Bucket"]})
        stub.add_response("create_bucket", {}, expected)
        class Session:
            def client(self, service):
                assert service == "s3"
                return s3
        assert provision_mysql._bucket(Session(), region, "123456789012", True) == expected["Bucket"]
        stub.assert_no_pending_responses()
