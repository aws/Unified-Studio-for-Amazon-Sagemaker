"""Long-lived e2e fixture: a private RDS MySQL reachable from Glue jobs.

    python .github/workflows/glue-migration-tests/e2e/provision_mysql.py up     # idempotent create, prints exports
    python .github/workflows/glue-migration-tests/e2e/provision_mysql.py env    # print exports for existing fixture
    python .github/workflows/glue-migration-tests/e2e/provision_mysql.py down   # delete everything created by `up`

Uses the standard boto3 credential chain; GS_SMUS_E2E_PROFILE / GS_SMUS_E2E_REGION
optionally pick a profile and region. Every
resource is named/tagged `e2e-gs-smus*` and lives in the region's default VPC:
one RDS instance, one self-referencing security group, an S3 gateway endpoint,
Secrets Manager + STS interface endpoints (Glue ENIs have no internet route),
a script bucket and a Glue job role. Nothing pre-existing is modified except
that the S3 gateway endpoint adds a route to the VPC's main route table.
"""
from __future__ import annotations

import json
import sys
import time

import os

import boto3

NAME = "e2e-gs-smus"
DB_ID = f"{NAME}-mysql"
JOB_ROLE = f"{NAME}-job-role"
TAGS = [{"Key": "Name", "Value": NAME}, {"Key": "purpose", "Value": "gs-smus-migration-e2e"}]
_IFACE = ("secretsmanager", "sts")


def _ctx():
    s = boto3.Session(profile_name=os.environ.get("GS_SMUS_E2E_PROFILE"),
                      region_name=os.environ.get("GS_SMUS_E2E_REGION"))
    region = s.region_name
    acct = s.client("sts").get_caller_identity()["Account"]
    ec2 = s.client("ec2")
    vpc = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc]},
                                            {"Name": "default-for-az", "Values": ["true"]}])["Subnets"]
    subnet = sorted(subnets, key=lambda x: x["AvailabilityZone"])[0]
    return s, region, acct, ec2, vpc, subnet


def _sg(ec2, vpc, create):
    got = ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc]},
                                                {"Name": "group-name", "Values": [NAME]}])["SecurityGroups"]
    if got or not create:
        return got[0]["GroupId"] if got else None
    sg = ec2.create_security_group(GroupName=NAME, Description="gs-smus e2e (Glue self-ref)", VpcId=vpc,
                                   TagSpecifications=[{"ResourceType": "security-group", "Tags": TAGS}])["GroupId"]
    ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[
        {"IpProtocol": "tcp", "FromPort": 0, "ToPort": 65535, "UserIdGroupPairs": [{"GroupId": sg}]}])
    return sg


def _endpoints(ec2, region, vpc, subnet, sg, create):
    have = {e["ServiceName"]: e["VpcEndpointId"] for e in ec2.describe_vpc_endpoints(
        Filters=[{"Name": "vpc-id", "Values": [vpc]}, {"Name": "tag:Name", "Values": [NAME]},
                 {"Name": "vpc-endpoint-state", "Values": ["pending", "available"]}])["VpcEndpoints"]}
    if not create:
        return list(have.values())
    spec = {"ResourceType": "vpc-endpoint", "Tags": TAGS}
    s3 = f"com.amazonaws.{region}.s3"
    if s3 not in have:
        rt = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc]},
                                                {"Name": "association.main", "Values": ["true"]}])["RouteTables"][0]
        ec2.create_vpc_endpoint(VpcId=vpc, ServiceName=s3, VpcEndpointType="Gateway",
                                RouteTableIds=[rt["RouteTableId"]], TagSpecifications=[spec])
    for svc in _IFACE:
        name = f"com.amazonaws.{region}.{svc}"
        if name not in have:
            ec2.create_vpc_endpoint(VpcId=vpc, ServiceName=name, VpcEndpointType="Interface",
                                    SubnetIds=[subnet["SubnetId"]], SecurityGroupIds=[sg],
                                    PrivateDnsEnabled=True, TagSpecifications=[spec])


def _bucket(s, region, acct, create):
    name = f"{NAME}-{acct}-{region}"
    if create:
        s3 = s.client("s3")
        try:
            s3.head_bucket(Bucket=name)
        except s3.exceptions.ClientError:
            kwargs = {} if region == "us-east-1" else {
                "CreateBucketConfiguration": {"LocationConstraint": region}}
            s3.create_bucket(Bucket=name, **kwargs)
    return name


