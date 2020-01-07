import os

from .base import HandlerTestCase, MOCK_ANY

os.environ["AWS_REGION"] = "mock-region"  # (before importing handler)
from aws_cfn_ses_domain.ses_email_identity import handle_email_identity_request


class TestEmailIdentityHandler(HandlerTestCase):

    patch_base = 'aws_cfn_ses_domain.ses_email_identity'

    def test_email_required(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {},
            "StackId": self.mock_stack_id}
        handle_email_identity_request(event, self.mock_context)
        self.assertSentResponse(
            event, status="FAILED",
            reason="The 'EmailAddress' property is required.",
            physical_resource_id="MISSING")

    def test_non_empty_email_required(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "EmailAddress": " \t ",
            },
            "StackId": self.mock_stack_id}
        handle_email_identity_request(event, self.mock_context)
        self.assertSentResponse(
            event, status="FAILED",
            reason="The 'EmailAddress' property is required.",
            physical_resource_id="MISSING")

    def test_create_default(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "EmailAddress": "sender@example.com",
            },
            "StackId": self.mock_stack_id}
        self.ses_stubber.add_response(
            'verify_email_identity',
            {},
            {'EmailAddress': "sender@example.com"})
        handle_email_identity_request(event, self.mock_context)

        # Should default to SES in current region (where stack is running):
        self.mock_boto3_client.assert_called_once_with('ses', region_name="mock-region")

        outputs = self.assertSentResponse(
            event, physical_resource_id="arn:aws:ses:mock-region:111111111111:identity/sender@example.com")
        self.assertEqual(outputs["EmailAddress"], "sender@example.com")
        self.assertEqual(outputs["Region"], "mock-region")
        self.assertEqual(outputs["Arn"], "arn:aws:ses:mock-region:111111111111:identity/sender@example.com")

    def test_create_all_options(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "EmailAddress": "  sender@example.com  ",
                "Region": "us-test-2",
            },
            "StackId": self.mock_stack_id}
        self.ses_stubber.add_response(
            'verify_email_identity',
            {},
            {'EmailAddress': "sender@example.com"})
        handle_email_identity_request(event, self.mock_context)

        # Should override SES region when Region property provided:
        self.mock_boto3_client.assert_called_once_with('ses', region_name="us-test-2")

        outputs = self.assertSentResponse(
            event, physical_resource_id="arn:aws:ses:us-test-2:111111111111:identity/sender@example.com")
        self.assertEqual(outputs["Region"], "us-test-2")
        self.assertEqual(outputs["Arn"], "arn:aws:ses:us-test-2:111111111111:identity/sender@example.com")

    def test_update(self):
        # Update is essentially the same as Create on the new address.
        # CloudFormation will automatically Delete the old one once the resource id changes.
        event = {
            "RequestType": "Update",
            "PhysicalResourceId": "arn:aws:ses:mock-region:111111111111:identity/sender@example.com",
            "ResourceProperties": {
                "EmailAddress": "other@example.org",
            },
            "StackId": self.mock_stack_id}
        self.ses_stubber.add_response(
            'verify_email_identity',
            {},
            {'EmailAddress': "other@example.org"})
        handle_email_identity_request(event, self.mock_context)

        outputs = self.assertSentResponse(
            event, physical_resource_id="arn:aws:ses:mock-region:111111111111:identity/other@example.org")
        self.assertEqual(outputs["Region"], "mock-region")
        self.assertEqual(outputs["Arn"], "arn:aws:ses:mock-region:111111111111:identity/other@example.org")

    def test_delete(self):
        event = {
            "RequestType": "Delete",
            "PhysicalResourceId": "arn:aws:ses:mock-region:111111111111:identity/sender@example.com",
            "ResourceProperties": {
                "EmailAddress": "sender@example.com",
            },
            "StackId": self.mock_stack_id}
        self.ses_stubber.add_response(
            'delete_identity',
            {},
            {'Identity': "sender@example.com"})
        handle_email_identity_request(event, self.mock_context)

        outputs = self.assertSentResponse(
            event, physical_resource_id="arn:aws:ses:mock-region:111111111111:identity/sender@example.com")
        self.assertEqual(outputs["Region"], "mock-region")
        self.assertEqual(outputs["Arn"], "arn:aws:ses:mock-region:111111111111:identity/sender@example.com")

    def test_boto_error(self):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "EmailAddress": "bad email",
            },
            "StackId": self.mock_stack_id}
        self.ses_stubber.add_client_error(
            'verify_email_identity',
            "InvalidParameterValue",
            "Invalid email address bad email.",
            expected_params={'EmailAddress': "bad email"})
        with self.assertLogs(level="ERROR") as cm:
            handle_email_identity_request(event, self.mock_context)
        self.assertSentResponse(
            event, status="FAILED",
            reason="An error occurred (InvalidParameterValue) when calling the"
                   " VerifyEmailIdentity operation: Invalid email address bad email.",
            physical_resource_id=MOCK_ANY)

        # Check that the exception got logged
        self.assertEqual(len(cm.output), 1)
        self.assertIn(
            'ERROR:root:Error updating SES: An error occurred (InvalidParameterValue) when'
            ' calling the VerifyEmailIdentity operation: Invalid email address bad email.',
            cm.output[0])
