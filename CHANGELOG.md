# Changelog

## v0.3.dev0

*Unreleased changes*

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