def _job_role(s, acct, bucket, create):
    iam = s.client("iam")
    try:
        arn = iam.get_role(RoleName=JOB_ROLE)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        if not create:
            return None
        trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole",
                                                         "Principal": {"Service": "glue.amazonaws.com"}}]}
        arn = iam.create_role(RoleName=JOB_ROLE, AssumeRolePolicyDocument=json.dumps(trust),
                              Tags=TAGS)["Role"]["Arn"]
        iam.attach_role_policy(RoleName=JOB_ROLE,
                               PolicyArn="arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole")
    if create:
        iam.put_role_policy(RoleName=JOB_ROLE, PolicyName="e2e", PolicyDocument=json.dumps({
            "Version": "2012-10-17", "Statement": [
                {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                 "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"]},
                # A job moved into a project keeps its role and runs the script the move
                # copied to <domain>/<project>/shared/jobs/ in the project bucket.
                {"Effect": "Allow", "Action": ["s3:GetObject"],
                 "Resource": f"arn:aws:s3:::amazon-sagemaker-{acct}-*/*/*/shared/jobs/*"},
                {"Effect": "Allow", "Action": ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                 "Resource": f"arn:aws:secretsmanager:*:{acct}:secret:e2e-*"},
                # V2 VPC connections validate the VPC with the connection's ROLE_ARN.
                {"Effect": "Allow", "Action": ["ec2:DescribeVpcs"], "Resource": "*"}]}))
        time.sleep(10)  # IAM propagation before Glue validates the role
    return arn


def _db(s, subnet, sg, create):
    rds = s.client("rds")
    try:
        db = rds.describe_db_instances(DBInstanceIdentifier=DB_ID)["DBInstances"][0]
    except rds.exceptions.DBInstanceNotFoundFault:
        if not create:
            return None
        rds.create_db_instance(
            DBInstanceIdentifier=DB_ID, Engine="mysql", DBInstanceClass="db.t4g.micro",
            AllocatedStorage=20, DBName="e2e", MasterUsername="e2eadmin", ManageMasterUserPassword=True,
            VpcSecurityGroupIds=[sg], AvailabilityZone=subnet["AvailabilityZone"], PubliclyAccessible=False,
            BackupRetentionPeriod=0, DeletionProtection=False, Tags=TAGS)
        print("waiting for RDS (5-10 min)...", file=sys.stderr)
        rds.get_waiter("db_instance_available").wait(DBInstanceIdentifier=DB_ID)
        db = rds.describe_db_instances(DBInstanceIdentifier=DB_ID)["DBInstances"][0]
    return db


def up(create=True):
    s, region, acct, ec2, vpc, subnet = _ctx()
    sg = _sg(ec2, vpc, create)
    if sg is None:
        raise SystemExit("fixture not provisioned; run `up`")
    _endpoints(ec2, region, vpc, subnet, sg, create)
    bucket = _bucket(s, region, acct, create)
    role = _job_role(s, acct, bucket, create)
    db = _db(s, subnet, sg, create)
    if db is None or role is None:
        raise SystemExit("fixture not provisioned; run `up`")
    env = {"MYSQL_HOST": db["Endpoint"]["Address"], "MYSQL_PORT": str(db["Endpoint"]["Port"]),
           "MYSQL_DB": "e2e", "MYSQL_MASTER_SECRET": db["MasterUserSecret"]["SecretArn"],
           "SUBNET_ID": subnet["SubnetId"], "AZ": subnet["AvailabilityZone"], "SG_ID": sg,
           "BUCKET": bucket, "JOB_ROLE_ARN": role}
    for k, v in env.items():
        print(f"export GS_SMUS_E2E_{k}={v}")


def down():
    s, region, acct, ec2, vpc, subnet = _ctx()
    rds, iam = s.client("rds"), s.client("iam")
    try:
        rds.delete_db_instance(DBInstanceIdentifier=DB_ID, SkipFinalSnapshot=True,
                               DeleteAutomatedBackups=True)
        rds.get_waiter("db_instance_deleted").wait(DBInstanceIdentifier=DB_ID)
    except rds.exceptions.DBInstanceNotFoundFault:
        pass
    sg = _sg(ec2, vpc, False)
    eps = _endpoints(ec2, region, vpc, subnet, sg, False)
    if eps:
        ec2.delete_vpc_endpoints(VpcEndpointIds=eps)
        time.sleep(60)  # interface ENIs must detach before the SG can go
    if sg:
        ec2.delete_security_group(GroupId=sg)
    bucket = _bucket(s, region, acct, False)
    b = s.resource("s3").Bucket(bucket)
    try:
        b.objects.all().delete()
        b.delete()
    except s.client("s3").exceptions.NoSuchBucket:
        pass
    try:
        iam.detach_role_policy(RoleName=JOB_ROLE,
                               PolicyArn="arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole")
        iam.delete_role_policy(RoleName=JOB_ROLE, PolicyName="e2e")
        iam.delete_role(RoleName=JOB_ROLE)
    except iam.exceptions.NoSuchEntityException:
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "env"
    {"up": up, "env": lambda: up(create=False), "down": down}[cmd]()
