#!/bin/env python3
import argparse
import mimetypes
import re
import sys
from os import path, getenv


def die(message, status=1):
    sys.stderr.write(message)
    sys.stderr.write('\n')
    sys.exit(status)


try:
    import github3
except ImportError:
    if __name__ == '__main__':
        die("Required `github3` package not found. Perhaps you forgot to activate the "
            "development virtualenv? (Try `pipenv run {argv})`".format(
                argv=" ".join(sys.argv)),
            status=255)
    raise


class CommandError(Exception):
    pass


parser = argparse.ArgumentParser(
    description='Publish release in GitHub, with optional asset upload.')
parser.add_argument('-r', '--repo',
                    required=True,
                    metavar='OWNER/REPO',
                    help="Required: GitHub repository")
parser.add_argument('-t', '--tag',
                    required=True,
                    metavar='RELEASE_TAG',
                    help="Required: Git tag for release (e.g., 'v1.3'; "
                         "must already exist in GitHub repository)")
parser.add_argument('-d', '--description',
                    metavar="MARKDOWN",
                    default="Release {tag}",
                    help="Release description ('{repo}' and '{tag}' substitute that info, "
                         "'{*_id} for markdown heading anchor id'; default: 'Release {tag}')")
parser.add_argument('-a', '--assets', nargs='+',
                    metavar='FILE',
                    help="Release assets to upload")
parser.add_argument('--release-without-draft',
                    action='store_false',
                    dest='draft',
                    help="Whether to release immediately (default: just publish a draft release)")
parser.add_argument('--token',
                    help="GitHub token (default: from env GITHUB_TOKEN)")


def run(args=None):
    options = parser.parse_args(args=args)

    token = options.token or getenv('GITHUB_TOKEN')
    if token is None:
        raise CommandError("GITHUB_TOKEN not found in env or as --token")
    github = github3.login(token=token)

    try:
        owner_name, repo_name = options.repo.split('/')
    except (TypeError, ValueError):
        raise CommandError(f"Invalid format for owner/repository '{options.repo}'")

    repo = github.repository(owner_name, repo_name)

    # Publish the draft release
    formatted_description = options.description.format(
        tag=options.tag, tag_id=github_markdown_anchor(options.tag),
        repo=options.repo, repo_id=github_markdown_anchor(options.repo))
    release = repo.create_release(tag_name=options.tag, name=options.tag,
                                  body=formatted_description, draft=options.draft)

    # Upload the assets
    for filepath in options.assets:
        filename = path.basename(filepath)
        with open(filepath, 'rb') as file:
            content_type, encoding = mimetypes.guess_type(filename)
            content_type = content_type or 'application/octet-stream'
            release.upload_asset(content_type, filename, file)

    return options.tag, formatted_description


def github_markdown_anchor(text):
    """Returns the GitHub markdown anchor id for given heading text"""
    # See https://github.com/jch/html-pipeline/blob/v2.12.0/lib/html/pipeline/toc_filter.rb#L43-L45.
    # (Thanks @TomOnTime https://gist.github.com/asabaylus/3071099#gistcomment-1593627.)
    # (This doesn't have exactly the same handling for non-ASCII text, and isn't aware of duplicates.)
    PUNCTUATION_REGEXP = r'[^\w\- ]'
    text = text.lower()
    id = re.sub(PUNCTUATION_REGEXP, '', text)
    id = id.replace(' ', '-')
    return id


if __name__ == '__main__':
    try:
        name, description = run()
    except CommandError as err:
        die(str(err))
    else:
        sys.stdout.write(
            "Set release {name} description to:\n{description}\n".format(
                name=name, description=description))
