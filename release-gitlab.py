#!/bin/env python3
import argparse
import sys
from os import path


def die(message, status=1):
    sys.stderr.write(message)
    sys.stderr.write('\n')
    sys.exit(status)


try:
    import gitlab
except ImportError:
    if __name__ == '__main__':
        die("Required `gitlab` package not found. Perhaps you forgot to activate the "
            "development virtualenv? (Try `pipenv run {argv})`".format(
                argv=" ".join(sys.argv)),
            status=255)
    raise


class CommandError(Exception):
    pass


parser = argparse.ArgumentParser(description='Publish release in GitLab, '
                                             'with optional artifacts.')
parser.add_argument('-i', '--id',
                    required=True,
                    dest='project_id',
                    metavar='PROJECT',
                    help="Required: GitLab project id: number or 'username/project'")
parser.add_argument('-n', '--name',
                    required=True,
                    metavar='RELEASE_NAME',
                    help="Required: Git tag for release (e.g., 'v1.3'; "
                         "must already exist in GitLab repository)")
parser.add_argument('-d', '--description',
                    default="Release {name}\n\n{artifacts}",
                    help="Release description (markdown allowed; can use '{name}' "
                         "and '{artifacts}' to include that info)")
parser.add_argument('-a', '--artifacts', nargs='+',
                    metavar='FILE',
                    help="Release artifacts")
# GitLab API options (match python-gitlab's CLI):
parser.add_argument('-c', '--config-file',
                    action='append',
                    help="Configuration file (multiple allowed; "
                         "see Python-GitLab docs for defaults)")
parser.add_argument('-g', '--gitlab',
                    dest='config_section',
                    help="Which configuration section to use"
                         " (default if not present)")


def run(args=None):
    options = parser.parse_args(args=args)
    gl = gitlab.Gitlab.from_config(options.config_section, options.config_file)

    # Retrieve the GitLab project and release
    try:
        project = gl.projects.get(options.project_id)
    except gitlab.GitlabError as err:
        if err.response_code == 404:
            raise CommandError(
                "GitLab project {project_id} not found".format(
                    project_id=options.project_id))
        else:
            raise

    try:
        release_tag = project.tags.get(options.name)
    except gitlab.GitlabError as err:
        if err.response_code == 404:
            raise CommandError(
                "Tag {name} not found at GitLab in project {project_id}".format(
                    name=options.name, project_id=options.project_id))
        else:
            raise

    # Upload files
    artifacts_markdown = []
    for filepath in options.artifacts:
        filename = path.basename(filepath)
        result = project.upload(filename, filepath=filepath)
        artifacts_markdown.append(result['markdown'])

    # Set release description
    formatted_description = options.description.format(
        name=options.name,
        artifacts="\n\n".join(artifacts_markdown))
    release_tag.set_release_description(formatted_description)
    return options.name, formatted_description


if __name__ == '__main__':
    try:
        name, description = run()
    except CommandError as err:
        die(str(err))
    else:
        sys.stdout.write(
            "Set release {name} description to:\n{description}\n".format(
                name=name, description=description))
