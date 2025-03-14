import boto3
import datetime
import hashlib
import hmac
import json
import requests
import os
from urllib.parse import quote, urlencode


def obtain_credential():
    # Use boto session to get back the credentials
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    session_token = credentials.token

    return access_key, secret_key, session_token


def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def getSignatureKey(key, dateStamp, regionName, serviceName):
    kDate = sign(("AWS4" + key).encode("utf-8"), dateStamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, "aws4_request")
    return kSigning


def sign_request(method, service, host, region, canonical_uri, target, raw_data):
    # Sign the request using SigV4
    access_key, secret_key, session_token = obtain_credential()

    # Create a datetime object for signing
    t = datetime.datetime.now(datetime.UTC)
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')

    # Create the canonical request
    canonical_querystring = ''
    payload_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
    canonical_headers = ('content-type:' + 'application/x-amz-json-1.1' + '\n'
                        + 'host:' + host + '\n' \
                        + 'x-amz-date:' + amzdate + '\n'
                        + 'x-amz-target:' + target + '\n')
    signed_headers = 'content-type;host;x-amz-date;x-amz-target'
    canonical_request = (method + '\n' + canonical_uri + '\n' + canonical_querystring + '\n'
                         + canonical_headers + '\n' + signed_headers + '\n' + payload_hash)

    # Create the string to sign
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = datestamp + '/' + region + '/' + service + '/' + 'aws4_request'
    string_to_sign = (algorithm + '\n' +  amzdate + '\n' +  credential_scope + '\n' +
                      hashlib.sha256(canonical_request.encode('utf-8')).hexdigest())

    # Sign the string
    signing_key = getSignatureKey(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, (string_to_sign).encode('utf-8'), hashlib.sha256).hexdigest()

    # Add signing information to the request
    authorization_header = (algorithm + ' ' + 'Credential=' + access_key + '/' + credential_scope + ', ' +
                            'SignedHeaders=' + signed_headers + ', ' + 'Signature=' + signature)

    headers = {
        'Authorization': authorization_header,
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Date': amzdate,
        'X-Amz-Target': target
    }

    # If session_token is not None, add it to the headers
    if session_token is not None:
        headers['X-Amz-Security-Token'] = session_token
    else:
        print("Session token is None")

    return headers


def get_emr_workspace_storage_location(workspace_id, region):
    method = 'POST'
    service = 'elasticmapreduce'
    host = f'elasticmapreduce.{region}.amazonaws.com'
    target = 'ElasticMapReduce.DescribeEditorPrivate'
    endpoint = '/'

    canonical_uri = endpoint
    raw_data = json.dumps(
        {
            "EditorId": workspace_id
        }
    )
    request_url = 'https://' + host + canonical_uri
    headers = sign_request(method, service, host, region, canonical_uri, target, raw_data)

    print(f"Getting workspace storage location for workspace {workspace_id} in region {region}...")
    response = requests.request(method, request_url, headers=headers, timeout=5, data=raw_data)
    response.raise_for_status()
    print(f"Got workspace storage location for workspace {workspace_id} in region {region}.")

    response_json = response.json()
    return f"{response_json['Editor']['LocationUri']}/{workspace_id}/"
