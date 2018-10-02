# See also:
# - https://medium.com/poka-techblog/verify-domains-for-ses-using-cloudformation-8dd185c9b05c
# - https://github.com/binxio/cfn-ses-provider
import json
import logging
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "WARNING"))


DEFAULT_PROPERTIES = {
    "Domain": None,
    "EnableSend": True,
    "EnableReceive": False,
    "MailFromSubdomain": "mail",
    "DMARC": '"v=DMARC1; p=none; pct=100; sp=none; aspf=r;"',
    "TTL": "1800",
    "Region": os.getenv("AWS_REGION"),
}


ses = boto3.client('ses')


def lambda_handler(event, context):
    logger.info("Received event %r", event)

    properties = DEFAULT_PROPERTIES.copy()
    properties.update(event["ResourceProperties"])
    domain = properties["Domain"]
    logger.info("Expanded properties to %r", properties)

    # Validate inputs
    if not domain:
        send(event, context, FAILED,
             reason="The 'Domain' property is required.",
             physical_resource_id="MISSING")
        return

    try:
        if event["RequestType"] == "Delete":
            handle_delete(domain)
            records = []
        else:
            records = handle_create_or_update(domain, properties)
    except (BotoCoreError, ClientError) as error:
        # for ClientError, might be helpful to look at error.response, too
        logger.exception("Error processing request: %s", error)
        send(event, context, FAILED, reason=str(error), physical_resource_id=domain)
    else:
        outputs = {
            "Route53RecordSets": records,
            "ZoneFileEntries": [record_to_zone_file(record) for record in records],
        }
        send(event, context, SUCCESS, response_data=outputs, physical_resource_id=domain)


def handle_delete(domain):
    """De-provision SES domain identity"""
    ses.delete_identity(Identity=domain)
    logger.info("SES:DeleteIdentity(Identity=%r) succeeded", domain)


def handle_create_or_update(domain, properties):
    """Provision SES domain and return list of AWS::Route53::RecordSet resources required"""
    records = []

    enable_send = properties["EnableSend"]
    enable_receive = properties["EnableReceive"]

    if enable_send or enable_receive:
        token = ses.verify_domain_identity(Domain=domain)["VerificationToken"]
        logger.info("SES:VerifyDomainIdentity(Domain=%r) returned %r", domain, token)
        records.append({
            "Name": "_amazonses.{Domain}.".format(**properties),
            "Type": "TXT",
            "ResourceRecords": ['"{token}"'.format(token=token)]
        })

    if enable_send:
        dkim_tokens = ses.verify_domain_dkim(Domain=domain)['DkimTokens']
        logger.info("SES:VerifyDomainDKIM(Domain=%r) returned %r", domain, dkim_tokens)
        # ??? ses.set_identity_dkim_enabled(Identity=domain, DkimEnabled=True)
        records.extend([{
            "Name": "{token}._domainkey.{Domain}.".format(token=token, **properties),
            "Type": "CNAME",
            "ResourceRecords": ["{token}.dkim.amazonses.com".format(token=token)]
        } for token in dkim_tokens])

        if properties["MailFromSubdomain"]:
            mail_from_domain = "{MailFromSubdomain}.{Domain}".format(**properties)
            mail_from_domain_fq = "{}.".format(mail_from_domain)
            ses.set_identity_mail_from_domain(Identity=domain, MailFromDomain=mail_from_domain)
            logger.info("SES:SetIdentityMailFromDomain(Domain=%r, MailFromDomain=%r) succeeded",
                        domain, mail_from_domain)
            records.extend([{
                "Name": mail_from_domain_fq,
                "Type": "MX",
                "ResourceRecords": [
                    "10 feedback-smtp.{Region}.amazonaws.com.".format(**properties)
                ]
            }, {
                "Name": mail_from_domain_fq,
                "Type": "TXT",
                "ResourceRecords": ['"v=spf1 include:amazonses.com -all"']
            }])

        if properties["DMARC"]:
            records.append({
                "Name": domain,
                "Type": "TXT",
                "ResourceRecords": [properties["DMARC"]]
            })

    if not enable_send or not properties["MailFromSubdomain"]:
        # (could check with ses.get_identity_mail_from_domain first, but no harm in clearing if it's not set)
        ses.set_identity_mail_from_domain(Identity=domain, MailFromDomain="")
        logger.info("SES:SetIdentityMailFromDomain(Domain=%r, MailFromDomain=%r) succeeded", domain, "")

    if enable_receive:
        records.append({
            "Name": domain,
            "Type": "MX",
            "ResourceRecords": [
                "10 inbound-smtp.{Region}.amazonaws.com.".format(**properties)
            ]
        })

    for record in records:
        record["TTL"] = properties["TTL"]

    return records


def record_to_zone_file(record):
    """Return a Zone File line for an AWS::Route53::RecordSet"""
    return "{name}\t{ttl}\tIN\t{type}\t{data}".format(
        name=record["Name"], ttl=record["TTL"], type=record["Type"],
        data=" ".join(record["ResourceRecords"]))


#
# cfnresponse (simplified for Python 3)
# adapted from https://github.com/jorgebastida/cfn-response
#

SUCCESS = "SUCCESS"
FAILED = "FAILED"


def send(event, context, response_status, reason=None, response_data=None, physical_resource_id=None):
    response_body = json.dumps({
        "Status": response_status,
        "Reason": reason or "See the details in CloudWatch Log Stream: {}".format(context.log_stream_name),
        "PhysicalResourceId": physical_resource_id or context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": response_data or {}
    })
    logger.info("Sending response %r", response_body)

    request = Request(event["ResponseURL"], method="PUT",
                      data=response_body.encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    try:
        response = urlopen(request)
        logger.info("Successfully sent response: status=%s reason=%s", response.status, response.reason)
    except HTTPError as exc:
        logger.exception("Error sending response: code=%s", exc.code)
