import os

from .base import HandlerTestCase, MOCK_ANY

os.environ["AWS_REGION"] = "mock-region"  # (before importing handler)
from aws_cfn_ses_domain.ses_domain_identity import handle_domain_identity_request


class TestDomainIdentityHandler(HandlerTestCase):

    patch_base = 'aws_cfn_ses_domain.ses_domain_identity'

    def test_domain_required(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {},
            "StackId": self.mock_stack_id}
        handle_domain_identity_request(event, self.mock_context)
        self.assertSentResponse(
            event, status="FAILED",
            reason="The 'Domain' property is required.",
            physical_resource_id="MISSING")

    def test_non_empty_domain_required(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": " . ",
            },
            "StackId": self.mock_stack_id}
        handle_domain_identity_request(event, self.mock_context)
        self.assertSentResponse(
            event, status="FAILED",
            reason="The 'Domain' property is required.",
            physical_resource_id="MISSING")

    def test_create_default(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": "example.com.",
            },
            "StackId": self.mock_stack_id}
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
        handle_domain_identity_request(event, self.mock_context)

        # Should default to SES in current region (where stack is running):
        self.mock_boto3_client.assert_called_once_with('ses', region_name="mock-region")

        outputs = self.assertSentResponse(
            event, physical_resource_id="arn:aws:ses:mock-region:111111111111:identity/example.com")
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
        self.assertEqual(outputs["Region"], "mock-region")
        self.assertEqual(outputs["Arn"], "arn:aws:ses:mock-region:111111111111:identity/example.com")

    def test_create_all_options(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": "example.com.",
                "EnableSend": "true",
                "EnableReceive": "true",
                "MailFromSubdomain": "bounce",
                "CustomDMARC": '"v=DMARC1; p=quarantine; rua=mailto:d@example.com;"',
                "TTL": "300",
                "Region": "us-test-2",
            },
            "StackId": self.mock_stack_id}
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
        handle_domain_identity_request(event, self.mock_context)

        # Should override SES region when Region property provided:
        self.mock_boto3_client.assert_called_once_with('ses', region_name="us-test-2")

        outputs = self.assertSentResponse(
            event, physical_resource_id="arn:aws:ses:us-test-2:111111111111:identity/example.com")
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
        self.assertEqual(outputs["Region"], "us-test-2")
        self.assertEqual(outputs["Arn"], "arn:aws:ses:us-test-2:111111111111:identity/example.com")

    def test_update_receive_only(self):
        event = {
            "RequestType": "Update",
            "ResourceProperties": {
                "Domain": "example.com.",
                "EnableSend": "false",
                "EnableReceive": "true",
                "CustomDMARC": None,
            },
            "StackId": self.mock_stack_id}
        self.ses_stubber.add_response(
            'verify_domain_identity',
            {'VerificationToken': "ID_TOKEN"},
            {'Domain': "example.com"})
        self.ses_stubber.add_response(
            'set_identity_mail_from_domain',
            {},
            {'Identity': "example.com", 'MailFromDomain': ""})
        handle_domain_identity_request(event, self.mock_context)

        outputs = self.assertSentResponse(
            event, physical_resource_id="arn:aws:ses:mock-region:111111111111:identity/example.com")
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
            "PhysicalResourceId": "arn:aws:ses:mock-region:111111111111:identity/example.com",
            "ResourceProperties": {
                "Domain": "example.com.",
                "EnableSend": "true",
                "EnableReceive": "true",
            },
            "StackId": self.mock_stack_id}
        self.ses_stubber.add_response(
            'delete_identity',
            {},
            {'Identity': "example.com"})
        self.ses_stubber.add_response(
            'set_identity_mail_from_domain',
            {},
            {'Identity': "example.com", 'MailFromDomain': ""})
        handle_domain_identity_request(event, self.mock_context)

        outputs = self.assertSentResponse(
            event, physical_resource_id="arn:aws:ses:mock-region:111111111111:identity/example.com")
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

    def test_v0_3_physical_id_change(self):
        # Prior to v0.3, the PhysicalResourceId was just the cleaned Domain.
        # Make sure we ignore the Delete operation that CF will issue on the
        # old physical ID after upgrading.
        event = {
            "RequestType": "Delete",
            "PhysicalResourceId": "example.com",  # old format: just the domain
            "ResourceProperties": {
                "Domain": "example.com.",
                "EnableSend": "true",
                "EnableReceive": "true",
            },
            "StackId": self.mock_stack_id}
        # self.ses_stubber.nothing: *no* SES ops should occur
        handle_domain_identity_request(event, self.mock_context)

        outputs = self.assertSentResponse(event, physical_resource_id="example.com")
        self.assertEqual(outputs["Domain"], "example.com")

    def test_boto_error(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": "bad domain name",
            },
            "StackId": self.mock_stack_id}
        self.ses_stubber.add_client_error(
            'verify_domain_identity',
            "InvalidParameterValue",
            "Invalid domain name bad domain name.",
            expected_params={'Domain': "bad domain name"})
        with self.assertLogs(level="ERROR") as cm:
            handle_domain_identity_request(event, self.mock_context)
        self.assertSentResponse(
            event, status="FAILED",
            reason="An error occurred (InvalidParameterValue) when calling the"
                   " VerifyDomainIdentity operation: Invalid domain name bad domain name.",
            physical_resource_id=MOCK_ANY)

        # Check that the exception got logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn(
            'ERROR:root:Error updating SES: An error occurred (InvalidParameterValue) when'
            ' calling the VerifyDomainIdentity operation: Invalid domain name bad domain name.',
            cm.output[0])

    def test_invalid_boolean_property(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "Domain": "example.com",
                "EnableSend": "yes",
            },
            "StackId": self.mock_stack_id}
        handle_domain_identity_request(event, self.mock_context)
        self.assertSentResponse(
            event, status="FAILED",
            reason="The 'EnableSend' property must be 'true' or 'false', not 'yes'.",
            physical_resource_id=MOCK_ANY)
