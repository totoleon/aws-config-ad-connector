"""
Evaluation on AD users
"""

import json
import boto3


def evaluate_compliance(configuration_item):
    if configuration_item["configurationItemStatus"] == "ResourceDeleted":
        return {
            "compliance_type": "NOT_APPLICABLE",
            "annotation": "The configurationItem was deleted and therefore cannot be validated."
        }

    configuration = configuration_item.get('configuration')
    userAccountControl = int(configuration.get('userAccountControl'))

    # Checking AD control flag based on UserAccountControl
    # https://support.microsoft.com/en-us/help/305144/how-to-use-useraccountcontrol-to-manipulate-user-account-properties
    if str.format('0x{:08x}', userAccountControl)[-5] == '1':
        return {
            "compliance_type": "NON_COMPLIANT",
            "annotation": "Password Never Expire is enabled"
        }
    else:
        return {
            "compliance_type": "COMPLIANT",
            "annotation": "No Password Never Expire"
        }


def lambda_handler(event, context):
    print("Starting evaluation ...")
    print(event)
    invoking_event = json.loads(event['invokingEvent'])
    configuration_item = invoking_event["configurationItem"]
    evaluation = evaluate_compliance(configuration_item)
    config = boto3.client('config')
    config.put_evaluations(
        Evaluations=[
            {
                'ComplianceResourceType': invoking_event['configurationItem']['resourceType'],
                'ComplianceResourceId': invoking_event['configurationItem']['resourceId'],
                'ComplianceType': evaluation["compliance_type"],
                "Annotation": evaluation["annotation"],
                'OrderingTimestamp': invoking_event['configurationItem']['configurationItemCaptureTime']
            },
        ],
        ResultToken=event['resultToken'])
