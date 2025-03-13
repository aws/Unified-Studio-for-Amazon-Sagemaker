import argparse
import boto3

def _parse_args():
    parser = argparse.ArgumentParser(description='Python script to bring your glue tables to a specified project in sagemaker unified studio')

    parser.add_argument('--project-role-arn', type=str, required=True, help='Project role arn of the project in which you want to bring your own glue tables')
    parser.add_argument('--database-name', type=str, required=True, help='Glue database name of the table you want to bring into your project')
    parser.add_argument('--table-name', type=str, required=False, help='Glue table name you want to bring into your project. If table name is not provided, imports all the tables of the provided database into the project')
    parser.add_argument('--iam-role-arn-lf-resource-register', type=str, required=False, help='IAM Role arn which would be used in registration of S3 location in LakeFormation. Please refer to https://docs.aws.amazon.com/lake-formation/latest/dg/registration-role.html'
                                                                                              ' for role requirements. If not provided, AWSServiceRoleForLakeFormation service-linked role is used.')
    parser.add_argument('--region', type=str, required=False, help='The AWS region. If not specified, the default region from your AWS credentials will be used')

    return parser.parse_args()

def _check_database_managed_by_iam_access_and_enable_opt_in(database_name, role_arn, lf_client):
    '''
    Checks if the database is managed by IAM access. If it is, then enables hybrid mode for the database to allow Lake Formation permissions to work.
    '''
    try:
        db_access = lf_client.list_permissions(
            Resource={
                'Database': {
                    'Name': database_name
                }
            },
            Principal={
                'DataLakePrincipalIdentifier': 'IAM_ALLOWED_PRINCIPALS'
            }
        ).get('PrincipalResourcePermissions', [])

        if db_access:
            print(f"Glue database: {database_name} is managed via IAM access")
            db_opt_in = lf_client.list_lake_formation_opt_ins(
                Principal={
                    'DataLakePrincipalIdentifier': role_arn
                },
                Resource={
                    'Database': {
                        'Name': database_name
                    }
                }
            ).get('LakeFormationOptInsInfoList', [])

            if db_opt_in:
                print(f"Principal: {role_arn} is already opted-in to {database_name}")
            else:
                lf_client.create_lake_formation_opt_in(
                    Principal={
                        'DataLakePrincipalIdentifier': role_arn
                    },
                    Resource={
                        'Database': {
                            'Name': database_name
                        }
                    }
                )
                print(f"Successfully created Lake Formation opt-in for database: {database_name}")
        else:
            print(f"Glue database: {database_name} is already managed via LakeFormation")

    except Exception as e:
        print(f"Error checking whether glue database {database_name} is managed by IAM access and setting opt in : {str(e)}")
        raise e

def _check_table_managed_by_iam_access_and_enable_opt_in(database_name, table_name, role_arn, lf_client):
    '''
    Checks if the table is managed by IAM access. If it is, then enables hybrid mode for the table to allow Lake Formation permissions to work.
    '''
    try:
        table_access = lf_client.list_permissions(
            Resource={
                'Table': {
                    'DatabaseName': database_name,
                    'Name': table_name
                }
            },
            Principal={
                'DataLakePrincipalIdentifier': 'IAM_ALLOWED_PRINCIPALS'
            }
        ).get('PrincipalResourcePermissions', [])

        if table_access:
            print(f"Glue table: {database_name}.{table_name} is managed via IAM access")
            tb_opt_in = lf_client.list_lake_formation_opt_ins(
                Principal={
                    'DataLakePrincipalIdentifier': role_arn
                },
                Resource={
                    'Table': {
                        'DatabaseName': database_name,
                        'Name': table_name
                    }
                }
            ).get('LakeFormationOptInsInfoList', [])

            if tb_opt_in:
                print(f"Principal: {role_arn} is already opted-in to {database_name}.{table_name}")
            else:
                lf_client.create_lake_formation_opt_in(
                    Principal={
                        'DataLakePrincipalIdentifier': role_arn
                    },
                    Resource={
                        'Table': {
                            'DatabaseName': database_name,
                            'Name': table_name
                        }
                    }
                )
                print(f"Successfully created Lake Formation opt-in for {database_name}.{table_name}")
        else:
            print(f"Glue table: {database_name}.{table_name} is already managed via LakeFormation")

    except Exception as e:
        print(f"Error checking whether glue database and table {database_name}.{table_name} is managed by IAM access and setting opt in : {str(e)}")
        raise e

def _register_s3_location(s3_path, role_arn, lf_client):
    '''
    Registers the S3 location of the glue table as Hybrid Mode to the lake formation with provided role arn, if role arn is not provided, use service linked role
    '''
    try:
        # Convert S3 path to arn
        resource_arn = f"arn:aws:s3:::{s3_path.replace('s3://', '')}"

        if role_arn:
            lf_client.register_resource(
                ResourceArn=resource_arn,
                RoleArn=role_arn,
                HybridAccessEnabled=True
            )
            print(f"Successfully registered {resource_arn} to {role_arn}")
        else:
            # if role arn for access is not provided by the user, AWSServiceRoleForLakeFormationDataAccess service linked role would be used
            lf_client.register_resource(
                ResourceArn=resource_arn,
                UseServiceLinkedRole=True,
                HybridAccessEnabled=True
            )
            print(f"Successfully registered {resource_arn} to AWSServiceRoleForLakeFormationDataAccess service linked role")

    except Exception as e:
        print(f"Error registering {resource_arn}: {str(e)}")
        raise e

