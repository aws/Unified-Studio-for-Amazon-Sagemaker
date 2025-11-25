"""Integration test for Dashboard-Glue-Quick workflow deployment."""

import pytest
import os
import subprocess
import re
import boto3
from tests.integration.base import IntegrationTestBase


class TestDashboardGlueQuickWorkflow(IntegrationTestBase):
    """Test Dashboard-Glue-Quick workflow deployment with QuickSight."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()
        self.cleanup_glue_databases()
        self.cleanup_quicksight_dashboards()
        self.setup_quicksight_test_dashboard()

    def cleanup_quicksight_dashboards(self):
        """Delete test QuickSight dashboards from previous runs."""
        quicksight_client = boto3.client('quicksight', region_name='us-east-2')
        account_id = boto3.client('sts').get_caller_identity()['Account']
        
        # Only cleanup deployed dashboard, keep source dashboard
        dashboards_to_delete = ['deployed-test-covid-dashboard']
        
        for dashboard_id in dashboards_to_delete:
            try:
                quicksight_client.delete_dashboard(
                    AwsAccountId=account_id,
                    DashboardId=dashboard_id
                )
                self.logger.info(f"✅ Deleted QuickSight dashboard: {dashboard_id}")
            except quicksight_client.exceptions.ResourceNotFoundException:
                pass
            except Exception as e:
                self.logger.info(f"⚠️ Could not delete dashboard {dashboard_id}: {e}")

    def setup_quicksight_test_dashboard(self):
        """Import test dashboard if it doesn't exist."""
        from src.smus_cicd.helpers.quicksight import lookup_dashboard_by_name
        
        quicksight_client = boto3.client('quicksight', region_name='us-east-2')
        account_id = boto3.client('sts').get_caller_identity()['Account']
        dashboard_name = 'TotalDeathByCountry'
        
        try:
            # Check if dashboard exists by name
            dashboard_id = lookup_dashboard_by_name(dashboard_name, account_id, 'us-east-2')
            self.logger.info(f"✅ Test dashboard already exists: {dashboard_name} (ID: {dashboard_id})")
        except Exception:
            # Dashboard doesn't exist, import it
            self.logger.info(f"📊 Importing test dashboard: {dashboard_name}")
            setup_script = os.path.join(
                os.path.dirname(__file__),
                "../../../../examples/analytic-workflow/dashboard-glue-quick/quicksight/setup_test_dashboard.py"
            )
            result = subprocess.run(
                ["python", setup_script],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.logger.info(f"✅ Test dashboard imported: {dashboard_name}")
            else:
                self.logger.warning(f"⚠️ Failed to import test dashboard: {result.stderr}")

    def cleanup_glue_databases(self):
        """Delete test Glue databases and S3 data."""
        glue_client = boto3.client('glue', region_name='us-east-1')
        s3_client = boto3.client('s3', region_name='us-east-1')
        
        # Also cleanup covid19_db to force recreation with fixed script
        glue_client_us_east_2 = boto3.client('glue', region_name='us-east-2')
        try:
            glue_client_us_east_2.delete_table(DatabaseName='covid19_db', Name='us_simplified')
            self.logger.info("✅ Deleted old covid19_db.us_simplified table")
        except glue_client_us_east_2.exceptions.EntityNotFoundException:
            pass
        except Exception as e:
            self.logger.warning(f"⚠️ Could not delete covid19_db.us_simplified: {e}")
        
        databases_to_delete = ['analytic_workflow_test_db', 'covid19_summary_db']
        
        for db_name in databases_to_delete:
            try:
                # Get database location before deleting
                try:
                    db_info = glue_client.get_database(Name=db_name)
                    location_uri = db_info.get('Database', {}).get('LocationUri', '')
                    
                    # Delete S3 data if location exists
                    if location_uri.startswith('s3://'):
                        bucket_and_key = location_uri[5:].split('/', 1)
                        bucket = bucket_and_key[0]
                        prefix = bucket_and_key[1] if len(bucket_and_key) > 1 else ''
                        
                        # Delete all objects in the location
                        paginator = s3_client.get_paginator('list_objects_v2')
                        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                            objects = page.get('Contents', [])
                            if objects:
                                delete_keys = [{'Key': obj['Key']} for obj in objects]
                                s3_client.delete_objects(Bucket=bucket, Delete={'Objects': delete_keys})
                                self.logger.info(f"✅ Deleted S3 data: s3://{bucket}/{prefix}")
                except glue_client.exceptions.EntityNotFoundException:
                    pass
                
                # Delete the database
                glue_client.delete_database(Name=db_name)
                self.logger.info(f"✅ Deleted Glue database: {db_name}")
            except glue_client.exceptions.EntityNotFoundException:
                pass
            except Exception as e:
                self.logger.info(f"⚠️ Could not delete database {db_name}: {e}")

    def get_pipeline_file(self):
        return os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/dashboard-glue-quick/manifest.yaml"
        )

    def verify_quicksight_dashboard_deployed(self):
        """Verify QuickSight dashboard was deployed successfully."""
        quicksight_client = boto3.client('quicksight', region_name='us-east-2')
        account_id = boto3.client('sts').get_caller_identity()['Account']
        dashboard_prefix = 'deployed-test-covid-'
        
        try:
            # List dashboards and find one with our prefix
            response = quicksight_client.list_dashboards(AwsAccountId=account_id)
            dashboards = response.get('DashboardSummaryList', [])
            
            deployed_dashboard = None
            for dashboard in dashboards:
                if dashboard['DashboardId'].startswith(dashboard_prefix):
                    deployed_dashboard = dashboard
                    break
            
            if not deployed_dashboard:
                pytest.fail(f"Dashboard with prefix {dashboard_prefix} not found after deploy")
            
            dashboard_id = deployed_dashboard['DashboardId']
            self.logger.info(f"✅ Dashboard deployed: {dashboard_id}")
            self.logger.info(f"   Name: {deployed_dashboard['Name']}")
            
            # Get full dashboard details
            detail_response = quicksight_client.describe_dashboard(
                AwsAccountId=account_id,
                DashboardId=dashboard_id
            )
            self.logger.info(f"   Version: {detail_response['Dashboard']['Version']['VersionNumber']}")
            
            # Verify dashboard name has deployment prefix
            assert deployed_dashboard['Name'].startswith('deployed-test-'), "Dashboard name should have deployment prefix"
            
            # Check datasets exist
            datasets = quicksight_client.list_data_sets(AwsAccountId=account_id)
            dataset_count = len(datasets.get('DataSetSummaries', []))
            self.logger.info(f"✅ Datasets found: {dataset_count}")
            assert dataset_count > 0, "Should have at least one dataset"
            
            # Check data sources exist
            data_sources = quicksight_client.list_data_sources(AwsAccountId=account_id)
            source_count = len(data_sources.get('DataSources', []))
            self.logger.info(f"✅ Data sources found: {source_count}")
            assert source_count > 0, "Should have at least one data source"
            
        except quicksight_client.exceptions.ResourceNotFoundException:
            pytest.fail(f"Dashboard {dashboard_id} not found after deploy")
        except Exception as e:
            pytest.fail(f"Error verifying QuickSight dashboard: {e}")

    @pytest.mark.integration
    def test_dashboard_glue_quick_workflow_deployment(self):
        """Test Dashboard-Glue-Quick workflow deployment with QuickSight."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        workflow_name = "covid_dashboard_glue_quick_pipeline"
        
        # Cleanup: Delete QuickSight deployed assets
        self.logger.info("\n=== Cleanup: Delete QuickSight deployed assets ===")
        try:
            import boto3
            qs = boto3.client('quicksight', region_name='us-east-2')
            account_id = '198737698272'
            
            # Delete dashboards
            dashboards = qs.list_dashboards(AwsAccountId=account_id)['DashboardSummaryList']
            for dash in dashboards:
                if dash['DashboardId'].startswith('deployed-test'):
                    qs.delete_dashboard(AwsAccountId=account_id, DashboardId=dash['DashboardId'])
                    self.logger.info(f"✅ Deleted dashboard: {dash['DashboardId']}")
            
            # Delete datasets
            datasets = qs.list_data_sets(AwsAccountId=account_id)['DataSetSummaries']
            for ds in datasets:
                if ds['DataSetId'].startswith('deployed-test'):
                    qs.delete_data_set(AwsAccountId=account_id, DataSetId=ds['DataSetId'])
                    self.logger.info(f"✅ Deleted dataset: {ds['DataSetId']}")
            
            # Delete data sources
            sources = qs.list_data_sources(AwsAccountId=account_id)['DataSources']
            for src in sources:
                if src['DataSourceId'].startswith('deployed-test'):
                    qs.delete_data_source(AwsAccountId=account_id, DataSourceId=src['DataSourceId'])
                    self.logger.info(f"✅ Deleted data source: {src['DataSourceId']}")
                    
        except Exception as e:
            self.logger.info(f"⚠️ Could not delete QuickSight assets: {e}")
        
        # Cleanup: Remove etl directory from test project S3
        self.logger.info("\n=== Cleanup: Remove test project S3 etl directory ===")
        try:
            subprocess.run(
                ["aws", "s3", "rm", "s3://amazon-sagemaker-198737698272-us-east-1-4pg255jku47vdz/shared/dashboard-glue-quick/", "--recursive"],
                capture_output=True,
                text=True
            )
            self.logger.info("✅ Cleaned test project S3 etl directory")
        except Exception as e:
            self.logger.info(f"⚠️ Could not clean S3: {e}")

        # Step 1: Describe --connect
        self.logger.info("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        assert result["success"], f"Describe --connect failed: {result['output']}"
        self.logger.info("✅ Describe --connect successful")

        # Step 2: Upload ETL code to S3 (dev project)
        self.logger.info("\n=== Step 2: Upload ETL Code to S3 (dev project) ===")
        etl_dir = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/dashboard-glue-quick"
        ))
        self.upload_code_to_dev_project(
            pipeline_file=pipeline_file,
            source_dir=etl_dir,
            target_prefix="dashboard-glue-quick/"
        )

        # Step 3: Bundle from dev
        self.logger.info("\n=== Step 3: Bundle from dev ===")
        result = self.run_cli_command(["bundle", "--manifest", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        self.logger.info("✅ Bundle successful")

        # Step 4: Deploy
        self.logger.info("\n=== Step 4: Deploy ===")
        result = self.run_cli_command(["deploy", "test", "--manifest", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        self.logger.info("✅ Deploy successful")

        # Step 4.5: Verify QuickSight Dashboard Deployed
        self.logger.info("\n=== Step 4.5: Verify QuickSight Dashboard ===")
        self.verify_quicksight_dashboard_deployed()

        # Step 5: Monitor
        self.logger.info("\n=== Step 5: Monitor ===")
        result = self.run_cli_command(["monitor", "--targets", "test", "--manifest", pipeline_file])
        assert result["success"], f"Monitor failed: {result['output']}"
        self.logger.info("✅ Monitor successful")

        # Step 6: Run workflow and extract ARN
        self.logger.info("\n=== Step 6: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--manifest", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        
        # Extract workflow ARN from run output
        workflow_arn_match = re.search(r'🔗 ARN: (arn:aws:airflow-serverless:[^\s]+)', result["output"])
        workflow_arn = workflow_arn_match.group(1) if workflow_arn_match else None
        
        if workflow_arn:
            self.logger.info(f"✅ Workflow started: {workflow_arn}")
        else:
            self.logger.info("✅ Workflow started (ARN not found)")

        # Step 7: Monitor workflow status
        self.logger.info("\n=== Step 7: Monitor Workflow Status ===")
        result = self.run_cli_command(["monitor", "--targets", "test", "--manifest", pipeline_file])
        assert result["success"], f"Monitor after run failed: {result['output']}"
        self.logger.info("✅ Monitor after run successful")

        # Step 8: Wait for workflow completion using logs
        self.logger.info("\n=== Step 8: Wait for Workflow Completion ===")
        if workflow_arn:
            self.logger.info(f"📋 Monitoring workflow: {workflow_arn}")
            result = self.run_cli_command(["logs", "--live", "--workflow", workflow_arn])
            
            # Extract run_id from logs output
            run_id_match = re.search(r"Run:\s+([a-zA-Z0-9]+)", result["output"])
            run_id = run_id_match.group(1) if run_id_match else None
            
            # Assert workflow run started after test began
            if run_id:
                self.assert_workflow_run_after_test_start(run_id, workflow_arn)
            
            # logs --live waits for completion and returns success/failure
            if result["success"]:
                self.logger.info("✅ Workflow completed successfully")
            else:
                self.logger.info(f"⚠️ Workflow failed or timed out: {result['output']}")
                # Don't fail the test yet - let pipeline tests determine success
        else:
            self.logger.info("⚠️ Could not extract workflow ARN, skipping log wait")
        
        # Step 8.5: Validate table data
        self.logger.info("\n=== Step 8.5: Validate Table Data ===")
        
        # Grant Lake Formation permissions to current role
        import boto3
        sts = boto3.client('sts', region_name='us-east-2')
        caller = sts.get_caller_identity()
        role_arn = caller['Arn'].replace(':assumed-role/', ':role/').rsplit('/', 1)[0]
        
        lf = boto3.client('lakeformation', region_name='us-east-2')
        
        # Grant permissions on database first
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': role_arn},
                Resource={'Database': {'Name': 'covid19_db'}},
                Permissions=['DESCRIBE']
            )
            self.logger.info(f"✅ Granted database permissions to {role_arn}")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not grant database permissions: {e}")
        
        # Grant permissions on table
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': role_arn},
                Resource={'Table': {'DatabaseName': 'covid19_db', 'Name': 'us_simplified'}},
                Permissions=['DESCRIBE']
            )
            self.logger.info(f"✅ Granted table DESCRIBE permissions to {role_arn}")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not grant table permissions: {e}")
        
        # Grant column-level SELECT permissions
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': role_arn},
                Resource={'TableWithColumns': {
                    'DatabaseName': 'covid19_db',
                    'Name': 'us_simplified',
                    'ColumnWildcard': {}
                }},
                Permissions=['SELECT']
            )
            self.logger.info(f"✅ Granted column SELECT permissions to {role_arn}")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not grant column permissions: {e}")
        
        # Query table row count
        athena = boto3.client('athena', region_name='us-east-2')
        query_id = athena.start_query_execution(
            QueryString='SELECT COUNT(*) as row_count FROM covid19_db.us_simplified',
            ResultConfiguration={'OutputLocation': 's3://amazon-sagemaker-198737698272-us-east-2-5330xnk7amt221/athena-results/'}
        )['QueryExecutionId']
        
        import time
        time.sleep(5)
        
        result = athena.get_query_results(QueryExecutionId=query_id)
        row_count = int(result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue'])
        self.logger.info(f"📊 Table row count: {row_count:,}")
        assert row_count > 1000000, f"Expected >1M rows, got {row_count:,}"
        self.logger.info("✅ Row count validation passed")
        
        # Query first 10 records
        query_id = athena.start_query_execution(
            QueryString='SELECT * FROM covid19_db.us_simplified LIMIT 10',
            ResultConfiguration={'OutputLocation': 's3://amazon-sagemaker-198737698272-us-east-2-5330xnk7amt221/athena-results/'}
        )['QueryExecutionId']
        
        # Wait for query to complete
        for _ in range(10):
            time.sleep(3)
            status = athena.get_query_execution(QueryExecutionId=query_id)
            state = status['QueryExecution']['Status']['State']
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
        
        if state != 'SUCCEEDED':
            error_msg = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            self.logger.error(f"❌ Query failed: {error_msg}")
            assert False, f"Query failed with state: {state}, reason: {error_msg}"
        
        result = athena.get_query_results(QueryExecutionId=query_id)
        rows = result['ResultSet']['Rows']
        
        # Validate we have data rows (header + at least 1 data row)
        assert len(rows) >= 2, f"Expected at least 2 rows (header + data), got {len(rows)}"
        
        # Validate first data row has valid date format (not Python code)
        first_data_row = rows[1]['Data']
        date_value = first_data_row[0].get('VarCharValue', '')
        assert not date_value.startswith('import '), f"Table contains Python code instead of CSV data: {date_value}"
        assert not date_value.startswith('def '), f"Table contains Python code instead of CSV data: {date_value}"
        
        # Validate date format (YYYY-MM-DD)
        assert re.match(r'\d{4}-\d{2}-\d{2}', date_value), f"Invalid date format: {date_value}"
        
        self.logger.info(f"✅ First record date: {date_value}")
        self.logger.info("✅ Table data validation passed")
        
        # Step 9: Run pipeline tests
        self.logger.info("\n=== Step 9: Run Pipeline Tests ===")
        result = self.run_cli_command(["test", "--targets", "test", "--test-output", "console", "--manifest", pipeline_file])
        assert result["success"], f"Pipeline tests failed: {result['output']}"
        self.logger.info("✅ Pipeline tests passed")
        self.logger.info("✅ Dashboard-Glue-Quick workflow test completed successfully")
