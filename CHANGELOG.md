# Changelog

## v0.4

*2022-05-13*

### Fixes

* Update AWS Lambda runtime to python3.9 (from deprecated python3.6).


## v0.3

*2020-01-07*

### Breaking changes

* The physical resource ID of a `Custom::SES_Domain` resource is now the full ARN 
  of the Amazon SES domain identity. (Previously it was just the domain name.)
  If you have templates that use `!Ref MySESDomain` to get the domain, change them 
  to `!GetAtt MySESDomain.Domain` instead.

* Because of the physical resource ID change, the first stack update after upgrading
  to v0.3 will appear to update and then delete existing `Custom::SES_Domain` resources.
  Don't be alarmed: your SES domain *isn't* actually deleted. (The delete operation 
  covers the old physical resource ID, and will be ignored.)

### Fixes

* Support using the [`Region`](README.md#region) property to provision an Amazon SES 
  domain in a different region from where you're running your CloudFormation stack.
  (Thanks to @gfodor.)
  
* Fix incorrect handling of `EnableSend: false` and other potential problems with
  Boolean properties, by working around CloudFormation's non-standard YAML parsing. 
  (Thanks to @aajtodd.)


### Features

* Add a new [`Custom::SES_EmailIdentity`](README.md#customses_emailidentity) custom
  resource type for managing Amazon SES verified email addresses.

* Make [`Arn`](README.md#other-attributes) and [`Region`](README.md#other-attributes)
  attributes available on `Custom::SES_Domain` resources.

### Deprecations

* The `ServiceToken` used for a `Custom::SES_Domain` has changed from the nested stack's
  `...Outputs.Arn` to `...Outputs.CustomDomainIdentityArn` (to distinguish it from the 
  new `...Outputs.CustomEmailIdentityArn` for `Custom::SES_EmailIdentity` resources).
  If your templates use something like `ServiceToken: !GetAtt CfnSESDomain.Outputs.Arn`, 
  they will continue to work with v0.3, but you should replace `Arn` to prepare for
  future releases: `ServiceToken: !GetAtt CfnSESDomain.Outputs.CustomDomainIdentityArn`.


## v0.2

*2019-04-23*

### Fixes

* Use correct subdomain for DMARC record

### Features

* Add cfn-lint spec file (cfn-lint 0.9.0 supports custom override specs)

### Internal

* Fix release-pypi dist commands in makefile
* Fix example-usage template defaults


## v0.1

*2018-11-02*

Initial release