def _grant_permissions_to_table(role_arn, database_name, table_name, lf_client):
    try:
        lf_client.grant_permissions(
            Principal={
                'DataLakePrincipalIdentifier': role_arn
            },
            Resource={
                'Table': {
                    'Name': table_name,
                    'DatabaseName': database_name
                }
            },
            Permissions=['ALL'],
            PermissionsWithGrantOption=['ALL']
        )
        print(f"Successfully granted ALL permission and ALL WITH GRANT Option permission on database {database_name}.{table_name} to {role_arn}")
    except Exception as e:
        print(f"Error granting permissions: {str(e)}")
        raise e

def s3_arn_to_s3_path(arn):
    """
    Convert an S3 ARN to an S3 path.
    Example: 'arn:aws:s3:::bucket/key' -> 's3://bucket/key'
    """
    # Remove the ARN prefix (everything up to and including the triple colon)
    s3_path = arn.rstrip('/').split(':::', 1)[1]
    return f"s3://{s3_path}"

def _get_s3_subpaths(s3_path):
    """
    Get all sub-paths for a given S3 path.
    Returns list of paths from bucket to full path.
    """

    # Remove trailing slash if present
    s3_path = s3_path.rstrip('/')

    paths = []
    # Split into parts
    parts = s3_path.split('/')
    current = parts[0] + '//' + parts[2]  # s3://bucket
    paths.append(current)

    # Add each subfolder level
    for part in parts[3:]:
        current = current + '/' + part
        paths.append(current)

    return paths

def _get_S3_registered_locations(lf_client):
    """
    Get all registered S3 locations
    """
    registered_locations = []
    next_token = None

    try:
        while True:
            params = {}
            if next_token:
                params['NextToken'] = next_token

            response = lf_client.list_resources(**params)

            # Process resources in current page
            for resource in response.get('ResourceInfoList', []):
                resource_arn = resource.get('ResourceArn', '')
                if 's3:::' in resource_arn:
                    registered_locations.append(s3_arn_to_s3_path(resource_arn))

            # Check if there are more resources to fetch
            next_token = response.get('NextToken')
            if not next_token:
                break

    except ClientError as e:
        print(f"Error calling Lake Formation list_resources api to fetch registered S3 locations: {str(e)}")
        raise e

    return registered_locations

def _check_and_register_location(tables, role_arn, lf_client):
    s3_registered_locations = _get_S3_registered_locations(lf_client)

    for table in tables:
        # Remove trailing '/' if present
        s3_location = table['StorageDescriptor']['Location'].rstrip('/')
        s3_subpaths = _get_s3_subpaths(s3_location)
        s3_registration = False
        for s3_path in s3_subpaths:
            if s3_path in s3_registered_locations:
                print(f"S3 location: {s3_location} is already registered in Lake Formation, either directly or through its subpaths.")
                s3_registration = True
                break

        if not s3_registration:
            _register_s3_location(s3_location, role_arn, lf_client)
            s3_registered_locations.append(s3_location)


def _get_table(database_name, table_name, glue_client):
    try:
        return glue_client.get_table(DatabaseName=database_name, Name=table_name)['Table']
    except Exception as e:
        print(f"Error retrieving table in database {database_name} : {str(e)}")
        raise e

def _get_all_tables_for_a_database(database_name, glue_client):
    try:
        tables = []
        next_token = None

        while True:
            if next_token:
                response = glue_client.get_tables(
                    DatabaseName=database_name,
                    NextToken=next_token
                )
            else:
                response = glue_client.get_tables(
                    DatabaseName=database_name
                )

            for table in response['TableList']:
                tables.append(table)

            if 'NextToken' in response:
                next_token = response['NextToken']
            else:
                break

        return tables

    except ClientError as e:
        print(f"Error while retrieving tables in database {database_name} : {e}")
        raise e

def byogdc_main():
    args = _parse_args()
    if args.region:
        session = boto3.Session(region_name=args.region)
    else:
        session = boto3.Session()
    lf_client = session.client('lakeformation')
    glue_client = session.client('glue')

    try:
        _check_database_managed_by_iam_access_and_enable_opt_in(args.database_name, args.project_role_arn, lf_client)

        if args.table_name:
            tables = [_get_table(args.database_name, args.table_name, glue_client)]
        else:
            tables = _get_all_tables_for_a_database(args.database_name, glue_client)

        _check_and_register_location(tables, args.iam_role_arn_lf_resource_register, lf_client)

        for table in tables:
            table_name = table['Name']
            _check_table_managed_by_iam_access_and_enable_opt_in(args.database_name, table_name, args.project_role_arn, lf_client)
            _grant_permissions_to_table(args.project_role_arn, args.database_name, table_name, lf_client)

    except Exception as e:
        print(f"An error occurred during import process: {e}")
        raise

if __name__ == "__main__":
    byogdc_main()
    print(f"Successfully imported resources into provided project")
