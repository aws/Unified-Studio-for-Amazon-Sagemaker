# Implementation Plan: Custom Project Policies

## Overview

Replace the unused `AmazonSageMakerProjectRole` IAM role with a customer-managed IAM policy (`MySageMakerStudioAdminIAMPermissiveExecutionPolicy`) that gets passed to the Tooling blueprint via `customerPolicyArns`. This touches CloudFormation templates (standalone + StackSet), the SetupOrchestrator Lambda, blueprint enablement, and domain config. The policy document must be fetched from the live AWS managed policy (v16, 37 statements) and embedded in the CF template.

## Tasks

- [x] 1. Create the custom policy CloudFormation template
  - [x] 1.1 Fetch the AWS managed `SageMakerStudioAdminIAMPermissiveExecutionPolicy` (v16) policy document and create `templates/cloudformation/03-project-account/deploy/05-custom-policy.yaml`
    - Run `aws iam get-policy-version --policy-arn arn:aws:iam::aws:policy/SageMakerStudioAdminIAMPermissiveExecutionPolicy --version-id v16 --query "PolicyVersion.Document"` to get the full 37-statement document
    - Create `05-custom-policy.yaml` with `AWS::IAM::ManagedPolicy` resource named `MySageMakerStudioAdminIAMPermissiveExecutionPolicy`
    - Include `PolicyName` parameter (default: `MySageMakerStudioAdminIAMPermissiveExecutionPolicy`)
    - Output `CustomPolicyArn` (the `!Ref` of a ManagedPolicy returns its ARN)
    - Tag with `ManagedBy: AccountPoolFactory`, `MirroredFrom: arn:aws:iam::aws:policy/SageMakerStudioAdminIAMPermissiveExecutionPolicy`, `MirroredVersion: v16`
    - Verify the whitespace-stripped policy document fits within IAM managed policy 6,144 character limit; if not, document the issue and consider splitting
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 6.1_

  - [x] 1.2 Create the StackSet version at `templates/cloudformation/stacksets/idc/05-custom-policy.yaml`
    - Copy the standalone template to the StackSet path (same content, both paths must exist)
    - _Requirements: 1.1, 6.1, 6.2_

- [x] 2. Update blueprint enablement templates to accept `customerPolicyArns`
  - [x] 2.1 Update `templates/cloudformation/03-project-account/deploy/blueprint-enablement-iam.yaml`
    - Add `CustomerPolicyArns` parameter (Type: String, Default: "")
    - Add `customerPolicyArns: !Ref CustomerPolicyArns` to the Tooling resource's `RegionalParameters.Parameters`
    - Bump `TemplateVersion` output to "3"
    - _Requirements: 2.1, 2.3_

  - [x] 2.2 Update `templates/cloudformation/stacksets/idc/06-blueprint-enablement.yaml`
    - Add `CustomerPolicyArns` parameter (Type: String, Default: "")
    - Add `customerPolicyArns: !Ref CustomerPolicyArns` to the ToolingLite resource's `RegionalParameters.Parameters` (StackSet IDC path uses ToolingLite, not Tooling)
    - _Requirements: 2.1, 2.3_

