"""Context resolver for workflow YAML variable substitution."""

import os
import re
from typing import Any, Dict


class ContextResolver:
    """Resolves context variables in workflow YAMLs."""

    def __init__(
        self,
        project_name: str,
        domain_id: str,
        domain_name: str,
        region: str,
        env_vars: Dict[str, str] = None,
    ):
        """
        Initialize context resolver.

        Args:
            project_name: Project name
            domain_id: Domain ID
            domain_name: Domain name
            region: AWS region
            env_vars: Optional environment variables dict (defaults to os.environ)
        """
        self.project_name = project_name
        self.domain_id = domain_id
        self.domain_name = domain_name
        self.region = region
        self.env_vars = env_vars or dict(os.environ)
        self._context = None

    def _build_context(self) -> Dict[str, Any]:
        """Build context from project and environment."""
        if self._context:
            return self._context

        from . import datazone, connections

        # Get project ID
        project_id = datazone.get_project_id_by_name(
            self.project_name, self.domain_id, self.region
        )

        # Get project IAM role
        iam_role = datazone.get_project_user_role_arn(
            self.project_name, self.domain_name, self.region
        )

        # Extract role name from ARN (arn:aws:iam::123:role/RoleName -> RoleName)
        iam_role_name = iam_role.split("/")[-1] if iam_role else None

        # Get KMS key (if available)
        kms_key_arn = None
        try:
            # Try to get KMS key from project metadata
            datazone_client = datazone._get_datazone_client(self.region)
            project_response = datazone_client.get_project(
                domainIdentifier=self.domain_id, identifier=project_id
            )
            # KMS key might be in project metadata
            kms_key_arn = project_response.get("kmsKeyArn")
        except Exception:
            pass

        context = {
            "proj": {
                "id": project_id,
                "name": self.project_name,
                "domain_id": self.domain_id,
                "iam_role": iam_role,
                "iam_role_arn": iam_role,
                "iam_role_name": iam_role_name,
                "kms_key_arn": kms_key_arn or "",
                "connection": {},
            },
            "env": self.env_vars,
        }

        # Get all project connections using our helper
        project_connections = connections.get_project_connections(
            self.project_name, self.domain_name, self.region
        )

        # Add connections to context
        for conn_name, conn_data in project_connections.items():
            context["proj"]["connection"][conn_name] = self._flatten_connection(
                conn_data
            )

        self._context = context
        return context

    def _flatten_connection(self, conn_data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten connection properties to simple key-value pairs."""
        flat = {}

        # Add environment user role if available
        if "environmentUserRole" in conn_data:
            flat["environmentUserRole"] = conn_data["environmentUserRole"]

        # S3 properties
        if "s3Uri" in conn_data:
            flat["s3Uri"] = conn_data["s3Uri"]
        if "bucket_name" in conn_data:
            flat["bucket_name"] = conn_data["bucket_name"]

        # MLflow properties
        if "trackingServerArn" in conn_data:
            flat["trackingServerArn"] = conn_data["trackingServerArn"]
        if "trackingServerName" in conn_data:
            flat["trackingServerName"] = conn_data["trackingServerName"]

        # Spark Glue properties
        if "sparkGlueProperties" in conn_data:
            props = conn_data["sparkGlueProperties"]
            flat["glueVersion"] = props.get("glueVersion")
            flat["workerType"] = props.get("workerType")
            flat["numberOfWorkers"] = props.get("numberOfWorkers")

        # Athena properties
        if "workgroupName" in conn_data:
            flat["workgroupName"] = conn_data["workgroupName"]

        return flat

    def resolve(self, content: str) -> str:
        """
        Resolve all context variables in content.

        Args:
            content: String content with {env.VAR} or {proj.property} variables

        Returns:
            Content with variables replaced
        """
        context = self._build_context()

        # Pattern matches {env.VAR} or {proj.property.nested}
        pattern = r"\{(env|proj)\.([^}]+)\}"

        def replacer(match):
            namespace = match.group(1)
            path = match.group(2)

            try:
                value = context[namespace]

                # Special handling for proj.connection.* paths
                if namespace == "proj" and path.startswith("connection."):
                    # Split into: connection, conn_name, property
                    parts = path.split(".", 2)
                    if len(parts) >= 3:
                        # parts[0] = "connection"
                        # parts[1] = first part of connection name
                        # parts[2] = rest (could be more connection name + property)

                        # Find the connection name by checking what exists in context
                        conn_dict = value["connection"]
                        remaining = path[11:]  # Remove "connection."

                        # Try to match connection names (they can have dots)
                        for conn_name in conn_dict.keys():
                            if remaining.startswith(conn_name + "."):
                                # Found the connection
                                property_name = remaining[len(conn_name) + 1 :]
                                return str(conn_dict[conn_name][property_name])
                            elif remaining == conn_name:
                                # Requesting the whole connection object
                                return str(conn_dict[conn_name])

                        # Connection not found
                        return match.group(0)
                else:
                    # Normal path traversal
                    for key in path.split("."):
                        value = value[key]
                    return str(value)
            except (KeyError, TypeError):
                # Keep original if not found
                return match.group(0)

        return re.sub(pattern, replacer, content)
