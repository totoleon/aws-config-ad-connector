from aws_cdk import (
    aws_events as events,
    aws_lambda as lambda_,
    aws_events_targets as targets,
    aws_s3 as s3,
    aws_iam as iam,
    aws_config as config,
    core,
)
import os
dirname = os.path.dirname(__file__)

lambda_layer_file_name = 'lambda_layer_packages.zip'
lambda_code_file_name = 'lambda_code.zip'
connector_function_name = 'lambda_config_ad_connector'
config_rule_function_name = 'lambda_config_rule_passwd_expire'

lambda_envs = ['AD_DOMAIN_NAME', 'AD_DOMAIN_BASE', 'LDAP_FQDN', 'LDAP_SECURE', 'LDAP_PORT', 'AD_BIND_USER_SM_ARN', 'RESOURCE_TYPE']
lambda_env_map = {key: os.environ[key] for key in lambda_envs}
secret_manager_arn = lambda_env_map['AD_BIND_USER_SM_ARN']

class LambdaConfigADConnector(core.Stack):
    def __init__(self, app: core.App, id: str) -> None:
        super().__init__(app, id)

        # IAM permissions for the Lambda functions
        configCustomResourcePermission = iam.PolicyStatement(
            actions=['config:ListDiscoveredResources',
                     'config:DeleteResourceConfig',
                     'config:PutResourceConfig',
                     'cloudformation:DescribeType'],
            resources=['*']
        )
        configRuleLambdaPermission = iam.PolicyStatement(
            actions=['config:PutEvaluations'],
            resources=['*']
        )
        secretManagerPermission = iam.PolicyStatement(
            actions=['secretsmanager:GetSecretValue'],
            resources=[secret_manager_arn]
        )

        # Lambda Layer
        lambdaLayer = lambda_.LayerVersion(
            self, "ConfigADConnectorLayer",
            code=lambda_.Code.from_asset(os.path.join(dirname, f'../.build/{lambda_layer_file_name}')),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_6]
        )

        # Lambda function and periodic trigger for Config - AD connector
        configAdLambdaFn = lambda_.Function(
            self, "ConfigADConnector",
            code=lambda_.Code.from_asset(os.path.join(dirname, f'../.build/{lambda_code_file_name}')),
            handler=f"{connector_function_name}.lambda_handler",
            timeout=core.Duration.seconds(300),
            runtime=lambda_.Runtime.PYTHON_3_6,
            layers=[lambdaLayer],
            initial_policy=[configCustomResourcePermission, secretManagerPermission],
            environment=lambda_env_map
        )
        rule = events.Rule(
            self, "Rule",
            schedule=events.Schedule.rate(
                duration=core.Duration.minutes(1)
            )
        )
        rule.add_target(targets.LambdaFunction(configAdLambdaFn))

        # Custom Config Rule with a Lambda function for AD user evaluation
        ruleEvaluationLambdaFn = lambda_.Function(
            self, "ADUserPasswdExpiresCheck",
            code=lambda_.Code.from_asset(os.path.join(dirname, f'../.build/{lambda_code_file_name}')),
            handler=f"{config_rule_function_name}.lambda_handler",
            timeout=core.Duration.seconds(300),
            runtime=lambda_.Runtime.PYTHON_3_6,
            layers=[lambdaLayer],
            initial_policy=[configRuleLambdaPermission],
            environment=lambda_env_map
        )
        configRule = config.CustomRule(
            self, "ADUserPasswdExpires",
            lambda_function=ruleEvaluationLambdaFn,
            configuration_changes=True
        )
        configRule.scope_to_resources(os.environ['RESOURCE_TYPE'])

app = core.App()
LambdaConfigADConnector(app, "LambdaConfigADConnector")
app.synth()
