# The script will undo what the deployment script did

AWS_ACCOUNT_ID=`aws sts get-caller-identity --query Account --output text`
DEFUALT_REGION=`aws configure get region`

echo "This will undo what the deployment script did in $AWS_ACCOUNT_ID $DEFUALT_REGION"
read -p "Press any key to confirm and continue" CONT

aws cloudformation deregister-type --type "RESOURCE" --type-name "MyCompany::ActiveDirectory::User"

aws cloudformation delete-stack --stack-name "LambdaConfigADConnector"

rm -rf .build