- [x] 3. Checkpoint - Validate CloudFormation templates
  - Ensure all modified YAML templates are syntactically valid
  - Verify the `CustomerPolicyArns` parameter is correctly wired in both blueprint enablement templates
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update SetupOrchestrator Lambda
  - [x] 4.1 Replace `deploy_project_role()` with `deploy_custom_policy()` in `src/setup-orchestrator/lambda_function.py`
    - Rename function from `deploy_project_role` to `deploy_custom_policy`
    - Change config keys from `ProjectRoleEnabled`/`ProjectRoleName`/`ProjectRoleManagedPolicyArn` to `ProjectPolicyEnabled`/`ProjectPolicyName`
    - Change StackSet name from `SMUS-AccountPoolFactory-ProjectRole` to `SMUS-AccountPoolFactory-CustomPolicy`
    - Change parameters from `RoleName`/`ManagedPolicyArn` to `PolicyName`
    - Change return key from `projectRoleArn` to `customPolicyArn`, reading `CustomPolicyArn` output
    - Update log messages to reference custom policy instead of project role
    - _Requirements: 3.1, 3.2, 6.2_

  - [x] 4.2 Update `execute_setup_workflow()` to use `deploy_custom_policy` and pass result to `enable_blueprints`
    - Replace `deploy_project_role` call with `deploy_custom_policy` in Wave 1 parallel tasks
    - Rename `project_role_result` variable to `custom_policy_result`
    - Update `update_progress` call: change key from `project_role` to `custom_policy`, update StackSet name in `deployed_stacksets` list
    - Pass `custom_policy_result` to `enable_blueprints` in Wave 2
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 4.3 Update `enable_blueprints()` to accept and pass `custom_policy_result`
    - Add `custom_policy_result: Dict[str, Any] = None` parameter
    - Extract `customPolicyArn` from `custom_policy_result` (default to empty string)
    - Add `{'ParameterKey': 'CustomerPolicyArns', 'ParameterValue': customer_policy_arns}` to the params list
    - _Requirements: 2.1, 2.3, 3.3_

  - [ ]* 4.4 Write unit tests for `deploy_custom_policy` and updated `enable_blueprints`
    - Test `deploy_custom_policy` returns `{'customPolicyArn': ...}` on success
    - Test `deploy_custom_policy` returns `{}` when `ProjectPolicyEnabled` is `'false'`
    - Test `enable_blueprints` includes `CustomerPolicyArns` param when `custom_policy_result` is provided
    - Test `enable_blueprints` passes empty string for `CustomerPolicyArns` when `custom_policy_result` is None
    - **Property 1: Blueprint parameter propagation**
    - **Property 2: Feature toggle disablement**
    - **Validates: Requirements 2.1, 2.3, 3.3, 4.1, 4.2**

- [x] 5. Update domain configuration
  - [x] 5.1 Update `domain-config.yaml` schema from `project_role` to `project_policy`
    - Replace the `project_role` section with `project_policy` section
    - Change keys: `enabled: true`, `policy_name: MySageMakerStudioAdminIAMPermissiveExecutionPolicy` (remove `role_name` and `managed_policy_arn`)
    - _Requirements: 4.1, 4.3_

  - [x] 5.2 Update `load_config()` or config consumers to handle new `project_policy` keys
    - Ensure SSM parameter path or config loading maps `project_policy.enabled` → `ProjectPolicyEnabled` and `project_policy.policy_name` → `ProjectPolicyName`
    - Add backward compatibility: if old `ProjectRoleEnabled` key exists but `ProjectPolicyEnabled` does not, treat as enabled with default policy name
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 6. Checkpoint - Code review and local validation
  - Ensure all code changes are consistent (no references to old `deploy_project_role` or `ProjectRole` StackSet remain in active code paths)
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. End-to-end validation on test account 682839842827
  - [x] 7.1 Deploy custom policy template to test account and verify policy creation
    - Deploy `05-custom-policy.yaml` via CloudFormation to account `682839842827`
    - Verify policy exists: `aws iam get-policy --policy-arn arn:aws:iam::682839842827:policy/MySageMakerStudioAdminIAMPermissiveExecutionPolicy`
    - Compare policy document to AWS managed version — must be identical
    - _Requirements: 1.1, 1.2, 8.3_

  - [x] 7.2 Update blueprint enablement with `customerPolicyArns` and create test project
    - Update the blueprint enablement stack in account `682839842827` to include `CustomerPolicyArns` parameter with the custom policy ARN
    - Create a test project targeting account `682839842827` via DataZone API
    - Verify the `datazone_usr_role_*` has ONLY `MySageMakerStudioAdminIAMPermissiveExecutionPolicy` (not the default three)
    - Clean up: delete the test project
    - _Requirements: 2.1, 2.2, 8.1, 8.2_

- [ ] 8. Final checkpoint - Feature complete
  - Ensure all tests pass, ask the user if questions arise.
  - Confirm exit criteria: `datazone_usr_role_*` uses only the custom policy, not the three defaults

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The policy document is ~22KB JSON with 37 statements — must verify it fits within IAM managed policy 6,144 character limit after whitespace removal during task 1.1
- Both standalone (`03-project-account/deploy/`) and StackSet (`stacksets/idc/`) template paths must be updated
- The StackSet IDC blueprint enablement uses `ToolingLite` (not `Tooling`) — the `customerPolicyArns` parameter must be added to the correct resource
- Config is loaded from SSM Parameter Store with flat keys — the `project_policy` YAML section maps to `ProjectPolicyEnabled` and `ProjectPolicyName` SSM parameters
- Property tests validate universal correctness properties; unit tests validate specific examples and edge cases
- Checkpoints ensure incremental validation
