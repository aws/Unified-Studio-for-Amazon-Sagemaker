import os
import boto3
import argparse

from migration.utils.datazone_helper import get_project_repo


def upload_notebooks(local_folder, domain_id, project_id, emr_studio_id, emr_workspace_id, region):
    if not local_folder:
        print("No local folder provided. Skipping notebook upload.")
        return
    else:
        if not emr_studio_id or not emr_workspace_id:
            raise ValueError("EMR Studio ID and Workspace ID are required when uploading notebooks")

    if not os.path.exists(local_folder):
        raise ValueError(f"Local folder {local_folder} does not exist")

    repo = get_project_repo(domain_id, project_id, region)

    print(f"Uploading notebook from local folder {local_folder} to CodeCommit repo {repo}...")
    code_commit = boto3.client('codecommit', region_name=region)
    branch = "main"
    putFilesList = []

    for (root, folders, files) in os.walk(local_folder):
        for file in files:
            file_path = os.path.join(root, file)
            print("Local file: " + file_path)
            # If the file_path has '.git', then ignore it, because it will cause git pull to fail.
            if ".git" in file_path:
                print("Ignoring file: " + file_path)
                continue
            print("Uploading to: " + str(file_path).replace(local_folder, f'emr_notebooks/{emr_studio_id}/{emr_workspace_id}'))
            with open(file_path, mode='r+b') as file_obj:
                file_content = file_obj.read()
                putFileEntry = {
                    'filePath': str(file_path).replace(local_folder, f'emr_notebooks/{emr_studio_id}/{emr_workspace_id}'),
                    'fileContent': file_content
                }
                putFilesList.append(putFileEntry)

    parent_commit_id = code_commit.get_branch(repositoryName=repo, branchName=branch).get("branch").get("commitId")
    code_commit.create_commit(
        repositoryName=repo,
        branchName=branch,
        parentCommitId=parent_commit_id,
        putFiles=putFilesList
    )
    print(f"Uploaded notebook from local folder {local_folder} to CodeCommit repo {repo}.")


if __name__ == '__main__':
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description='Migrate EMR workspace notebooks to a SageMaker Unified Studio project')
    # Add arguments
    parser.add_argument('--local-path', type=str, help='Path to Local folder for EMR workspace')
    parser.add_argument('--domain-id', type=str, required=True, help='ID of the SageMaker Unified Studio Domain')
    parser.add_argument('--project-id', type=str, required=True, help='Project ID in the SageMaker Unified Studio Domain')
    parser.add_argument('--emr-studio-id', type=str, help='Id for EMR Studio. Format es-XXXX')
    parser.add_argument('--emr-workspace-id', type=str, help='Id for EMR studio workspace. Format is e-YYYY')
    parser.add_argument('--region', type=str, required=True, help='AWS region')
    # Parse the arguments
    args = parser.parse_args()

    upload_notebooks(args.local_path, args.domain_id, args.project_id, args.emr_studio_id, args.emr_workspace_id, args.region)



