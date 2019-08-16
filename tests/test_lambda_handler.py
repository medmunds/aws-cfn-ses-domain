import os
import boto3
from unittest import TestCase
from unittest.mock import patch, ANY as MOCK_ANY
from botocore.stub import Stubber

os.environ["AWS_REGION"] = "mock-region"  # (before loading lambda_function)
from aws_cfn_ses_domain.lambda_function import create_ses_domain

ses = boto3.client('ses')
mock_context = object()

class TestLambdaHandler(TestCase):
    # Use botocore.stub.Stubber to simulate AWS responses

    maxDiff = None

    def setUp(self):
        self.ses_stubber = Stubber(ses)
        self.ses_stubber.activate()
        self.addCleanup(self.ses_stubber.deactivate)
        send_patcher = patch('aws_cfn_ses_domain.lambda_function.send')
        self.mock_send = send_patcher.start()
        self.addCleanup(send_patcher.stop)

    def tearDown(self):
        self.ses_stubber.assert_no_pending_responses()

    def assertLambdaResponse(self, event=MOCK_ANY, context=mock_context, status="SUCCESS", **kwargs):
        """Asserts mock_send was called once, and returns response_data (if any)"""
        if status == "SUCCESS":
            kwargs.setdefault("response_data", MOCK_ANY)
        self.mock_send.assert_called_once_with(event, context, status, **kwargs)
        return self.mock_send.call_args[1].get("response_data", None)

    def test_domain_required(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {}}
        create_ses_domain(ses, event, mock_context)
        self.assertLambdaResponse(
            event, status="FAILED",
            reason="The 'Domain' property is required.",
            physical_resource_id="MISSING")

    def test_non_empty_domain_required(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": " . ",
            }}
        create_ses_domain(ses, event, mock_context)
        self.assertLambdaResponse(
            event, status="FAILED",
            reason="The 'Domain' property is required.",
            physical_resource_id="MISSING")

    def test_create_default(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": "example.com.",
            }}
        self.ses_stubber.add_response(
            'verify_domain_identity',
            {'VerificationToken': "ID_TOKEN"},
            {'Domain': "example.com"})
        self.ses_stubber.add_response(
            'verify_domain_dkim',
            {'DkimTokens': ["DKIM_TOKEN_1", "DKIM_TOKEN_2"]},
            {'Domain': "example.com"})
        self.ses_stubber.add_response(
            'set_identity_mail_from_domain',
            {},
            {'Identity': "example.com", 'MailFromDomain': "mail.example.com"})
        create_ses_domain(ses, event, mock_context)

        outputs = self.assertLambdaResponse(event, physical_resource_id="example.com")
        self.assertEqual(outputs["Domain"], "example.com")
        self.assertEqual(outputs["VerificationToken"], "ID_TOKEN")
        self.assertEqual(outputs["DkimTokens"], ["DKIM_TOKEN_1", "DKIM_TOKEN_2"])
        self.assertEqual(outputs["MailFromDomain"], "mail.example.com")
        self.assertEqual(outputs["MailFromMX"], "feedback-smtp.mock-region.amazonses.com")
        self.assertEqual(outputs["MailFromSPF"], '"v=spf1 include:amazonses.com -all"')
        self.assertEqual(outputs["DMARC"], '"v=DMARC1; p=none; pct=100; sp=none; aspf=r;"')
        self.assertNotIn("ReceiveMX", outputs)
        self.assertCountEqual(outputs["Route53RecordSets"], [
            {'Type': 'TXT', 'Name': '_amazonses.example.com.', 'TTL': '1800',
             'ResourceRecords': ['"ID_TOKEN"']},
            {'Type': 'CNAME', 'Name': 'DKIM_TOKEN_1._domainkey.example.com.', 'TTL': '1800',
             'ResourceRecords': ['DKIM_TOKEN_1.dkim.amazonses.com.']},
            {'Type': 'CNAME', 'Name': 'DKIM_TOKEN_2._domainkey.example.com.', 'TTL': '1800',
             'ResourceRecords': ['DKIM_TOKEN_2.dkim.amazonses.com.']},
            {'Type': 'MX', 'Name': 'mail.example.com.', 'TTL': '1800',
             'ResourceRecords': ['10 feedback-smtp.mock-region.amazonses.com.']},
            {'Type': 'TXT', 'Name': 'mail.example.com.', 'TTL': '1800',
             'ResourceRecords': ['"v=spf1 include:amazonses.com -all"']},
            {'Type': 'TXT', 'Name': '_dmarc.example.com.', 'TTL': '1800',
             'ResourceRecords': ['"v=DMARC1; p=none; pct=100; sp=none; aspf=r;"']},
        ])
        self.assertCountEqual(outputs["ZoneFileEntries"], [
            '_amazonses.example.com.             \t1800\tIN\tTXT  \t"ID_TOKEN"',
            'DKIM_TOKEN_1._domainkey.example.com.\t1800\tIN\tCNAME\tDKIM_TOKEN_1.dkim.amazonses.com.',
            'DKIM_TOKEN_2._domainkey.example.com.\t1800\tIN\tCNAME\tDKIM_TOKEN_2.dkim.amazonses.com.',
            'mail.example.com.                   \t1800\tIN\tMX   \t10 feedback-smtp.mock-region.amazonses.com.',
            'mail.example.com.                   \t1800\tIN\tTXT  \t"v=spf1 include:amazonses.com -all"',
            '_dmarc.example.com.                 \t1800\tIN\tTXT  \t"v=DMARC1; p=none; pct=100; sp=none; aspf=r;"',
        ])

    def test_create_all_options(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": "example.com.",
                "EnableSend": True,
                "EnableReceive": True,
                "MailFromSubdomain": "bounce",
                "CustomDMARC": '"v=DMARC1; p=quarantine; rua=mailto:d@example.com;"',
                "TTL": "300",
                "Region": "us-test-2",
            }}
        self.ses_stubber.add_response(
            'verify_domain_identity',
            {'VerificationToken': "ID_TOKEN"},
            {'Domain': "example.com"})
        self.ses_stubber.add_response(
            'verify_domain_dkim',
            {'DkimTokens': ["DKIM_TOKEN_1", "DKIM_TOKEN_2"]},
            {'Domain': "example.com"})
        self.ses_stubber.add_response(
            'set_identity_mail_from_domain',
            {},
            {'Identity': "example.com", 'MailFromDomain': "bounce.example.com"})
        create_ses_domain(ses, event, mock_context)

        outputs = self.assertLambdaResponse(event, physical_resource_id="example.com")
        self.assertEqual(outputs["Domain"], "example.com")
        self.assertEqual(outputs["VerificationToken"], "ID_TOKEN")
        self.assertEqual(outputs["DkimTokens"], ["DKIM_TOKEN_1", "DKIM_TOKEN_2"])
        self.assertEqual(outputs["MailFromDomain"], "bounce.example.com")
        self.assertEqual(outputs["MailFromMX"], "feedback-smtp.us-test-2.amazonses.com")
        self.assertEqual(outputs["MailFromSPF"], '"v=spf1 include:amazonses.com -all"')
        self.assertEqual(outputs["DMARC"], '"v=DMARC1; p=quarantine; rua=mailto:d@example.com;"')
        self.assertEqual(outputs["ReceiveMX"], "inbound-smtp.us-test-2.amazonaws.com")
        self.assertCountEqual(outputs["Route53RecordSets"], [
            {'Type': 'TXT', 'Name': '_amazonses.example.com.', 'TTL': '300',
             'ResourceRecords': ['"ID_TOKEN"']},
            {'Type': 'CNAME', 'Name': 'DKIM_TOKEN_1._domainkey.example.com.', 'TTL': '300',
             'ResourceRecords': ['DKIM_TOKEN_1.dkim.amazonses.com.']},
            {'Type': 'CNAME', 'Name': 'DKIM_TOKEN_2._domainkey.example.com.', 'TTL': '300',
             'ResourceRecords': ['DKIM_TOKEN_2.dkim.amazonses.com.']},
            {'Type': 'MX', 'Name': 'bounce.example.com.', 'TTL': '300',
             'ResourceRecords': ['10 feedback-smtp.us-test-2.amazonses.com.']},
            {'Type': 'TXT', 'Name': 'bounce.example.com.', 'TTL': '300',
             'ResourceRecords': ['"v=spf1 include:amazonses.com -all"']},
            {'Type': 'TXT', 'Name': '_dmarc.example.com.', 'TTL': '300',
             'ResourceRecords': ['"v=DMARC1; p=quarantine; rua=mailto:d@example.com;"']},
            {'Type': 'MX', 'Name': 'example.com.', 'TTL': '300',
             'ResourceRecords': ['10 inbound-smtp.us-test-2.amazonaws.com.']}
        ])
        self.assertCountEqual(outputs["ZoneFileEntries"], [
            '_amazonses.example.com.             \t300\tIN\tTXT  \t"ID_TOKEN"',
            'DKIM_TOKEN_1._domainkey.example.com.\t300\tIN\tCNAME\tDKIM_TOKEN_1.dkim.amazonses.com.',
            'DKIM_TOKEN_2._domainkey.example.com.\t300\tIN\tCNAME\tDKIM_TOKEN_2.dkim.amazonses.com.',
            'bounce.example.com.                 \t300\tIN\tMX   \t10 feedback-smtp.us-test-2.amazonses.com.',
            'bounce.example.com.                 \t300\tIN\tTXT  \t"v=spf1 include:amazonses.com -all"',
            '_dmarc.example.com.                 \t300\tIN\tTXT  \t"v=DMARC1; p=quarantine; rua=mailto:d@example.com;"',
            'example.com.                        \t300\tIN\tMX   \t10 inbound-smtp.us-test-2.amazonaws.com.',
        ])

    def test_update_receive_only(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": "example.com.",
                "EnableSend": False,
                "EnableReceive": True,
                "CustomDMARC": None,
            }}
        self.ses_stubber.add_response(
            'verify_domain_identity',
            {'VerificationToken': "ID_TOKEN"},
            {'Domain': "example.com"})
        self.ses_stubber.add_response(
            'set_identity_mail_from_domain',
            {},
            {'Identity': "example.com", 'MailFromDomain': ""})
        create_ses_domain(ses, event, mock_context)

        outputs = self.assertLambdaResponse(event, physical_resource_id="example.com")
        self.assertEqual(outputs["Domain"], "example.com")
        self.assertEqual(outputs["VerificationToken"], "ID_TOKEN")
        self.assertNotIn("DkimTokens", outputs)
        self.assertNotIn("MailFromDomain", outputs)
        self.assertNotIn("MailFromMX", outputs)
        self.assertNotIn("MailFromSPF", outputs)
        self.assertNotIn("DMARC", outputs)
        self.assertEqual(outputs["ReceiveMX"], "inbound-smtp.mock-region.amazonaws.com")
        self.assertCountEqual(outputs["Route53RecordSets"], [
            {'Type': 'TXT', 'Name': '_amazonses.example.com.', 'TTL': '1800',
             'ResourceRecords': ['"ID_TOKEN"']},
            {'Type': 'MX', 'Name': 'example.com.', 'TTL': '1800',
             'ResourceRecords': ['10 inbound-smtp.mock-region.amazonaws.com.']}
        ])
        self.assertCountEqual(outputs["ZoneFileEntries"], [
            '_amazonses.example.com.\t1800\tIN\tTXT  \t"ID_TOKEN"',
            'example.com.           \t1800\tIN\tMX   \t10 inbound-smtp.mock-region.amazonaws.com.',
        ])

    def test_delete(self):
        event = {
            "RequestType": "Delete",
            "ResourceProperties": {
                "Domain": "example.com.",
                "EnableSend": True,
                "EnableReceive": True,
            }}
        self.ses_stubber.add_response(
            'delete_identity',
            {},
            {'Identity': "example.com"})
        self.ses_stubber.add_response(
            'set_identity_mail_from_domain',
            {},
            {'Identity': "example.com", 'MailFromDomain': ""})
        create_ses_domain(ses, event, mock_context)

        outputs = self.assertLambdaResponse(event, physical_resource_id="example.com")
        self.assertEqual(outputs["Domain"], "example.com")
        self.assertNotIn("VerificationToken", outputs)
        self.assertNotIn("DkimTokens", outputs)
        self.assertNotIn("MailFromDomain", outputs)
        self.assertNotIn("MailFromMX", outputs)
        self.assertNotIn("MailFromSPF", outputs)
        self.assertNotIn("DMARC", outputs)
        self.assertNotIn("ReceiveMX", outputs)
        self.assertEqual(outputs["Route53RecordSets"], [])
        self.assertEqual(outputs["ZoneFileEntries"], [])

    def test_boto_error(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": "bad domain name",
            }}
        self.ses_stubber.add_client_error(
            'verify_domain_identity',
            "InvalidParameterValue",
            "Invalid domain name bad domain name.",
            expected_params={'Domain': "bad domain name"})
        with self.assertLogs(level="ERROR") as cm:
            create_ses_domain(ses, event, mock_context)
        self.assertLambdaResponse(
            event, status="FAILED",
            reason="An error occurred (InvalidParameterValue) when calling the"
                   " VerifyDomainIdentity operation: Invalid domain name bad domain name.",
            physical_resource_id="bad domain name")

        # Check that the exception got logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn(
            'ERROR:root:Error updating SES: An error occurred (InvalidParameterValue) when'
            ' calling the VerifyDomainIdentity operation: Invalid domain name bad domain name.',
            cm.output[0])
