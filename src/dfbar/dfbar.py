#!/usr/bin/env python3

import os
import sys
import argparse
import json
import re
import subprocess
import shlex

class Logger:
    def __init__(self, verbose):
        self.verbose = verbose

    def log_verbose(self, message):
        if self.verbose:
            print(message)

    def log_info(self, message):
        print(message)

    def log_warning(self, message):
        print('WARNING: ' + message)

def process_docker_spec(spec, dockerfile=None, verbose=False,
                             run=True, shell=False, ignore_missing=False, mode=''):
    logger = Logger(verbose)

    # Make sure we have a valid spec
    if spec is None or spec == '':
        raise Exception('Spec must not be empty')

    if not os.path.exists(spec):
        raise Exception('Spec does not exist: %s' % spec)

    # Make sure the mode is valid
    if mode is None:
        mode = 'default'
    elif mode == '' or re.search('^[A-Za-z0-9]+$', mode) is None:
        raise Exception('Invalid mode specified - Must be [A-Za-z0-9]+')

    # Work out what to do with the spec and optional dockerfile
    if dockerfile is not None and dockerfile != '':
        # We have a dockerfile reference, so the spec must be a directory
        if not os.path.isdir(spec):
            raise Exception('Dockerfile specified, but the spec is not a directory')
    else:
        if os.path.isfile(spec):
            dockerfile = spec
            spec = os.path.dirname(dockerfile)
        elif os.path.isdir(spec):
            dockerfile = os.path.join(spec, 'Dockerfile')
        else:
            raise Exception('Could not determine type of target spec: %s' % spec)

    # At this point, spec is the path to the Docker build directory and dockerfile
    # is the location of the actual Dockerfile
    logger.log_verbose('Directory: ' + spec)
    logger.log_verbose('Dockerfile: ' + dockerfile)

    build_opts = ""
    run_opts = ""
    image_opts = ""

    # Read the dockerfile for processing
    lines = []
    try:
        with open(dockerfile, 'r') as file:
            lines = file.read().splitlines()
    except FileNotFoundError as e:
        logger.log_info('Dockerfile (%s) not found' % dockerfile)
        if ignore_missing:
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

        if mode is not None and mode != '':
            match = re.search('^\s*#\s*' + mode + '_BUILD_OPTS\s*(.*)', line)
            if match is not None:
                build_opts = "%s %s" % (build_opts, match.groups()[0])
                continue

            match = re.search('^\s*#\s*' + mode + '_RUN_OPTS\s*(.*)', line)
            if match is not None:
                run_opts = "%s %s" % (run_opts, match.groups()[0])
                continue

            match = re.search('^\s*#\s*' + mode + '_IMAGE_OPTS\s*(.*)', line)
            if match is not None:
                image_opts = "%s %s" % (image_opts, match.groups()[0])
                continue

    logger.log_verbose('Build Options: %s' % build_opts)
    logger.log_verbose('Run Options: %s' % run_opts)
    logger.log_verbose('Image Options: %s' % image_opts)

    # Configure environment variables for use by docker commands
    os.environ['DFBAR_DOCKER_DIR'] = spec
    os.environ['DFBAR_DOCKERFILE'] = dockerfile
    os.environ['DFBAR_USER_ID'] = str(os.getuid())
    os.environ['DFBAR_GROUP_ID'] = str(os.getgid())

    # Perform a build of the Dockerfile
    build_cmd = ('docker build -f %s -q %s ' % (dockerfile, spec)) + build_opts
    if shell:
        call_args = build_cmd
    else:
        call_args = shlex.split(build_cmd)
        call_args = [os.path.expandvars(x) for x in call_args]

    logger.log_verbose('Build call args: %s' % call_args)

    docker_image = subprocess.check_output(call_args, shell=shell).decode('ascii').splitlines()[0]
    logger.log_verbose("Docker image SHA: %s" % docker_image)

    # Run the container image
    if run:
        logger.log_verbose('Running container image')

        interactive_arg = ''
        if sys.stdin.isatty():
            logger.log_verbose('Input is a TTY')
            interactive_arg = ' -i '
        else:
            logger.log_verbose('Input is not a TTY')

        run_cmd = 'docker run --rm %s -t %s %s %s ' % (interactive_arg, run_opts, docker_image, image_opts)
        if shell:
            call_args = run_cmd
        else:
            call_args = shlex.split(run_cmd)
            call_args = [os.path.expandvars(x) for x in call_args]

        logger.log_verbose('Run call args: %s' % call_args)

        subprocess.check_call(call_args, shell=shell)

def main():
    # Process the command line arguments
    parser = argparse.ArgumentParser(
        prog='dfbar',
        description='Dockerfile Build and Run',
        exit_on_error=False
    )

    # Mutually exclusive group to alter default behaviour
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-p',
        action='store_true',
        dest='profile',
        help='A profile name to run. This is the name of a directory under ~/.dfbar to build and run')

    group.add_argument('-f',
        action='store',
        dest='dockerfile',
        help='Override the location of the Dockerfile. This is not valid is spec resolves to a directory')

    group.add_argument('-b',
        action='store_true',
        dest='basedir',
        help='The "spec" is a directory with subdirectories that should be built and run, in lexical order')

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

    parser.add_argument('-m',
        action='store',
        dest='mode',
        default=None,
        help='Mode to apply to the dockerfile build and run. Mode affects the configuration directives read from the Dockerfile')

    parser.add_argument('spec',
        action='store',
        help='The Dockerfile directory, Dockerfile, base directory or image profile, depending on options. Default to determine Dockerfile directory or Dockerfile')

    args = parser.parse_args()
    logger = Logger(args.verbose)

    # Store the options here to allow modification depending on options
    ignore_missing = args.ignore_missing
    dockerfile = args.dockerfile
    verbose = args.verbose
    run = args.run
    shell = args.shell
    mode = args.mode

    spec_list = []

    # Make sure we have a valid spec
    if args.spec is None or args.spec == '':
        raise Exception('Spec must not be empty')

    # If we have a profile, set the directory to the location of the profile
    if args.profile:
        if ignore_missing:
            logger.log_warning('ignore missing does not apply with a profile name.')
            ignore_missing = False

        # dockerfile should be empty and we have an array of a single directory/spec, representing the
        # profile to run
        spec_list = [ os.path.join(os.path.expanduser('~'), '.dfbar', args.spec) ]
    elif args.basedir:
        if dockerfile:
            logger.log_warning('Dockerfile is not valid with a base directory.')
            dockerfile = None

        # Collect a list of subdirectories and sort lexically
        spec_list = [x.path for x in os.scandir(args.spec) if x.is_dir() ]
        spec_list.sort()
    else:
        # Not a base directory or profile

        if ignore_missing:
            logger.log_warning('ignore missing does not apply with a single directory.')
            ignore_missing = False

        spec_list = [ args.spec ]

    logger.log_verbose('Processing specs:')
    logger.log_verbose(json.dumps(spec_list, indent=2))
    logger.log_verbose('')

    # Process the specs
    try:
        for spec in spec_list:
            process_docker_spec(spec, dockerfile=dockerfile,
                                     verbose=verbose, run=run, shell=shell,
                                     ignore_missing=ignore_missing, mode=mode)
    except Exception as e:
        raise Exception('Processing failed with error: %s' % str(e))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(e)
        sys.exit(1)

    sys.exit(0)
