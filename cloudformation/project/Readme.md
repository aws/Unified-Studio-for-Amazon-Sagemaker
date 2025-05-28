# AWS SMUS Project Creation Template

## Overview

This CloudFormation template creates a SMUS project and assigns project memberships to specified users. The template uses AWS::LanguageExtensions transform to iterate through a list of users and create project memberships.


## Parameters

```yaml
Parameters:
  DomainId:
    Description: Domain for which blueprint needs to be enabled
    Type: String
  ProjectProfileId:
    Description: Project Profile id for which we need to create project
    Type: String
  Name:
    Description: Name of the project
    Type: String
  UsersList:
    Description: Users for the project
    Type: CommaDelimitedList
```

## Resources

### Project

```yaml
Resources:
  Project:
    Type: AWS::DataZone::Project
    Properties:
      Description: "Testing CFN Project"
      DomainIdentifier: !Ref DomainId
      Name: !Ref Name
      ProjectProfileId: !Ref ProjectProfileId
```

### Project Memberships

```yaml
  "Fn::ForEach::Users":
    - User
    - !Ref UsersList
    - "${User}ProjectMembership":
        Type: "AWS::DataZone::ProjectMembership"
        Properties:
          DomainIdentifier: !Ref DomainId
          ProjectIdentifier: !GetAtt Project.Id
          Member:
            UserIdentifier: !Ref User
          Designation: "PROJECT_OWNER"
```

## Usage

### Prerequisites
- Existing AWS SMUS domain
- Valid Project Profile ID
- List of valid user identifiers
- Necessary IAM permissions

### Deployment

1. Create a parameters file (parameters.json):

```yaml
Parameters:
  DomainId:
    Description: Domain for which blueprint needs to be enabled
    Type: String
  ProjectProfileId:
    Description: Project Profile Id for which we need to create Project
    Type: String
  Name:
    Description: Name of the project
    Type: String
  UsersList:
    Description: Users that needs to be added to this 
    Type: CommaDelimitedList
```

2. Deploy using AWS CLI:

```bash
aws cloudformation create-stack \
  --stack-name my-smus-project \
  --template-body file://project-template.yaml \
  --parameters file://parameters.json
```

## Important Notes

1. All users in UsersList become PROJECT_OWNER
4. Sequential project membership creation
