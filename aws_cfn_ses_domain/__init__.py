from .__about__ import __version__, VERSION
from .ses_domain_identity import handle_domain_identity_request
from .ses_email_identity import handle_email_identity_request
__all__ = [
    'handle_domain_identity_request',
    'handle_email_identity_request',
    '__version__',
    'VERSION',
]
