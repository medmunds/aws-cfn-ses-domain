import os
from unittest import TestCase
from unittest.mock import patch, ANY as MOCK_ANY

import boto3
from botocore.stub import Stubber


# Mock the AWS Lambda Runtime environment
# (to the extent helpful for mock tests locally).
os.environ["AWS_REGION"] = "mock-region"  # (before importing handler)


class HandlerTestCase(TestCase):
    """Common test code for Amazon SES custom resource handlers.

    Mocks boto3.client('ses') and cfnresponse.send, and
    uses botocore.stub.Stubber to simulate/validate AWS responses.
    """

    maxDiff = None  # full diffs are helpful for Stubber assertions

    # HandlerTestCase will patch boto3.client and cfnresponse.send within this module:
    patch_base = 'aws_cfn_ses_domain.<handler_module>'  # concrete tests must override

    def setUp(self):
        self.mock_context = object()
        self.mock_stack_id = "arn:aws:cloudformation:mock-region:111111111111:stack/example/deadbeef"

        if self.patch_base == HandlerTestCase.patch_base:
            raise NotImplementedError(f"{self.__class__.__name__} must override patch_base")

        ses = boto3.client('ses')  # need a real client for Stubber
        boto3_client_patcher = patch(f'{self.patch_base}.boto3.client', return_value=ses)
        self.mock_boto3_client = boto3_client_patcher.start()
        self.addCleanup(boto3_client_patcher.stop)

        self.ses_stubber = Stubber(ses)
        self.ses_stubber.activate()
        self.addCleanup(self.ses_stubber.deactivate)

        send_patcher = patch(f'{self.patch_base}.send')
        self.mock_send = send_patcher.start()
        self.addCleanup(send_patcher.stop)

    def tearDown(self):
        self.ses_stubber.assert_no_pending_responses()

    def assertSentResponse(self, event=MOCK_ANY, context=None, status="SUCCESS", **kwargs):
        """Asserts cfnresponse.send was called once, and returns response_data (if any)"""
        if context is None:
            context = self.mock_context
        if status == "SUCCESS":
            kwargs.setdefault("response_data", MOCK_ANY)
        self.mock_send.assert_called_once_with(event, context, status, **kwargs)
        return self.mock_send.call_args[1].get("response_data", None)
