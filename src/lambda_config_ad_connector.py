"""
A simple Lambda that pools user configuration from AD using LDAP
and update resource configuration in AWS Config
"""

# Import modules
import boto3
import os
import ssl
import json
from ldap3 import Server, Connection, Tls, NTLM, ALL_ATTRIBUTES, ALL_OPERATIONAL_ATTRIBUTES

# Main function
def ad_sync():
    print('-- Starting function --')

    # Setting variables from
    ldap_endpoint = os.environ['LDAP_FQDN']
    domain_name = os.environ['AD_DOMAIN_NAME']
    ad_binder_sm_arn = os.environ['AD_BIND_USER_SM_ARN']
    domain_base = os.environ['AD_DOMAIN_BASE']
    server_port = int(os.environ['LDAP_PORT'])
    secure_port_conf = os.environ['LDAP_SECURE'].lower()
    resource_type = os.environ['RESOURCE_TYPE']
    use_ssl = secure_port_conf == 'true'

    # Getting default resource type
    cfn = boto3.client('cloudformation')
    resp = cfn.describe_type(
        Type='RESOURCE',
        TypeName=resource_type
    )
    schema_version_id = resp['DefaultVersionId']

    # Retriving credentials from Secrets Manager
    secretsmanager = boto3.client('secretsmanager')
    resp = secretsmanager.get_secret_value(SecretId=ad_binder_sm_arn)
    user_credentials = json.loads(resp['SecretString'])
    caller_username = user_credentials['bindusername']
    caller_password = user_credentials['bindpassword']

    tls_config = Tls(validate=ssl.CERT_NONE)
    server = Server(ldap_endpoint, port=server_port, use_ssl=use_ssl, tls=tls_config)
    connection = Connection(server, user=f"{domain_name}\\{caller_username}",
                            password=caller_password, authentication=NTLM, auto_bind=True, auto_referrals=False)

    connection.search(search_base=domain_base, search_filter=f"(objectclass=person)",
                attributes=[ALL_ATTRIBUTES, ALL_OPERATIONAL_ATTRIBUTES])

    results = connection.entries
    config = boto3.client('config')
    user_names_set = set()
    row_format = "{:>20}" * 4
    print("")
    print("Sync user information from AD to Config ... ")
    print(row_format.format(*['SAMAccountName', 'Name', 'userAccountControl', 'PwdLastSet']))
    for entry in results:
        user_id = str(entry.sAMAccountName)
        user_name = str(entry.name)
        user_names_set.add(user_id)
        passwd_last_set = str(entry.pwdLastSet)
        control_code = str(entry.userAccountControl)
        print(row_format.format(*[user_id, user_name, control_code, passwd_last_set[:10]]))

        # Filling the information to Schema
        user_configuration = {
          "SAMAccountName": user_id,
          "Name": user_name,
          "PwdLastSet": passwd_last_set,
          "userAccountControl": control_code
        }

        # Updating the custom resource in to AWS Config
        config.put_resource_config(
            ResourceType=resource_type,
            SchemaVersionId=schema_version_id,
            ResourceId=user_id,
            Configuration=json.dumps(user_configuration),
        )

    # Compare the current list of resources in Config with the user list from AD
    # Call delete_resource_config on the users that no longer exist
    print("")
    print("Removing deleted users from Config")
    previous_users = []
    paginator = config.get_paginator(operation_name='list_discovered_resources')
    for page in paginator.paginate(resourceType=resource_type):
        previous_users += [i['resourceId'] for i in page['resourceIdentifiers']]
    resource_to_delete = [n for n in previous_users if n not in user_names_set]
    print(f"Users to remove from Config: {resource_to_delete}")
    for resource_id in resource_to_delete:
        config.delete_resource_config(ResourceType=resource_type, ResourceId=resource_id)

    print("")
    print("Finished")

# Lambda handler
def lambda_handler(event, context):
    ad_sync()

# Method for local test
if __name__ == '__main__':
    ad_sync()