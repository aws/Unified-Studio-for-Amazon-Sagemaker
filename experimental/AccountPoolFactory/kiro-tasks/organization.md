1. This package rooted at /Users/amirbo/code/smus-cicd/experimental/AccountPoolFactory can be used by two different audiences: 
    a.  Testing new accounts - A customer engineer that wants to evaluate the package and works on completely new set of accounts for evaluation \ testing purposes. 
    b.  Usage with existing accounts - A customer engineer that wants to deploy this package on existing aws accounts and existing SMUS domain. 

2. I want to put all scripts and cloudformation that are helping tesing new accounts under 'tests'.  These will be resources that help to establish the pre-requisites or variables that are specific for test.  Anything generic that is used by 1b should be under src (code) or scripts or templates . 

3. under that folder structure , a secondary organization would be the persona \ account that these things needs to be deployed in the same way we did under /Users/amirbo/code/smus-cicd/experimental/AccountPoolFactory/templates/cloudformation which is org-admin in the org mgmt account, domain-admin in domain account , and project account.. lets have the names of the accounts consistent across entire package and use the same folder names

4. Next organization folder is "deploy" for scripts that create deploy resourecs and "cleanup" for deleting and removing resources.  If there is a sequence required, clearly add numbers at the beginning to help users. deploy should be able to handle updates too.  

5. put utilty python or scripts under utils.. there are just too many scripts right now. 

clearly add to gitIgnore parameter files and never have any hard coded account numbers or regions in the scripts (not for tests nor for prod)

6. At some point , I want to have a flag or config setting that will decide for all the scripts if to use Cloud formation, or CDK or terraform.  

7. update the architecture document, it should be clear what is deployed in each account both in text and diagrams.  

