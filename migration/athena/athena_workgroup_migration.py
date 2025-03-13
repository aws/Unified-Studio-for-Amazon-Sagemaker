import argparse
import boto3
import os
import nbformat as nbf
import uuid

from migration.utils.datazone_helper import get_project_repo

def migrate_queries(workgroup_name, domain_id, project_id, account_id, region):
    # Create boto3 clients with the specified region
    athena = boto3.client('athena', region_name=region)
    code_commit = boto3.client('codecommit', region_name=region)

    repo = get_project_repo(domain_id, project_id, region)
    branch = "main"

    # Initialize an empty list to store all named query IDs
    all_named_query_ids = []

    # Paginate through all named queries
    paginator = athena.get_paginator('list_named_queries')
    for page in paginator.paginate(WorkGroup=workgroup_name):
        all_named_query_ids.extend(page['NamedQueryIds'])

    putFilesList = []
    migration_info = []  # List to store migration information

    # Process each named query
    for query_id in all_named_query_ids:
        query_result = athena.get_named_query(NamedQueryId=query_id)
        query_name = query_result['NamedQuery']['Name']
        query_string = query_result['NamedQuery']['QueryString']

        # Generate a UUID for this iteration
        new_uuid = str(uuid.uuid4())

        # Create the sqlnb file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_file = os.path.join(script_dir, 'template.sqlnb')
        nb = nbf.read(template_file, as_version=4)
        code_cell = nbf.v4.new_code_cell(query_string)
        cell_metadata = {'isLimitOn': True, 'displayMode': 'maximized', 'width': 12}
        code_cell['metadata'] = cell_metadata
        nb['cells'].append(code_cell)
        nb['metadata']['title'] = query_name
        nb['metadata']['id'] = nb['metadata']['id'].replace('<uniqueid>', new_uuid)
        nb['metadata']['id'] = nb['metadata']['id'].replace('<region>', region)
        nb['metadata']['id'] = nb['metadata']['id'].replace('<aws-account-id>', account_id)

        # Write the sqlnb file
        with open(f'{query_name}.sqlnb', 'w') as f:
            nbf.write(nb, f)

        # Add the file to putFilesList
        with open(f'{query_name}.sqlnb', mode='r+b') as file_obj:
            file_content = file_obj.read()
        file_path = f'athena_saved_queries/{workgroup_name}/{query_name}.sqlnb'
        putFileEntry = {
            'filePath': file_path,
            'fileContent': file_content
        }
        putFilesList.append(putFileEntry)

        # Store migration info
        migration_info.append({
            'name': query_name,
            'query_id': query_id,
            'path': file_path
        })

        # Clean up the local file
        os.remove(f'{query_name}.sqlnb')

    # Perform a single commit with all files
    if putFilesList:
        parent_commit_id = code_commit.get_branch(repositoryName=repo, branchName=branch).get("branch").get("commitId")
        commit_response = code_commit.create_commit(
            repositoryName=repo,
            branchName=branch,
            parentCommitId=parent_commit_id,
            putFiles=putFilesList
        )
        
        # Check if commit was successful
        if 'commitId' in commit_response:
            print("Migration successful. Commit ID:", commit_response['commitId'])
            print("\nMigrated queries:")
            for info in migration_info:
                print(f"Name: {info['name']}")
                print(f"Query ID: {info['query_id']}")
                print(f"Migrated to: {info['path']}")
                print("---")
        else:
            print("Migration failed. No commit was made.")
    else:
        print("No queries to migrate.")

    print(f"Query migration process completed. Total queries migrated: {len(all_named_query_ids)}")


def bring_your_own_workgroup(workgroup_name, domain_id, project_id, account_id, region):
    print(f"Tagging Athena workgroup {workgroup_name} with DataZone project ID...")
    # Call Athena tag-resource API with the given workgroup_name
    athena = boto3.client('athena', region_name=region)
    athena.tag_resource(
        ResourceARN=f'arn:aws:athena:{region}:{account_id}:workgroup/{workgroup_name}',
        Tags=[{'Key': 'AmazonDataZoneProject', 'Value': project_id}]
    )
    print(f"Tagged Athena workgroup {workgroup_name} with DataZone project ID.")

    print(f"Updating default Athena connection with workgroup {workgroup_name}...")
    # Call Datazone list-connections API to find the default Athena connection
    datazone = boto3.client('datazone', region_name=region)
    default_athena_connection = datazone.list_connections(
        domainIdentifier=domain_id,
        projectIdentifier=project_id,
        type='ATHENA'
    )
    # Call DataZone update-connection API to update the default Athena connection with the given workgroup_name
    datazone.update_connection(
        domainIdentifier=domain_id,
        identifier=default_athena_connection['items'][0]['connectionId'],
        props={
            'athenaProperties': {
                'workgroupName': workgroup_name
            }
        }
    )
    print(f"Updated default Athena connection with workgroup {workgroup_name}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Migrate Athena named queries to CodeCommit')
    parser.add_argument('--workgroup-name', type=str, required=True, help='Athena workgroup name')
    parser.add_argument('--domain-id', type=str, required=True, help='ID of the SageMaker Unified Studio Domain')
    parser.add_argument('--project-id', type=str, required=True, help='Project ID in the SageMaker Unified Studio Domain')
    parser.add_argument('--account-id', type=str, required=True, help='AWS account ID')
    parser.add_argument('--region', type=str, required=True, help='AWS region')
    args = parser.parse_args()

    migrate_queries(args.workgroup_name, args.domain_id, args.project_id, args.account_id, args.region)
    bring_your_own_workgroup(args.workgroup_name, args.domain_id, args.project_id, args.account_id, args.region)