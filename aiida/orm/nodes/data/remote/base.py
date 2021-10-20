# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Data plugin that models a folder on a remote computer."""
import os

from aiida.orm import AuthInfo

from ..data import Data

__all__ = ('RemoteData',)


class RemoteData(Data):
    """
    Store a link to a file or folder on a remote machine.

    Remember to pass a computer!
    """

    def __init__(self, remote_path=None, **kwargs):
        super().__init__(**kwargs)
        if remote_path is not None:
            self.set_remote_path(remote_path)

    def get_remote_path(self):
        return self.get_attribute('remote_path')

    def set_remote_path(self, val):
        self.set_attribute('remote_path', val)

    @property
    def is_empty(self):
        """
        Check if remote folder is empty
        """
        authinfo = self.get_authinfo()
        transport = authinfo.get_transport()

        with transport:
            try:
                transport.chdir(self.get_remote_path())
            except IOError:
                # If the transport IOError the directory no longer exists and was deleted
                return True

            return not transport.listdir()

    def getfile(self, relpath, destpath):
        """
        Connects to the remote folder and retrieves the content of a file.

        :param relpath:  The relative path of the file on the remote to retrieve.
        :param destpath: The absolute path of where to store the file on the local machine.
        """
        authinfo = self.get_authinfo()

        with authinfo.get_transport() as transport:
            try:
                full_path = os.path.join(self.get_remote_path(), relpath)
                transport.getfile(full_path, destpath)
            except IOError as exception:
                if exception.errno == 2:  # file does not exist
                    raise IOError(
                        'The required remote file {} on {} does not exist or has been deleted.'.format(
                            full_path,
                            self.computer.label  # pylint: disable=no-member
                        )
                    ) from exception
                raise

    def listdir(self, relpath='.'):
        """
        Connects to the remote folder and lists the directory content.

        :param relpath: If 'relpath' is specified, lists the content of the given subfolder.
        :return: a flat list of file/directory names (as strings).
        """
        authinfo = self.get_authinfo()

        with authinfo.get_transport() as transport:
            try:
                full_path = os.path.join(self.get_remote_path(), relpath)
                transport.chdir(full_path)
            except IOError as exception:
                if exception.errno in (2, 20):  # directory not existing or not a directory
                    exc = IOError(
                        'The required remote folder {} on {} does not exist, is not a directory or has been deleted.'.
                        format(full_path, self.computer.label)  # pylint: disable=no-member
                    )
                    exc.errno = exception.errno
                    raise exc from exception
                else:
                    raise

            try:
                return transport.listdir()
            except IOError as exception:
                if exception.errno in (2, 20):  # directory not existing or not a directory
                    exc = IOError(
                        'The required remote folder {} on {} does not exist, is not a directory or has been deleted.'.
                        format(full_path, self.computer.label)  # pylint: disable=no-member
                    )
                    exc.errno = exception.errno
                    raise exc from exception
                else:
                    raise

    def listdir_withattributes(self, path='.'):
        """
        Connects to the remote folder and lists the directory content.

        :param relpath: If 'relpath' is specified, lists the content of the given subfolder.
        :return: a list of dictionaries, where the documentation is in :py:class:Transport.listdir_withattributes.
        """
        authinfo = self.get_authinfo()

        with authinfo.get_transport() as transport:
            try:
                full_path = os.path.join(self.get_remote_path(), path)
                transport.chdir(full_path)
            except IOError as exception:
                if exception.errno in (2, 20):  # directory not existing or not a directory
                    exc = IOError(
                        'The required remote folder {} on {} does not exist, is not a directory or has been deleted.'.
                        format(full_path, self.computer.label)  # pylint: disable=no-member
                    )
                    exc.errno = exception.errno
                    raise exc from exception
                else:
                    raise

            try:
                return transport.listdir_withattributes()
            except IOError as exception:
                if exception.errno in (2, 20):  # directory not existing or not a directory
                    exc = IOError(
                        'The required remote folder {} on {} does not exist, is not a directory or has been deleted.'.
                        format(full_path, self.computer.label)  # pylint: disable=no-member
                    )
                    exc.errno = exception.errno
                    raise exc from exception
                else:
                    raise

    def _clean(self):
        """
        Remove all content of the remote folder on the remote computer
        """
        from aiida.orm.utils.remote import clean_remote

        authinfo = self.get_authinfo()
        transport = authinfo.get_transport()
        remote_dir = self.get_remote_path()

        with transport:
            clean_remote(transport, remote_dir)

    def _validate(self):
        from aiida.common.exceptions import ValidationError

        super()._validate()

        try:
            self.get_remote_path()
        except AttributeError as exception:
            raise ValidationError("attribute 'remote_path' not set.") from exception

        computer = self.computer
        if computer is None:
            raise ValidationError('Remote computer not set.')

    def get_authinfo(self):
        return AuthInfo.objects(self.backend).get(dbcomputer=self.computer, aiidauser=self.user)
