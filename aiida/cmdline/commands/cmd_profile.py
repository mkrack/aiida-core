# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""`verdi profile` command."""
import click

from aiida.cmdline.commands.cmd_verdi import verdi
from aiida.cmdline.groups import DynamicEntryPointCommandGroup
from aiida.cmdline.params import arguments, options
from aiida.cmdline.params.options.commands import setup
from aiida.cmdline.utils import defaults, echo
from aiida.common import exceptions
from aiida.manage.configuration import Profile, create_profile, get_config


@verdi.group('profile')
def verdi_profile():
    """Inspect and manage the configured profiles."""


def command_create_profile(
    ctx: click.Context,
    storage_cls,
    non_interactive: bool,
    profile: Profile,
    set_as_default: bool = True,
    **kwargs
):  # pylint: disable=unused-argument
    """Create a new profile, initialise its storage and create a default user.

    :param ctx: The context of the CLI command.
    :param storage_cls: The storage class obtained through loading the entry point from ``aiida.storage`` group.
    :param non_interactive: Whether the command was invoked interactively or not.
    :param profile: The profile instance. This is an empty ``Profile`` instance created by the command line argument
        which currently only contains the selected profile name for the profile that is to be created.
    :param set_as_default: Whether to set the created profile as the new default.
    :param kwargs: Arguments to initialise instance of the selected storage implementation.
    """
    try:
        profile = create_profile(ctx.obj.config, storage_cls, name=profile.name, **kwargs)
    except (ValueError, TypeError, exceptions.EntryPointError, exceptions.StorageMigrationError) as exception:
        echo.echo_critical(str(exception))

    echo.echo_success(f'Created new profile `{profile.name}`.')

    if set_as_default:
        ctx.invoke(profile_setdefault, profile=profile)


@verdi_profile.group(
    'setup',
    cls=DynamicEntryPointCommandGroup,
    command=command_create_profile,
    entry_point_group='aiida.storage',
    shared_options=[
        setup.SETUP_PROFILE(),
        setup.SETUP_PROFILE_SET_AS_DEFAULT(),
        setup.SETUP_USER_EMAIL(),
        setup.SETUP_USER_FIRST_NAME(),
        setup.SETUP_USER_LAST_NAME(),
        setup.SETUP_USER_INSTITUTION(),
    ]
)
def profile_setup():
    """Set up a new profile."""


@verdi_profile.command('list')
def profile_list():
    """Display a list of all available profiles."""
    try:
        config = get_config()
    except (exceptions.MissingConfigurationError, exceptions.ConfigurationError) as exception:
        # This can happen for a fresh install and the `verdi setup` has not yet been run. In this case it is still nice
        # to be able to see the configuration directory, for instance for those who have set `AIIDA_PATH`. This way
        # they can at least verify that it is correctly set.
        from aiida.manage.configuration.settings import AIIDA_CONFIG_FOLDER
        echo.echo_report(f'configuration folder: {AIIDA_CONFIG_FOLDER}')
        echo.echo_critical(str(exception))
    else:
        echo.echo_report(f'configuration folder: {config.dirpath}')

    if not config.profiles:
        echo.echo_warning('no profiles configured: run `verdi setup` to create one')
    else:
        sort = lambda profile: profile.name  # pylint: disable=unnecessary-lambda-assignment
        highlight = lambda profile: profile.name == config.default_profile_name  # pylint: disable=unnecessary-lambda-assignment
        echo.echo_formatted_list(config.profiles, ['name'], sort=sort, highlight=highlight)


def _strip_private_keys(dct: dict):
    """Remove private keys (starting `_`) from the dictionary."""
    return {
        key: _strip_private_keys(value) if isinstance(value, dict) else value
        for key, value in dct.items()
        if not key.startswith('_')
    }


@verdi_profile.command('show')
@arguments.PROFILE(default=defaults.get_default_profile)
def profile_show(profile):
    """Show details for a profile."""

    if profile is None:
        echo.echo_critical('no profile to show')

    echo.echo_report(f'Profile: {profile.name}')
    config = _strip_private_keys(profile.dictionary)
    echo.echo_dictionary(config, fmt='yaml')


@verdi_profile.command('setdefault')
@arguments.PROFILE(required=True, default=None)
def profile_setdefault(profile):
    """Set a profile as the default one."""
    try:
        config = get_config()
    except (exceptions.MissingConfigurationError, exceptions.ConfigurationError) as exception:
        echo.echo_critical(str(exception))

    config.set_default_profile(profile.name, overwrite=True).store()
    echo.echo_success(f'{profile.name} set as default profile')


@verdi_profile.command('delete')
@options.FORCE(help='to skip questions and warnings about loss of data')
@click.option(
    '--include-config/--skip-config',
    default=True,
    show_default=True,
    help='Include deletion of entry in configuration file.'
)
@click.option(
    '--include-db/--skip-db',
    'include_database',
    default=True,
    show_default=True,
    help='Include deletion of associated database.'
)
@click.option(
    '--include-db-user/--skip-db-user',
    'include_database_user',
    default=False,
    show_default=True,
    help='Include deletion of associated database user.'
)
@click.option(
    '--include-repository/--skip-repository',
    default=True,
    show_default=True,
    help='Include deletion of associated file repository.'
)
@arguments.PROFILES(required=True)
def profile_delete(force, include_config, include_database, include_database_user, include_repository, profiles):
    """Delete one or more profiles.

    The PROFILES argument takes one or multiple profile names that will be deleted. Deletion here means that the profile
    will be removed including its file repository and database. The various options can be used to control which parts
    of the profile are deleted.
    """
    if not include_config:
        echo.echo_deprecated('the `--skip-config` option is deprecated and is no longer respected.')

    for profile in profiles:

        includes = {
            'database': include_database,
            'database user': include_database_user,
            'file repository': include_repository
        }

        if not all(includes.values()):
            excludes = [label for label, value in includes.items() if not value]
            message_suffix = f' excluding: {", ".join(excludes)}.'
        else:
            message_suffix = '.'

        echo.echo_warning(f'deleting profile `{profile.name}`{message_suffix}')
        echo.echo_warning('this operation cannot be undone, ', nl=False)

        if not force and not click.confirm('are you sure you want to continue?'):
            echo.echo_report(f'deleting of `{profile.name} cancelled.')
            continue

        get_config().delete_profile(
            profile.name,
            include_database=include_database,
            include_database_user=include_database_user,
            include_repository=include_repository
        )
        echo.echo_success(f'profile `{profile.name}` was deleted{message_suffix}.')
