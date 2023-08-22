#!/usr/bin/env python3

import os
import sys
import argparse
import json
import re
import subprocess
import shlex

class Session:
    def __init__(self):
        self.ignore_missing = False
        self.run = True
        self.verbose = False
        self.dockerfile = None

    def verbose_log(self, message):
        if self.verbose:
            print(message)

def process_docker_directory(directory, session):
    session.verbose_log('Processing Directory: %s' % directory)

    # Read the Dockerfile and process options
    dockerfile = session.dockerfile
    if dockerfile is None or dockerfile == '':
        dockerfile = os.path.join(directory, 'Dockerfile')

    build_opts = ""
    run_opts = ""
    image_opts = ""

    # Read the dockerfile for processing
    lines = []
    try:
        with open(dockerfile, 'r') as file:
            lines = file.read().splitlines()
    except FileNotFoundError as e:
        print('Dockerfile (%s) not found' % dockerfile)
        if session.ignore_missing:
            return
        else:
            raise

    # Look for any of the Dockerfile options affecting the build or run
    for line in lines:
        match = re.search('^\s*#\s*BUILD_OPTS\s*(.*)', line)
        if match is not None:
            build_opts = "%s %s" % (build_opts, match.groups()[0])
            continue

        match = re.search('^\s*#\s*RUN_OPTS\s*(.*)', line)
        if match is not None:
            run_opts = "%s %s" % (run_opts, match.groups()[0])
            continue

        match = re.search('^\s*#\s*IMAGE_OPTS\s*(.*)', line)
        if match is not None:
            image_opts = "%s %s" % (image_opts, match.groups()[0])
            continue

    session.verbose_log('Build Options: %s' % build_opts)
    session.verbose_log('Run Options: %s' % run_opts)
    session.verbose_log('Image Options: %s' % image_opts)

    # Perform a build of the Dockerfile
    build_cmd = ('docker build -f %s -q %s ' % (dockerfile, directory)) + build_opts
    if session.shell:
        call_args = build_cmd
    else:
        call_args = shlex.split(build_cmd)
        call_args = [os.path.expandvars(x) for x in call_args]

    session.verbose_log('Build call args: %s' % call_args)

    docker_image = subprocess.check_output(call_args, shell=session.shell).decode('ascii').splitlines()[0]
    session.verbose_log("Docker image SHA: %s" % docker_image)

    # Run the container image
    if session.run:
        session.verbose_log('Running container image')

        run_cmd = 'docker run --rm -it %s %s %s ' % (run_opts, docker_image, image_opts)
        if session.shell:
            call_args = run_cmd
        else:
            call_args = shlex.split(run_cmd)
            call_args = [os.path.expandvars(x) for x in call_args]

        session.verbose_log('Run call args: %s' % call_args)

        subprocess.check_call(call_args, shell=session.shell)

def main():
    # Process the command line arguments
    parser = argparse.ArgumentParser(
        prog='dfbar',
        description='Dockerfile Build and Run',
        exit_on_error=False
    )

    # Mutually exclusive group for profile or directory argument
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-d',
        action='store',
        dest='directory',
        help='A directory containing a Dockerfile to build and run or a base directory, if -b is specified')

    group.add_argument('-p',
        action='store',
        dest='profile',
        help='The name of a directory under ~/.dfbar to build and run')

    # Mutually exclusive group for base directory or Dockerfile specification
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-f',
        action='store',
        dest='dockerfile',
        help='Override the location of the Dockerfile. Only effective with -d')

    group.add_argument('-b',
        action='store_true',
        dest='basedir',
        help='The directory specified is a base directory and subdirectories should be processed instead. Only effective with -d')

    # Other options
    parser.add_argument('-n',
        action='store_false',
        dest='run',
        help='Do not run the Dockerfile, only build')

    parser.add_argument('-i',
        action='store_true',
        dest='ignore_missing',
        help='Ignore missing Dockerfiles when running with a base directory')

    parser.add_argument('-v',
        action='store_true',
        dest='verbose',
        help='Verbose output')

    parser.add_argument('-s',
        action='store_true',
        dest='shell',
        help='Use the shell to execute the build, run and image options. This can be dangerous if the Dockerfile is from an untrusted source')

    args = parser.parse_args()
    session = Session()

    # These options are global and do not depend on the mode we're running in
    session.verbose = args.verbose
    session.run = args.run
    session.shell = args.shell

    directories = []
    # If we have a profile, set the directory to the location of the profile
    if args.profile is not None and args.profile != "":
        if args.basedir:
            print('Warning: Base directory is not valid with a profile name.')

        if args.dockerfile:
            print('Warning: Dockerfile is not valid with a profile name.')

        if args.ignore_missing:
            print('Warning: ignore missing does not apply with a profile name.')

        directories = [ os.path.join(os.path.expanduser('~'), '.dfbar', args.profile) ]
    else:
        # No profile, so a directory is mandatory
        if args.directory is None or args.directory == '':
            raise Exception('Could not determine directory. Profile or directory missing')

        directories = [ args.directory ]

        # If basedir is true, then the directory specified is a parent to the actual Dockerfile directories
        # and subdirectories should be enumerated
        if args.basedir:
            if args.dockerfile:
                print('Warning: Dockerfile is not valid with a base directory.')

            # Collect a list of subdirectories and sort lexically
            directories = [x.path for x in os.scandir(args.directory) if x.is_dir() ]
            directories.sort()

            # This is a basedir, so accept the ignore_missing argument
            session.ignore_missing = args.ignore_missing
        else:
            # This is a single dockerfile directory
            if args.ignore_missing:
                print('Warning: ignore missing does not apply with a single directory.')

            # No basedir, so the dockerfile may be overridden
            session.dockerfile = args.dockerfile

    session.verbose_log('Processing directories:')
    session.verbose_log(json.dumps(directories, indent=2))
    session.verbose_log('')

    # Process the directory/directories
    try:
        for dirname in directories:
            process_docker_directory(dirname, session)
    except Exception as e:
        raise Exception('Directory processing failed with error: %s' % e)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(e)
        sys.exit(1)

    sys.exit(0)
