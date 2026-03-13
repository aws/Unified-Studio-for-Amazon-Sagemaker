# Requirements Document

## Introduction

This feature replaces the unused `AmazonSageMakerProjectRole` IAM role (deployed via `05-project-role.yaml`) with a customer-managed IAM policy called `MySageMakerStudioAdminIAMPermissiveExecutionPolicy`. The policy ARN is passed to the DataZone Tooling blueprint via the `customerPolicyArns` regional parameter, causing `datazone_usr_role_*` roles to use the custom policy instead of the three default AWS managed policies. This gives the team full control over project user role permissions.

## Glossary

- **SetupOrchestrator**: The Lambda function that orchestrates account setup by deploying StackSet instances across waves
- **CustomPolicy**: The customer-managed IAM policy (`MySageMakerStudioAdminIAMPermissiveExecutionPolicy`) that mirrors the AWS managed `SageMakerStudioAdminIAMPermissiveExecutionPolicy`
- **ToolingBlueprint**: The DataZone Tooling environment blueprint that provisions project infrastructure and user roles
- **BlueprintEnablement**: The CloudFormation template (`blueprint-enablement-iam.yaml`) that configures DataZone environment blueprints with regional parameters
- **AccountRecycler**: The Lambda function that deprovisions and resets project accounts for reuse
- **ProjectUserRole**: The `datazone_usr_role_*` IAM roles created by DataZone during project provisioning
- **StackSet**: AWS CloudFormation StackSets used to deploy resources across multiple project accounts from the org admin account
- **CustomPolicyTemplate**: The CloudFormation template (`05-custom-policy.yaml`) that creates the customer-managed IAM policy

## Requirements

### Requirement 1: Custom Policy Creation

**User Story:** As a platform engineer, I want to deploy a customer-managed IAM policy to project accounts, so that I can control the permissions attached to DataZone project user roles.

#### Acceptance Criteria

1. WHEN the SetupOrchestrator deploys the CustomPolicyTemplate to a project account, THE CustomPolicyTemplate SHALL create an IAM ManagedPolicy resource named `MySageMakerStudioAdminIAMPermissiveExecutionPolicy`
2. THE CustomPolicyTemplate SHALL produce the CustomPolicy document identical to the AWS managed `SageMakerStudioAdminIAMPermissiveExecutionPolicy` (v16, 37 statements)
3. THE CustomPolicyTemplate SHALL output the CustomPolicy ARN as `CustomPolicyArn` for consumption by downstream templates
4. THE CustomPolicyTemplate SHALL tag the CustomPolicy with `ManagedBy: AccountPoolFactory` and `MirroredFrom` referencing the source AWS managed policy ARN

### Requirement 2: Blueprint Enablement Integration

**User Story:** As a platform engineer, I want the Tooling blueprint configuration to include the custom policy ARN, so that DataZone uses the custom policy when creating project user roles.

#### Acceptance Criteria

1. WHEN the SetupOrchestrator provides a non-empty `customPolicyArn`, THE BlueprintEnablement SHALL include the ARN as the `customerPolicyArns` regional parameter for the ToolingBlueprint
2. WHEN the `customerPolicyArns` regional parameter is non-empty, THE ToolingBlueprint SHALL attach only the specified custom policies to newly created ProjectUserRole instances instead of the three default AWS managed policies
3. WHEN the `customPolicyArn` is empty or not provided, THE BlueprintEnablement SHALL pass an empty string for `customerPolicyArns`, preserving default behavior

### Requirement 3: SetupOrchestrator Workflow Update

**User Story:** As a platform engineer, I want the setup orchestrator to deploy the custom policy and pass its ARN to blueprint enablement, so that the end-to-end provisioning flow uses the custom policy automatically.

#### Acceptance Criteria

1. WHEN the SetupOrchestrator executes Wave 1, THE SetupOrchestrator SHALL deploy the `SMUS-AccountPoolFactory-CustomPolicy` StackSet instance in parallel with other Wave 1 tasks (VPC, IAM roles, EventBridge)
2. WHEN the CustomPolicy StackSet instance deployment completes, THE SetupOrchestrator SHALL read the `CustomPolicyArn` output from the stack
3. WHEN the SetupOrchestrator executes Wave 2, THE SetupOrchestrator SHALL pass the `CustomPolicyArn` value to the BlueprintEnablement StackSet as the `CustomerPolicyArns` parameter

