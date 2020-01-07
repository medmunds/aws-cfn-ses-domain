# Amazon SES email identity provisioning

import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .cfnresponse import FAILED, SUCCESS, send
from .utils import format_arn


logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "WARNING"))


DEFAULT_PROPERTIES = {
    "EmailAddress": "",
    "Region": os.getenv("AWS_REGION"),
}


def handle_email_identity_request(event, context):
    logger.info("Received event %r", event)

    properties = DEFAULT_PROPERTIES.copy()
    properties.update(event["ResourceProperties"])
    logger.info("Expanded properties to %r", properties)

    # Clean and validate inputs
    try:
        properties["EmailAddress"] = properties["EmailAddress"].strip()
    except (AttributeError, TypeError):
        pass
    email_address = properties["EmailAddress"]

    if not email_address:
        return send(event, context, FAILED,
                    reason="The 'EmailAddress' property is required.",
                    physical_resource_id="MISSING")

    ses = boto3.client("ses", region_name=properties["Region"])

    # Use an SES Identity ARN as the PhysicalResourceId - see:
    # https://docs.aws.amazon.com/IAM/latest/UserGuide/list_amazonses.html#amazonses-resources-for-iam-policies
    email_arn = format_arn(
        service="ses", region=properties["Region"],
        resource_type="identity", resource_name=email_address,
        defaults_from=event["StackId"])  # current stack's ARN has account and partition

    try:
        if event["RequestType"] == "Delete":
            response = ses.delete_identity(Identity=email_address)
            logger.info("SES:DeleteIdentity(Identity=%r) => %r", email_address, response)
        else:
            # Both Create and Update validate the new EmailAddress.
            # (For Update, the change in physical_resource_id will cause CloudFormation
            # to issue a Delete on the old EmailAddress after this request succeeds.)
            response = ses.verify_email_identity(EmailAddress=email_address)
            logger.info("SES:VerifyEmailIdentity(EmailAddress=%r) => %r", email_address, response)
    except (BotoCoreError, ClientError) as error:
        # for ClientError, might be helpful to look at error.response, too
        logger.exception("Error updating SES: %s", error)
        return send(event, context, FAILED,
                    reason=str(error), physical_resource_id=email_arn)

    outputs = {
        "Arn": email_arn,
        "EmailAddress": email_address,
        "Region": properties["Region"],
    }
    return send(event, context, SUCCESS,
                response_data=outputs, physical_resource_id=email_arn)
