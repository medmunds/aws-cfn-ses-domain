def format_arn(partition=None, service=None, region=None, account=None,
               resource=None, resource_type=None, resource_name=None,
               defaults_from=None):
    """Return an ARN composed from the specified components.

    Provide either resource or both resource_type and resource_name.

    defaults_from can be an existing ARN, which will be used to fill in any
    missing components.

    See https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html
    for the format.
    """
    if resource is None and resource_type is not None:
        resource = f"{resource_type}/{resource_name}"
    if defaults_from is not None:
        try:
            _arn, _partition, _service, _region, _account, _resource = defaults_from.split(":")
        except (TypeError, ValueError):
            raise ValueError(f"Invalid ARN in defaults_from={defaults_from!r}")
        partition = partition if partition is not None else _partition
        service = service if service is not None else _service
        region = region if region is not None else _region
        account = account if account is not None else _account
        resource = resource if resource is not None else _resource

    return f"arn:{partition}:{service}:{region}:{account}:{resource}"


def to_bool(val):
    """Convert val to True or False.

    Converts 'true' (case-insensitive) and 1, '1', or True to True.
    Converts 'false', 'null' or 'none' (case-insensitive), the empty string '',
    and 0, '0', or False to False.
    Raises a ValueError for any other input.

    >>> to_bool('true')
    True
    >>> to_bool('False')
    False
    >>> to_bool(0)
    False
    >>> to_bool('0')
    False
    >>> to_bool(None)
    False
    >>> to_bool('yes')
    ValueError("Invalid boolean value 'yes'")
    """
    # (Loosely adapted from distutils.util.strtobool)
    strval = str(val).lower()
    if strval in ('true', '1'):
        return True
    elif strval in ('false', '0', 'null', 'none', ''):
        return False
    else:
        raise ValueError(f"Invalid boolean value {val!r}")
