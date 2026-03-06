import json, subprocess, os, time

creds = json.load(open('experimental/AccountPoolFactory/.tmp-creds.json'))
env = os.environ.copy()
env['AWS_ACCESS_KEY_ID'] = creds['AccessKeyId']
env['AWS_SECRET_ACCESS_KEY'] = creds['SecretAccessKey']
env['AWS_SESSION_TOKEN'] = creds['SessionToken']

ts = str(int(time.time()))

user_params = json.dumps([
    {"environmentConfigurationName":"ToolingLite","environmentResolvedAccount":{"awsAccountId":"392423995616","regionName":"us-east-2","sourceAccountPoolId":"5id04597iehicp"}},
    {"environmentConfigurationName":"S3Bucket","environmentResolvedAccount":{"awsAccountId":"392423995616","regionName":"us-east-2","sourceAccountPoolId":"5id04597iehicp"}},
    {"environmentConfigurationName":"S3TableCatalog","environmentResolvedAccount":{"awsAccountId":"392423995616","regionName":"us-east-2","sourceAccountPoolId":"5id04597iehicp"}}
])

role_configs = json.dumps([
    {"roleArn":"arn:aws:iam::392423995616:role/service-role/AmazonSageMakerProjectRole","roleDesignation":"PROJECT_CONTRIBUTOR"}
])

cmd = [
    'aws', 'datazone', 'create-project',
    '--domain-identifier', 'dzd-5o0lje5xgpeuw9',
    '--name', f'test-from-pool-{ts}',
    '--description', 'Test from pool account',
    '--project-profile-id', '48ly31ms09wckp',
    '--user-parameters', user_params,
    '--customer-provided-role-configs', role_configs,
    '--region', 'us-east-2',
    '--output', 'json'
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=20)
    print(f'rc={result.returncode}')
    if result.stdout:
        print(result.stdout[:1000])
    if result.stderr:
        print(result.stderr[:1000])
except subprocess.TimeoutExpired:
    print('TIMEOUT after 20s')
