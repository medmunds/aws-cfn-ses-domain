# AWS CloudFormation SES Domain Custom Resource

AWS [CloudFormation][] provides several built-in Amazon SES resource types,
but oddly omits any way to manage SES domain identities. This package implements
a `Custom::SES_Domain` CloudFormation [custom resource][custom-resource] that
offers that missing functionality. 

You can use it to provision a domain for sending and/or receiving email through SES.
The `Custom::SES_Domain` resource handles all required Amazon SES identity management 
calls and outputs SES's required DNS entries. 

The `Custom::SES_Domain` resource deliberately avoids manipulating Route 53 itself. 
Instead, it returns an attribute that helps your template use a standard
[`AWS::Route53::RecordSetGroup`][RecordSetGroup] resource for those DNS entries. 
Or if you prefer, you can use other `Custom::SES_Domain` return values to customize 
DNS records for Route 53, or to use some other DNS provider entirely.

As an added benefit, this approach lets CloudFormation determine the optimal DNS 
updating strategy if you change your stack (e.g., to add inbound capability to an 
SES domain originally provisioned for sending only).

**Documentation**

* [Installation](#installation)
* [Usage](#usage)
  * [Properties](#properties)
  * [Return Values](#return-values)
  * [Validating Your Templates](#validating-your-templates)
* [Development](#development)
* [Alternatives](#alternatives)
* [Future](#future)


## Installation

The `Custom::SES_Domain` resource is implemented as an AWS Lambda Function. To use it
from your CloudFormation templates, you'll need to set up that function along with an 
IAM role giving it permission to manage your Amazon SES domains.

The easiest way to do this is with a CloudFormation [nested stack][NestedStack]: 

1. Copy the `aws-cfn-ses-domain-VERSION.lambda.zip` Lambda package and 
   `aws-cfn-ses-domain-VERSION.cf.yaml` CloudFormation template from this repository's 
   [releases][] page into an S3 bucket in the region where you'll be running your
   CloudFormation stack. This bucket needs to be readable from CloudFormation, but
   need not be public. 
   
2. Then in your CloudFormation template, use a nested stack to create the Lambda 
   Function and IAM role for the `Custom::SES_Domain` type:

```yaml
  CfnSESDomain:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: https://s3.amazonaws.com/YOUR_BUCKET/aws-cfn-ses-domain-VERSION.cf.yaml
      Parameters:
        LambdaCodeS3Bucket: YOUR_BUCKET
        LambdaCodeS3Key: aws-cfn-ses-domain-VERSION.lambda.zip
```

The `Custom::SES_Domain` resource type is now available to use like this (see 
[Usage](#usage) below for the full list of properties and return values):

```yaml
  MySESDomain:
    Type: Custom::SES_Domain
    Properties:
      # ServiceToken must be the Arn of the Lambda Function:
      ServiceToken: !GetAtt CfnSESDomain.Outputs.Arn
      Domain: "example.com"
      # ...
```

If you'd prefer to build and upload the `Custom::SES_Domain` code from source, 
see the [Development](#development) section.



## Usage

To work with a `Custom::SES_Domain` resource in your CloudFormation template, you'll
typically:

1. Define the AWS Lambda Function that implements the `Custom::SES_Domain` CloudFormation 
   custom resource type, as shown in [Installation](#installation) above.

2. Declare a `Custom::SES_Domain` resource for your Amazon SES domain, specifying 
   whatever SES options you need.

3. Declare an [`AWS::Route53::RecordSetGroup`][RecordSetGroup] resource to manage SES's 
   required DNS entries, passing it the [`Route53RecordSets`](#route53recordsets) 
   attribute of your `Custom::SES_Domain`. (Or if you're not using Route 53, use the 
   other `Custom::SES_Domain` [return values](#return-values) to create the appropriate 
   records with your DNS provider.)

Here's how that looks in a cloudformation.yaml template…

```yaml
Resources:
  # 1. Define the Custom::SES_Domain's Lambda Function via a nested stack. 
  CfnSESDomain:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: https://s3.amazonaws.com/YOUR_BUCKET/aws-cfn-ses-domain-VERSION.cf.yaml
      Parameters:
        LambdaCodeS3Bucket: YOUR_BUCKET
        LambdaCodeS3Key: aws-cfn-ses-domain-VERSION.lambda.zip

  # 2. Declare a Custom::SES_Domain resource for your SES domain.
  MySESDomain:
    Type: Custom::SES_Domain
    Properties:
      # ServiceToken is the Arn of the Lambda Function defined above:
      ServiceToken: !GetAtt CfnSESDomain.Outputs.Arn
      # Remaining Properties are options for provisioning for your SES domain identity:
      # (Domain is required; all others are optional and shown with their defaults)
      Domain: "example.com"
      EnableSend: true
      EnableReceive: false
      MailFromSubdomain: "mail"
      TTL: "1800"
      CustomDMARC: '"v=DMARC1; p=none; pct=100; sp=none; aspf=r;"'
      Region: !Ref "AWS::Region"

  # 3. Declare a Route 53 RecordSetGroup to manage SES's required DNS entries.
  #    (This assumes you already have a Route 53 hosted zone for your domain;
  #    if not, you'll also want an AWS::Route53::HostedZone resource for it.
  #    Or if you don't use Route 53, see "Return Values" for other DNS options.)
  MyRoute53RecordsForSES:
    Type: AWS::Route53::RecordSetGroup
    Properties:
      HostedZoneName: "example.com."
      # The Route53RecordSets attribute specifies all DNS records needed:
      RecordSets: !GetAtt MySESDomain.Route53RecordSets
```

### Properties

A `Custom::SES_Domain` resource supports the following Properties:

##### `ServiceToken`

The ARN of the Lambda Function that implements the `Custom::SES_Domain` type.
See [Installation](#installation) above for a simple way to obtain this.
(This is a standard property of all CloudFormation 
[AWS::CloudFormation::CustomResource][CustomResource] types.)

*Required:* Yes

*Type:* String

*Update requires:* Updates are not supported


##### `Domain` 

The domain name you want to provision for sending and/or receiving email via Amazon SES,
such as `example.com`. (A trailing period is not required, but is allowed to simplify 
working with Route 53 HostedZone names that do require it.)

For more information, see [Verifying Domains in Amazon SES][verifying-ses-domains] 
in the *Amazon SES Developer Guide.*

*Required:* Yes

*Type:* String

*Update requires:* Replacement


##### `EnableSend`

Whether to enable outbound Amazon SES email from the domain. If `true` (the default),
the resulting DNS records will include SES's required verification token and DKIM 
entries.

*Required:* No

*Type:* Boolean

*Default:* `true`

*Update requires:* No interruption


##### `EnableReceive`

Whether to enable inbound Amazon SES email to the domain. If `true`, the resulting
DNS records will include SES's required verification token and inbound MX entry.

*Required:* No

*Type:* Boolean

*Default:* `false`

*Update requires:* No interruption


##### `MailFromSubdomain`

The *subdomain* of [`Domain`](#domain) to use as a custom MAIL FROM domain when sending
through Amazon SES. The default is `mail` (so if your `Custom::SES_Domain` resource has 
`Domain: example.com`, it will by default be provisioned in SES with the custom
MAIL FROM domain `mail.example.com`). The resulting DNS records will include SES's 
required SPF and feedback MX entries for the MAIL FROM domain. 

To *disable* using a custom MAIL FROM domain (and instead use SES's default 
*amazonses.com*), set to an empty string: `MailFromSubdomain: ''`.

This property is only meaningful when [`EnableSend`](#enablesend) is `true`. 

For more information, see [Using a Custom MAIL FROM Domain][custom-mail-from-domain]
in the *Amazon SES Developer Guide.*

*Required:* No

*Type:* String

*Default:* `'mail'`

*Update requires:* No interruption


##### `CustomDMARC`

A custom DMARC value to include in the resulting DNS entries. The default will enable
DMARC for your outbound email in "report only" mode. Note that you *must* include the
double quotes around the entire string (which requires escaping in JSON or wrapping
in single quotes in YAML). Example:

```yaml
    CustomDMARC: '"v=DMARC1; p=reject; pct=100; rua=mailto:postmaster@example.com"'
```

To *disable* generating a DMARC record, set to an empty string: `CustomDMARC: ''`.

This property is only meaningful when [`EnableSend`](#enablesend) is `true`. 

For more information, see the [DMARC.org Overview][DMARC-overview].

*Required:* No

*Type:* String

*Default:* `'"v=DMARC1; p=none; pct=100; sp=none; aspf=r;"'`

*Update requires:* No interruption


##### `TTL`

The time-to-live value to include in resulting DNS records (in seconds).

*Required:* No

*Type:* String

*Default:* `'1800'`

*Update requires:* No interruption


##### `Region`

The AWS Region where your Amazon SES domain will be provisioned, e.g., `"us-east-1"`. 
This must be a region where Amazon SES is supported. The default is the region where
your CloudFormation stack is running (or technically, where the `Custom::SES_Domain` 
lambda function is running.)

*Required:* No

*Type:* String

*Default:* `${AWS::Region}`

*Update requires:* Replacement



### Return Values

#### Ref

When a `Custom::SES_Domain` resource is provided to the `Ref` intrinsic function, 
`Ref` returns an internal resource identifier. Your stack code should not make any
assumptions about the format of this identifier, as it may change in future updates.

(Prior to v0.3, `!Ref MySESDomain` was documented to return the domain. This is no 
longer true, and updated code should instead use `!GetAtt MySESDomain.Domain`.)


#### Fn::GetAtt

A `Custom::SES_Domain` resource returns several [`Fn::GetAtt`][GetAtt] attributes that 
can be used with other CloudFormation resources to maintain the required DNS records 
for your Amazon SES domain.


##### `Route53RecordSets`

A List of [`AWS::Route53::RecordSet`][RecordSet] objects specifying the DNS records
required for the `Custom::SES_Domain` identity.

This is suitable for use as the `RecordSets` property of an 
[`AWS::Route53::RecordSetGroup`][RecordSetGroup] resource. E.g.:

```yaml
  MyRoute53RecordsForSES:
    Type: AWS::Route53::RecordSetGroup
    Properties:
      # HostedZone or HostedZoneName: ...
      RecordSets: !GetAtt MySESDomain.Route53RecordSets
```

If you update a `Custom::SES_Domain` resource, the `Route53RecordSets` attribute 
will change accordingly, and CloudFormation will figure out the precise updates 
needed to the Route 53 records.


##### `ZoneFileEntries`

A List of String lines that can be used in a standard [Zone File][ZoneFile] to specify 
the DNS records required for the `Custom::SES_Domain` identity. The *name* field in each
entry is a fully qualified hostname (ends in a period).

Example:
```yaml
[
  '_amazonses.example.com.         1800  IN  TXT    "abcde12345"',
  'abcde1._domainkey.example.com.  1800  IN  CNAME  abcde1.dkim.amazonses.com.',
  'fghij2._domainkey.example.com.  1800  IN  CNAME  fghij2.dkim.amazonses.com.',
  'klmno3._domainkey.example.com.  1800  IN  CNAME  klmno3.dkim.amazonses.com.',
  'mail.example.com.               1800  IN  MX     10 feedback-smtp.us-west-1.amazonses.com.',
  'mail.example.com.               1800  IN  TXT    "v=spf1 include:amazonses.com -all"',
  '_dmarc.example.com.             1800  IN  TXT    "v=DMARC1; p=none; pct=100; sp=none; aspf=r;"',
  'example.com.                    1800  IN  MX     10 inbound-smtp.us-west-1.amazonaws.com.'
]
```

This can be useful if you are working with a DNS provider other than Route 53. For
example, to include the zone file entries in your stack's output, use something like:

```yaml
Outputs:
  ZoneFileEntries:
    Description: Add these lines to the zone file at your DNS provider.
    Value: !Join ["\n", !GetAtt MySESDomain.ZoneFileEntries]
```


##### Other attributes

A `Custom::SES_Domain` resource provides several other SES-related attributes which
may be helpful for generating custom DNS records or other purposes:

* `Domain` (String): The [`Domain`](#domain), without any trailing period. 
* `VerificationToken` (String): The VerificationToken returned from 
  [SES:VerifyDomainIdentity][VerifyDomainIdentity]
* `DkimTokens` (List of String): The list of DkimTokens returned from 
  [SES:VerifyDomainDkim][VerifyDomainDkim] 
  (not available if [`EnableSend`](#enablesend) is false)
* `MailFromDomain` (String): the custom MAIL FROM domain, e.g., `mail.example.com`
  (not available if [`EnableSend`](#enablesend) is false 
  or if [`MailFromSubdomain`](#mailfromsubdomain) is empty)
* `MailFromMX` (String): the feedback MX host to use with a custom MAIL FROM domain,
  e.g., `feedback-smtp.us-east-1.amazonses.com` 
  (not available if [`EnableSend`](#enablesend) is false 
  or if [`MailFromSubdomain`](#mailfromsubdomain) is empty)
* `MailFromSPF` (String): the SPF record value to use with a custom MAIL FROM domain
  (including the double quotes), e.g., `"v=spf1 include:amazonses.com -all"`
  (not available if [`EnableSend`](#enablesend) is false 
  or if [`MailFromSubdomain`](#mailfromsubdomain) is empty)
* `DMARC` (String): the DMARC record value to use for outbound mail (including the 
  double quotes), e.g., `"v=DMARC1; p=none; pct=100; sp=none; aspf=r;"`
  (not available if [`EnableSend`](#enablesend) is false 
  or if [`CustomDMARC`](#customdmarc) is empty)
* `ReceiveMX` (String): the inbound MX host to use for receiving email, e.g.,
  `inbound-smtp.us-east-1.amazonaws.com` 
  (not available if [`EnableReceive`](#enablereceive) is false) 


### Validating Your Templates

If you use [cfn-lint][] (recommended!) to check your CloudFormation templates,
you can include an "override spec" so your `Custom::SES_Domain` properties and 
attributes will be validated. Download a copy of 
[CustomSESDomainSpecification.json](CustomSESDomainSpecification.json) and then:

```bash
cfn-lint --override-spec CustomSESDomainSpecification.json YOUR-TEMPLATE.cf.yaml
``` 

(Without the override-spec, cfn-lint will allow *any* properties and values for
`Custom::SES_Domain` resources.)


## Development

Development requires GNU Make (standard on most Linux-like systems) and [pipenv][].
(Pipenv is used only to manage the development environment; package requirements are
tracked in `setup.py`.)

To set up your development environment, clone the repository and then run `make init`.
(This just runs `pipenv install`. If you are a package maintainer who will release
to PyPI, use `pipenv install --dev` instead.)

To see a list of available make targets, run `make help`.

To package and upload your own version of the Lambda zip package and the CloudFormation
templates, run `make S3_BUCKET=your_bucket_name upload`. If you just want to build 
locally without uploading to S3, run `make S3_BUCKET=your_bucket_name all`. You can also
include `S3_PREFIX=your/s3/prefix` or `S3_PREFIX=` in either of these commands,
if desired.

If you are changing code, you will want to run tests (`make test`) and static code
checks (`make check`) before uploading.

Additional development customization variables are documented near the top 
of the Makefile.


## Alternatives

These packages offer similar functionality (and provided some helpful background
for `Custom::SES_Domain`):

* https://medium.com/poka-techblog/verify-domains-for-ses-using-cloudformation-8dd185c9b05c
* https://github.com/binxio/cfn-ses-provider

Both of these manage your Route 53 records directly from the Lambda Function 
(rather than leaving that to other CloudFormation resources), and they may support 
fewer Amazon SES domain identity options than this package.


## Future

The `Custom::SES_Domain` implementation is currently missing these Amazon SES 
domain identity features:

* Control over SNS feedback notifications and forwarding options
  (SES:SetIdentityNotificationTopic and SES:SetIdentityFeedbackForwardingEnabled)
* Control over Easy DKIM enabling (SES:SetIdentityDkimEnabled—currently, 
  `Custom::SES_Domain` assumes if you are enabling sending, you also want Easy DKIM)

Adding them is likely straightforward; contributions are welcome.

Are you from Amazon? It'd be great to have an `AWS::SES::Domain` resource
standard in CloudFormation. Please consider adopting or obsoleting this package. 
(Just reach out if you'd like me to assign or transfer it.)


[cfn-lint]:
  https://github.com/awslabs/cfn-python-lint
[CloudFormation]:
  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html
[custom-mail-from-domain]: 
  https://docs.aws.amazon.com/ses/latest/DeveloperGuide/mail-from.html
[custom-resource]: 
  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-custom-resources.html
[CustomResource]:
  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cfn-customresource.html
[DMARC-overview]: 
  https://dmarc.org/overview/
[GetAtt]:
  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html
[NestedStack]: 
  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-nested-stacks.html
[RecordSet]: 
  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-recordset.html
[RecordSetGroup]: 
  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-recordsetgroup.html
[pipenv]:
  https://pipenv.readthedocs.io/
[releases]: 
  https://github.com/medmunds/aws-cfn-ses-domain/releases
[ses-smtp-endpoints]: 
  https://docs.aws.amazon.com/ses/latest/DeveloperGuide/regions.html#region-endpoints
[VerifyDomainDkim]: 
  https://docs.aws.amazon.com/ses/latest/APIReference/API_VerifyDomainDkim.html
[VerifyDomainIdentity]: 
  https://docs.aws.amazon.com/ses/latest/APIReference/API_VerifyDomainIdentity.html
[verifying-ses-domains]: 
  https://docs.aws.amazon.com/ses/latest/DeveloperGuide/verify-domains.html
[ZoneFile]: 
  https://en.wikipedia.org/wiki/Zone_file
