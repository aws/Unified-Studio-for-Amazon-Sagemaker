"""Helper for creating DataZone connections with proper status waiting."""

import time
from typing import Any, Dict

import boto3


class ConnectionCreator:
    """Helper class for creating DataZone connections with status monitoring."""

    def __init__(self, domain_id: str, region: str = "us-east-1"):
        self.domain_id = domain_id
        self.region = region
        self.client = boto3.client("datazone", region_name=region)
        self._custom_client = None
        self._temp_dir = None

    def _get_custom_datazone_client(self):
        """Get DataZone client with custom model that supports MLFlow connections."""
        if self._custom_client is None:
            import json
            import os
            import shutil
            import tempfile
            from pathlib import Path

            from botocore.loaders import Loader
            from botocore.session import Session as BotocoreSession

            # Get the path to the custom DataZone model
            current_dir = Path(__file__).parent.parent
            model_path = current_dir / "resources" / "datazone-2018-05-10.json"

            if not model_path.exists():
                raise FileNotFoundError(
                    f"Custom DataZone model not found at {model_path}"
                )

            # Load the custom model
            with open(model_path, "r") as f:
                service_model_data = json.load(f)

            # Create a temporary directory for the custom model
            temp_dir = tempfile.mkdtemp()

            try:
                # Create the expected directory structure for botocore
                service_dir = os.path.join(temp_dir, "datazone", "2018-05-10")
                os.makedirs(service_dir, exist_ok=True)

                # Write the service model
                service_file = os.path.join(service_dir, "service-2.json")
                with open(service_file, "w") as f:
                    json.dump(service_model_data, f)

                # Create a custom loader with our model directory
                loader = Loader(extra_search_paths=[temp_dir])

                # Create a botocore session with custom loader
                botocore_session = BotocoreSession()
                botocore_session.register_component("data_loader", loader)

                # Get credentials from boto3 session
                boto3_session = boto3.Session()
                credentials = boto3_session.get_credentials()
                botocore_session.set_credentials(
                    access_key=credentials.access_key,
                    secret_key=credentials.secret_key,
                    token=credentials.token,
                )

                # Get endpoint URL
                endpoint_url = os.environ.get("DATAZONE_ENDPOINT_URL")

                # Create the custom client
                self._custom_client = botocore_session.create_client(
                    "datazone",
                    region_name=self.region,
                    endpoint_url=endpoint_url,
                    api_version="2018-05-10",
                )

                # Store temp_dir for cleanup later
                self._temp_dir = temp_dir

            except Exception as e:
                # Clean up temp directory on error
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise e

        return self._custom_client

    def create_from_config(
        self,
        environment_id: str,
        connection_config,
        description: str = None,
    ) -> str:
        """
        Create connection from manifest ConnectionConfig.

        Args:
            environment_id: DataZone environment ID
            connection_config: ConnectionConfig object from manifest
            description: Optional description

        Returns:
            Connection ID
        """
        # Create connection directly from config properties
        # Environment variable substitution (${STS_REGION}, ${STS_ACCOUNT_ID})
        # happens during manifest loading in utils.substitute_env_vars()
        return self.create_connection(
            environment_id=environment_id,
            name=connection_config.name,
            connection_type=connection_config.type,
            description=description,
            **connection_config.properties,
        )

    def create_connection(
        self,
        environment_id: str,
        name: str,
        connection_type: str,
        description: str = None,
        **kwargs,
    ) -> str:
        """
        Create a DataZone connection and wait for it to be ready.

        Args:
            environment_id: DataZone environment ID
            name: Connection name
            connection_type: Type of connection (S3, IAM, SPARK_GLUE, etc.)
            description: Optional description
            **kwargs: Connection-specific properties

        Returns:
            Connection ID

        Raises:
            Exception: If connection creation fails or times out
        """
        props = self._build_connection_props(connection_type, **kwargs)

        # Use custom client for MLFlow connections
        client = (
            self._get_custom_datazone_client()
            if connection_type == "MLFLOW"
            else self.client
        )

        try:
            response = client.create_connection(
                domainIdentifier=self.domain_id,
                environmentIdentifier=environment_id,
                name=name,
                description=description or f"{connection_type} connection",
                props=props,
            )

            connection_id = response["connectionId"]

            # Wait for connection to be ready
            self._wait_for_connection_ready(connection_id, connection_type)

            return connection_id

        except Exception as e:
            raise Exception(
                f"Failed to create {connection_type} connection '{name}': {e}"
            )

    def _build_connection_props(self, connection_type: str, **kwargs) -> Dict[str, Any]:
        """Build connection properties based on type."""
        if connection_type == "S3":
            return {
                "s3Properties": {
                    "s3Uri": kwargs.get("s3_uri", "s3://default-bucket/data/")
                }
            }
        elif connection_type == "IAM":
            return {
                "iamProperties": {
                    "glueLineageSyncEnabled": kwargs.get("glue_lineage_sync", True)
                }
            }
        elif connection_type == "SPARK_GLUE":
            return {
                "sparkGlueProperties": {
                    "glueVersion": kwargs.get("glue_version", "4.0"),
                    "workerType": kwargs.get("worker_type", "G.1X"),
                    "numberOfWorkers": kwargs.get("num_workers", 3),
                }
            }
        elif connection_type == "SPARK_EMR":
            return {
                "sparkEmrProperties": {
                    "computeArn": kwargs.get("compute_arn"),
                    "runtimeRole": kwargs.get("runtime_role"),
                }
            }
        elif connection_type == "REDSHIFT":
            return {
                "redshiftProperties": {
                    "storage": {
                        "clusterName": kwargs.get("cluster_name", "default-cluster")
                    },
                    "databaseName": kwargs.get("database_name", "dev"),
                    "host": kwargs.get(
                        "host",
                        "default-cluster.abc123.us-east-1.redshift.amazonaws.com",
                    ),
                    "port": kwargs.get("port", 5439),
                }
            }
        elif connection_type == "ATHENA":
            return {
                "athenaProperties": {
                    "workgroupName": kwargs.get("workgroup", "primary")
                }
            }
        elif connection_type == "MLFLOW":
            tracking_server_arn = kwargs.get("trackingServerArn") or kwargs.get(
                "tracking_server_arn"
            )

            props = {
                "mlflowProperties": {
                    "trackingServerArn": tracking_server_arn,
                }
            }
            print(f"🔍 DEBUG: MLflow props being returned: {props}")

            return props
        elif connection_type == "WORKFLOWS_MWAA":
            return {
                "workflowsMwaaProperties": {
                    "mwaaEnvironmentName": kwargs.get(
                        "mwaa_environment_name", "default-mwaa-env"
                    )
                }
            }
        elif connection_type == "WORKFLOWS_SERVERLESS":
            return {"workflowsServerlessProperties": {}}
        else:
            raise ValueError(f"Unsupported connection type: {connection_type}")

    def _wait_for_connection_ready(
        self, connection_id: str, connection_type: str, max_wait: int = 120
    ):
        """Wait for connection to be ready."""
        wait_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            try:
                detail = self.client.get_connection(
                    domainIdentifier=self.domain_id, identifier=connection_id
                )

                status = self._extract_status(detail, connection_type)

                if status == "READY":
                    return
                elif status in ["FAILED", "DELETING"]:
                    raise Exception(f"Connection failed with status: {status}")

                time.sleep(wait_interval)
                elapsed += wait_interval

            except Exception as e:
                if "failed with status" in str(e):
                    raise
                # Continue waiting for other errors
                time.sleep(wait_interval)
                elapsed += wait_interval

        # Don't fail if timeout - connection might still work
        print(
            f"Warning: Connection {connection_id} did not become READY within {max_wait}s"
        )

    def _extract_status(
        self, connection_detail: Dict[str, Any], connection_type: str
    ) -> str:
        """Extract status from connection details based on type."""
        props = connection_detail.get("props", {})

        # Only GLUE-based connections have status field
        if connection_type in ["GLUE", "SNOWFLAKE", "JDBC"]:
            return props.get("glueProperties", {}).get("status", "UNKNOWN")
        elif connection_type == "S3":
            return props.get("s3Properties", {}).get("status", "READY")
        elif connection_type in ["SPARK_GLUE", "SPARK_EMR"]:
            return props.get("sparkGlueProperties", {}).get("status") or props.get(
                "sparkEmrProperties", {}
            ).get("status", "READY")
        elif connection_type == "REDSHIFT":
            return props.get("redshiftProperties", {}).get("status", "READY")
        elif connection_type == "ATHENA":
            return props.get("athenaProperties", {}).get("status", "READY")
        else:
            # Connections without status field (IAM, MLFLOW, etc.) are ready immediately
            return "READY"

    def update_connection(
        self,
        connection_id: str,
        name: str,
        connection_type: str,
        props: Dict[str, Any],
        environment_id: str,
    ) -> str:
        """Update an existing connection."""
        print(f"🔄 Updating connection '{name}'")

        try:
            # Use custom client for MLFlow connections, standard client for others
            if connection_type == "MLFLOW":
                client = self._get_custom_datazone_client()
            else:
                client = self.client

            client.update_connection(
                domainIdentifier=self.domain_id, identifier=connection_id, props=props
            )
            print(f"✅ Connection '{name}' updated: {connection_id}")
            return connection_id
        except Exception as e:
            raise Exception(
                f"Failed to update {connection_type} connection '{name}': {str(e)}"
            )

    def cleanup(self):
        """Clean up temporary directory."""
        if hasattr(self, "_temp_dir") and self._temp_dir:
            import shutil

            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
