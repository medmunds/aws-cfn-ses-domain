# -*- coding: utf-8 -*-

# Copyright 2018 Michael V. Edmunds
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this software except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

VERSION = (0, 1)
__version__ = ".".join(str(v) for v in VERSION)

NAME = "aws-cfn-ses-domain"
DESCRIPTION = "AWS CloudFormation custom resource for managing Amazon SES domains"
HOMEPAGE = "https://gitlab.com/medmunds/aws-cfn-ses-domain"
AUTHOR = "Mike Edmunds"
AUTHOR_EMAIL = "medmunds@gmail.com"
LICENSE = "Apache License 2.0"

CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Topic :: System :: Installation/Setup',
    'Topic :: System :: Systems Administration',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
]

KEYWORDS = [
    "AWS-CloudFormation",
    "CloudFormation",
    "CloudFormation-custom-resource",
    "CustomResource",
    "Amazon-SES",
    "SES",
    "Route53",
    "AWS-Lambda-Function",
]
