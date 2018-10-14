# AWS Lambda handler implementing Amazon SES domain identity provisioning
# for use as a CloudFormation CustomResource

import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .cfnresponse import FAILED, SUCCESS, send


logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "WARNING"))


DEFAULT_PROPERTIES = {
    "Domain": "",
    "EnableSend": True,
    "EnableReceive": False,
    "MailFromSubdomain": "mail",
    "CustomDMARC": '"v=DMARC1; p=none; pct=100; sp=none; aspf=r;"',
    "TTL": "1800",
    "Region": os.getenv("AWS_REGION"),
}


ses = boto3.client('ses')


def lambda_handler(event, context):
    logger.info("Received event %r", event)

    properties = DEFAULT_PROPERTIES.copy()
    properties.update(event["ResourceProperties"])
    logger.info("Expanded properties to %r", properties)

    # Clean and validate inputs
    try:
        properties["Domain"] = properties["Domain"].strip().rstrip(".")
    except (AttributeError, TypeError):
        pass
    domain = properties["Domain"]

    if not domain:
        return send(event, context, FAILED,
                    reason="The 'Domain' property is required.",
                    physical_resource_id="MISSING")

    if event["RequestType"] == "Delete":
        # Treat Delete as a request to disable both directions
        properties["EnableSend"] = False
        properties["EnableReceive"] = False

    # Update SES
    try:
        outputs = update_ses_domain_identity(domain, properties)
    except (BotoCoreError, ClientError) as error:
        # for ClientError, might be helpful to look at error.response, too
        logger.exception("Error updating SES: %s", error)
        return send(event, context, FAILED,
                    reason=str(error), physical_resource_id=domain)

    # Determine required DNS
    properties.update(outputs)
    route53_records = generate_route53_records(properties)
    outputs.update({
        "Domain": domain,
        "Route53RecordSets": route53_records,
        "ZoneFileEntries": route53_to_zone_file(route53_records),
    })

    return send(event, context, SUCCESS,
                response_data=outputs, physical_resource_id=domain)


def update_ses_domain_identity(domain, properties):
    """Handle SES (de-)provisioning for domain and returns dict of output info"""
    outputs = {}
    enable_send = properties["EnableSend"]
    enable_receive = properties["EnableReceive"]

    if enable_send or enable_receive:
        response = ses.verify_domain_identity(Domain=domain)
        logger.info("SES:VerifyDomainIdentity(Domain=%r) => %r", domain, response)
        outputs["VerificationToken"] = response["VerificationToken"]
    else:
        # Neither send nor receive, so de-provision
        response = ses.delete_identity(Identity=domain)
        logger.info("SES:DeleteIdentity(Identity=%r) => %r", domain, response)

    if enable_send:
        response = ses.verify_domain_dkim(Domain=domain)
        logger.info("SES:VerifyDomainDKIM(Domain=%r) => %r", domain, response)
        # ??? ses.set_identity_dkim_enabled(Identity=domain, DkimEnabled=True)
        outputs["DkimTokens"] = response["DkimTokens"]

    if enable_send and properties["MailFromSubdomain"]:
        mail_from_domain = "{MailFromSubdomain}.{Domain}".format(**properties)
        outputs.update({
            "MailFromDomain": mail_from_domain,
            "MailFromMX": "feedback-smtp.{Region}.amazonses.com".format(**properties),
            "MailFromSPF": '"v=spf1 include:amazonses.com -all"',
        })
    else:
        # Disable custom Mail FROM domain.
        # (Could check first using ses.get_identity_mail_from_domain,
        # but clearing it doesn't cause an error even if not set/applicable.)
        mail_from_domain = ""
    response = ses.set_identity_mail_from_domain(Identity=domain, MailFromDomain=mail_from_domain)
    logger.info("SES:SetIdentityMailFromDomain(Domain=%r, MailFromDomain=%r) => %r",
                domain, mail_from_domain, response)

    if enable_send and properties["CustomDMARC"]:
        outputs["DMARC"] = properties["CustomDMARC"]

    if enable_receive:
        outputs.update({
            "ReceiveMX": "inbound-smtp.{Region}.amazonaws.com".format(**properties),
        })

    return outputs


def generate_route53_records(properties):
    """Return list of AWS::Route53::RecordSet resources required"""
    records = []

    if properties.get("VerificationToken"):
        records.append({
            "Name": "_amazonses.{Domain}.".format(**properties),
            "Type": "TXT",
            "ResourceRecords": ['"{VerificationToken}"'.format(**properties)]})

    if properties.get("DkimTokens"):
        records.extend([{
            "Name": "{token}._domainkey.{Domain}.".format(token=token, **properties),
            "Type": "CNAME",
            "ResourceRecords": ["{token}.dkim.amazonses.com.".format(token=token)],
        } for token in properties["DkimTokens"]])

    if properties.get("MailFromDomain"):
        if properties.get("MailFromMX"):
            records.append({
                "Name": "{MailFromDomain}.".format(**properties),
                "Type": "MX",
                "ResourceRecords": ["10 {MailFromMX}.".format(**properties)]})
        if properties.get("MailFromSPF"):
            records.append({
                "Name": "{MailFromDomain}.".format(**properties),
                "Type": "TXT",
                "ResourceRecords": [properties["MailFromSPF"]]})

    if properties.get("DMARC"):
        records.append({
            "Name": "{Domain}.".format(**properties),
            "Type": "TXT",
            "ResourceRecords": [properties["DMARC"]]})

    if properties.get("ReceiveMX"):
        records.append({
            "Name": "{Domain}.".format(**properties),
            "Type": "MX",
            "ResourceRecords": ["10 {ReceiveMX}.".format(**properties)]})

    for record in records:
        record["TTL"] = properties["TTL"]
    return records


def route53_to_zone_file(records):
    """Return a list of Zone File lines from a list of AWS::Route53::RecordSet"""
    max_name_len = max([len(record["Name"]) for record in records], default=1)
    return [
        "{name:{max_name_len}}\t{ttl}\tIN\t{type:5}\t{data}".format(
            name=record["Name"], max_name_len=max_name_len,
            ttl=record["TTL"], type=record["Type"],
            data=" ".join(record["ResourceRecords"]))
        for record in records]