### Requirement 4: Backward Compatibility

**User Story:** As a platform engineer, I want the custom policy feature to be toggleable, so that I can disable it without breaking existing account provisioning.

#### Acceptance Criteria

1. WHEN `project_policy.enabled` is set to false in the configuration, THE SetupOrchestrator SHALL skip custom policy deployment and return an empty result
2. WHEN the SetupOrchestrator skips custom policy deployment, THE BlueprintEnablement SHALL receive an empty `customerPolicyArns` parameter, causing the ToolingBlueprint to use the three default AWS managed policies
3. WHEN the configuration uses the old `project_role` schema, THE SetupOrchestrator SHALL handle the migration gracefully without failing the setup workflow

### Requirement 5: Account Recycling Compatibility

**User Story:** As a platform engineer, I want the custom policy to persist across account recycling, so that recycled accounts do not require re-deployment of the policy.

#### Acceptance Criteria

1. WHEN the AccountRecycler deprovisions a project account, THE AccountRecycler SHALL delete only direct CloudFormation stacks (prefixed `DataZone-`) and SHALL NOT delete StackSet-managed resources including the CustomPolicy
2. WHEN a recycled account re-enters the setup workflow, THE SetupOrchestrator SHALL detect the existing CustomPolicy StackSet instance and skip re-deployment
3. WHEN a recycled account re-enters the setup workflow, THE SetupOrchestrator SHALL update the BlueprintEnablement with the existing CustomPolicy ARN

### Requirement 6: StackSet and Template Migration

**User Story:** As a platform engineer, I want the old project role StackSet replaced by the new custom policy StackSet, so that the infrastructure reflects the new approach cleanly.

#### Acceptance Criteria

1. THE CustomPolicyTemplate SHALL replace the old `05-project-role.yaml` template, creating an `AWS::IAM::ManagedPolicy` resource instead of an `AWS::IAM::Role` resource
2. THE StackSet SHALL be named `SMUS-AccountPoolFactory-CustomPolicy`, replacing the old `SMUS-AccountPoolFactory-ProjectRole` name
3. WHEN newly provisioned accounts are inspected, THE accounts SHALL contain the CustomPolicy and SHALL NOT contain a newly created `AmazonSageMakerProjectRole` IAM role

### Requirement 7: Error Handling

**User Story:** As a platform engineer, I want clear error handling when custom policy deployment fails, so that failed accounts can be identified and retried.

#### Acceptance Criteria

1. IF the CustomPolicy StackSet instance deployment fails, THEN THE SetupOrchestrator SHALL mark the account as FAILED and halt the setup workflow before Wave 2
2. IF the CustomPolicy StackSet instance deployment fails, THEN THE SetupOrchestrator SHALL log the failure reason for diagnostic purposes
3. WHEN a FAILED account is retried by the AccountRecycler, THE SetupOrchestrator SHALL clean up the failed StackSet instance before re-attempting deployment

### Requirement 8: Validation and Exit Criteria

**User Story:** As a platform engineer, I want to verify that the custom policy is correctly applied to project user roles, so that I can confirm the feature works end-to-end.

#### Acceptance Criteria

1. WHEN a test project is created in an account with the CustomPolicy and updated BlueprintEnablement, THE ProjectUserRole SHALL have only `MySageMakerStudioAdminIAMPermissiveExecutionPolicy` attached
2. WHEN a test project is created in an account with the CustomPolicy and updated BlueprintEnablement, THE ProjectUserRole SHALL NOT have the three default AWS managed policies (`SageMakerStudioProjectUserRolePolicy`, `SageMakerStudioProjectRoleMachineLearningPolicy`, `SageMakerStudioBedrockKnowledgeBaseServiceRolePolicy`) attached
3. WHEN the CustomPolicy document is compared to the AWS managed `SageMakerStudioAdminIAMPermissiveExecutionPolicy` (v16), THE documents SHALL be identical in content
