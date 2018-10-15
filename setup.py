from setuptools import setup, find_packages
from os import path


here = path.abspath(path.dirname(__file__))
packages = find_packages(exclude=['build', 'contrib', 'docs', 'tests'])

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Get package metadata from __about__.py (without importing the package)
about = {}
for package in packages:
    try:
        with open(path.join(here, package, '__about__.py')) as f:
            exec(f.read(), about)
    except FileNotFoundError:
        pass

setup(
    name=about["NAME"],
    version=about["__version__"],
    description=about["DESCRIPTION"],
    long_description=long_description,
    long_description_content_type='text/markdown',
    url=about["HOMEPAGE"],
    license=about["LICENSE"],
    author=about["AUTHOR"],
    author_email=about["AUTHOR_EMAIL"],
    classifiers=about["CLASSIFIERS"],
    keywords=" ".join(about["KEYWORDS"]),

    packages=packages,
    python_requires='>=3.6.0',
    install_requires=[
        # Requirements listed here will be bundled into the Lambda Function zip file.
        # Note that the AWS Lambda execution environment has boto3 pre-installed.
        # But if you need a newer version, use something like this to bundle boto3 too:
        # 'boto3>=1.12',
    ],
    extras_require={
        # use `pipenv install --dev` for dev requirements
        'test': ['boto3'],
    },
)
