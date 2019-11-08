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
