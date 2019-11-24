#!/usr/bin/env bash
set -e
source ./env.sh
WORK_PATH=`pwd`
AWS_ACCOUNT_ID=`aws sts get-caller-identity --query Account --output text`
DEFUALT_REGION=`aws configure get region`

echo "This will build and deploy components in $AWS_ACCOUNT_ID $DEFUALT_REGION"
read -p "Press any key to confirm and continue" CONT

# TODO 1. Dependency check, environment check

# - Part 1. Create custom resource type - 
mkdir .build && cd .build

virtualenv .venv
source .venv/bin/activate

pip install cloudformation-cli cloudformation-cli-java-plugin
mkdir CustomResourceType && cd CustomResourceType

# Intiating
( echo $RESOURCE_TYPE ; echo "" ) | cfn init

# Generating templates for build
cfn generate

# Updating the Schema file
rm *.json && cp $WORK_PATH/*.json .

# Validating the Schema
cfn validate

# Building the package usign Maven
mvn package

echo "Deploy to the default region. This might take some time."
cfn submit

# - End Part 1 - 

# - Part 2. Build Lambda layer - 

echo "Building the Lambda layer"

cd $WORK_PATH/.build
mkdir python
pip install -r $WORK_PATH/src/requirements.txt --target python
zip -r9 lambda_layer_packages.zip python
cp $WORK_PATH/src/lambda_* .
zip -r9 lambda_code.zip ./lambda_config_*.py

# - End Part 2 - 

# - Part 3. Deploy with AWS CDK - 
cd $WORK_PATH/cdk
pip install -r requirements.txt
cdk bootstrap
echo "" | cdk deploy --require-approval never
# - End Part 3 - 