# cfnresponse (simplified for Python 3)
# adapted from https://github.com/jorgebastida/cfn-response
import json
import logging
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger()


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
                      headers={"Content-Type": ""})  # "application/json" will cause 403
    try:
        response = urlopen(request)
    except HTTPError as exc:
        logger.exception("Error sending response: code=%s", exc.code)
        return False
    else:
        logger.info("Successfully sent response: status=%s reason=%s", response.status, response.reason)
        return True
