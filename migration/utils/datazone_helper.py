import boto3

def get_project_repo(domain_id, project_id, region):
    datazone = boto3.client('datazone', region_name=region)

    project_envs = datazone.list_environments(domainIdentifier=domain_id, projectIdentifier=project_id)
    tooling_env_info = next((env for env in project_envs['items'] if env['name'] == 'Tooling'), None)

    if tooling_env_info:
        tooling_env = datazone.get_environment(identifier=tooling_env_info['id'], domainIdentifier=domain_id)
        repo_info = next((resource for resource in tooling_env['provisionedResources'] if resource['name'] == 'codeRepositoryName'), None)

        if repo_info:
            return repo_info['value']

    raise Exception(f"Code repository not found for project {project_id} in domain {domain_id}")