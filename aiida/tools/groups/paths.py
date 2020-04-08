# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Provides functionality for managing large numbers of AiiDA Groups, via label delimitation."""
from collections import namedtuple
from functools import total_ordering
import re
from typing import Any, Iterable, List, Optional  # pylint: disable=unused-import
import warnings

from aiida import orm
from aiida.common.exceptions import NotExistent

__all__ = ('GroupPath', 'InvalidPath')

REGEX_ATTR = re.compile('^[a-zA-Z][\\_a-zA-Z0-9]*$')


class InvalidPath(Exception):
    """An exception to indicate that a path is not valid."""


class GroupNotFoundError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = 'No such group: {}'.format(grouppath.path)
        super().__init__(msg)


class GroupNotUniqueError(Exception):
    """An exception raised when a path has multiple associated groups."""

    def __init__(self, grouppath):
        msg = 'The path is not unique: {}'.format(grouppath.path)
        super().__init__(msg)


class NoGroupsInPathError(Exception):
    """An exception raised when a path has multiple associated groups."""

    def __init__(self, grouppath):
        msg = 'The path does not contain any descendant groups: {}'.format(grouppath.path)
        super().__init__(msg)


WalkNodeResult = namedtuple('WalkNodeResult', ['group_path', 'node'])


@total_ordering
class GroupPath:
    """A class to provide label delimited access to groups.

    See tests for usage examples.
    """

    def __init__(self, path='', type_string=orm.GroupTypeString.USER.value, warn_invalid_child=True):
        # type: (str, Optional[str], Optional[GroupPath])
        """Instantiate the class.

        :param path: The initial path of the group.
        :param type_string: Used to query for and instantiate a ``Group`` with.
        :param warn_invalid_child: Issue a warning, when iterating children, if a child path is invalid.

        """
        self._delimiter = '/'
        if not isinstance(type_string, str):
            raise TypeError('type_string must a str: {}'.format(type_string))
        self._type_string = type_string
        self._path_string = self._validate_path(path)
        self._path_list = self._path_string.split(self._delimiter) if path else []
        self._warn_invalid_child = warn_invalid_child

    def _validate_path(self, path):
        """Validate the supplied path."""
        if path == self._delimiter:
            return ''
        if self._delimiter * 2 in path:
            raise InvalidPath("The path may not contain a duplicate delimiter '{}': {}".format(self._delimiter, path))
        if (path.startswith(self._delimiter) or path.endswith(self._delimiter)):
            raise InvalidPath("The path may not start/end with the delimiter '{}': {}".format(self._delimiter, path))
        return path

    def __repr__(self):
        # type: () -> str
        """Represent the instantiated class."""
        return "{}('{}', type='{}')".format(self.__class__.__name__, self.path, self.type_string)

    def __eq__(self, other):
        # type: (Any) -> bool
        """Compare equality of path and type string to another ``GroupPath`` object."""
        if not isinstance(other, GroupPath):
            return NotImplemented
        return (self.path, self.type_string) == (other.path, other.type_string)

    def __lt__(self, other):
        # type: (Any) -> bool
        """Compare less-than operator of path and type string to another ``GroupPath`` object."""
        if not isinstance(other, GroupPath):
            return NotImplemented
        return (self.path, self.type_string) < (other.path, other.type_string)

    @property
    def path(self):
        # type: () -> str
        """Return the path string."""
        return self._path_string

    @property
    def path_list(self):
        # type: () -> List[str]
        """Return a list of the path components."""
        return self._path_list[:]

    @property
    def key(self):
        # type: () -> str
        """Return the final component of the the path."""
        if self._path_list:
            return self._path_list[-1]
        return None

    @property
    def delimiter(self):
        # type: () -> str
        """Return the delimiter used to split path into components."""
        return self._delimiter

    @property
    def type_string(self):
        # type: () -> str
        """Return the type_string used to query for and instantiate a ``Group`` with."""
        return self._type_string

    @property
    def parent(self):
        # type: () -> Optional[GroupPath]
        """Return the parent path."""
        if self.path_list:
            return GroupPath(
                self.delimiter.join(self.path_list[:-1]),
                type_string=self.type_string,
                warn_invalid_child=self._warn_invalid_child
            )
        return None

    def __truediv__(self, path):
        # type: (str) -> GroupPath
        """Return a child ``GroupPath``, with a new path formed by appending ``path`` to the current path."""
        if not isinstance(path, str):
            raise TypeError('path is not a string: {}'.format(path))
        path = self._validate_path(path)
        child = GroupPath(
            path=self.path + self.delimiter + path if self.path else path,
            type_string=self.type_string,
            warn_invalid_child=self._warn_invalid_child
        )
        return child

    def __getitem__(self, path):
        # type: (str) -> GroupPath
        """Return a child ``GroupPath``, with a new path formed by appending ``path`` to the current path."""
        return self.__truediv__(path)

    def get_group(self):
        # type: () -> Optional[orm.Group]
        """Return the concrete group associated with this path."""
        try:
            return orm.Group.objects.get(label=self.path, type_string=self.type_string)
        except NotExistent:
            return None

    @property
    def group_ids(self):
        # type: () -> List[int]
        """Return all the UUID associated with this GroupPath.

        :returns: and empty list, if no group associated with this label,
            or can be multiple if type_string was None

        This is an efficient method for checking existence,
        which does not require the (slow) loading of the ORM entity.
        """
        query = orm.QueryBuilder()
        filters = {'label': self.path}
        if self.type_string is not None:
            filters['type_string'] = self.type_string
        query.append(orm.Group, filters=filters, project='id')
        return [r[0] for r in query.all()]

    @property
    def is_virtual(self):
        # type: () -> bool
        """Return whether there is one or more concrete groups associated with this path."""
        return len(self.group_ids) == 0

    def get_or_create_group(self):
        # type: () -> (orm.Group, bool)
        """Return the concrete group associated with this path or, create it, if it does not already exist."""
        if self.type_string is not None:
            return orm.Group.objects.get_or_create(label=self.path, type_string=self.type_string)
        return orm.Group.objects.get_or_create(label=self.path)

    def delete_group(self):
        """Delete the concrete group associated with this path.

        :raises: GroupNotFoundError, GroupNotUniqueError
        """
        ids = self.group_ids
        if not ids:
            raise GroupNotFoundError(self)
        if len(ids) > 1:
            raise GroupNotUniqueError(self)
        orm.Group.objects.delete(ids[0])

    @property
    def children(self):
        # type: () -> Iterable[GroupPath]
        """Iterate through all (direct) children of this path."""
        query = orm.QueryBuilder()
        filters = {}
        if self.path:
            filters['label'] = {'like': self.path + self.delimiter + '%'}
        if self.type_string is not None:
            filters['type_string'] = self.type_string
        query.append(orm.Group, filters=filters, project='label')
        if query.count() == 0 and self.is_virtual:
            raise NoGroupsInPathError(self)

        yielded = []
        for (label,) in query.iterall():
            path = label.split(self._delimiter)
            if len(path) <= len(self._path_list):
                continue
            path_string = self._delimiter.join(path[:len(self._path_list) + 1])
            if (path_string not in yielded and path[:len(self._path_list)] == self._path_list):
                yielded.append(path_string)
                try:
                    yield GroupPath(
                        path=path_string, type_string=self.type_string, warn_invalid_child=self._warn_invalid_child
                    )
                except InvalidPath:
                    if self._warn_invalid_child:
                        warnings.warn('invalid path encountered: {}'.format(path_string))  # pylint: disable=no-member

    def __iter__(self):
        # type: () -> Iterable[GroupPath]
        """Iterate through all (direct) children of this path."""
        return self.children

    def __len__(self):
        # type: () -> int
        """Return the number of children for this path."""
        return sum(1 for _ in self.children)

    def __contains__(self, key):
        # type: (str) -> bool
        """Return whether a child exists for this key."""
        for child in self.children:
            if child.path_list[-1] == key:
                return True
        return False

    def walk(self, return_virtual=True):
        # type: () -> Iterable[GroupPath]
        """Recursively iterate through all children of this path."""
        for child in self:
            if return_virtual or not child.is_virtual:
                yield child
            for sub_child in child.walk(return_virtual=return_virtual):
                if return_virtual or not sub_child.is_virtual:
                    yield sub_child

    def walk_nodes(self, filters=None, node_class=None, query_batch=None):
        # type: () -> Iterable[WalkNodeResult]
        """Recursively iterate through all nodes of this path and its children.

        :param filters: filters to apply to the node query
        :param node_class: return only nodes of a certain class (or list of classes)
        :param int batch_size: The size of the batches to ask the backend to batch results in subcollections.
            You can optimize the speed of the query by tuning this parameter.
            Be aware though that is only safe if no commit will take place during this transaction.
        """
        query = orm.QueryBuilder()
        group_filters = {}
        if self.path:
            group_filters['label'] = {'or': [{'==': self.path}, {'like': self.path + self.delimiter + '%'}]}
        if self.type_string is not None:
            group_filters['type_string'] = self.type_string
        query.append(orm.Group, filters=group_filters, project='label', tag='group')
        query.append(
            orm.Node if node_class is None else node_class,
            with_group='group',
            filters=filters,
            project=['*'],
        )
        for (label, node) in query.iterall(query_batch) if query_batch else query.all():
            yield WalkNodeResult(GroupPath(label, type_string=self.type_string), node)

    @property
    def browse(self):
        """Return a ``GroupAttr`` instance, for attribute access to children."""
        return GroupAttr(self)


class GroupAttr:
    """A class to provide attribute access to a ``GroupPath`` children.

    The only public attributes on this class are dynamically created from the ``GroupPath`` child keys.
    NOTE: any child keys that do not conform to an acceptable (public) attribute string will be ignored.
    The ``GroupPath`` can be retrieved *via* a function call, e.g.::

        group_path = GroupPath()
        group_attr = GroupAttr(group_path)
        group_attr.a.b.c() == GroupPath("a/b/c")

    """

    def __init__(self, group_path):
        # type: (GroupPath)
        """Instantiate the ``GroupPath``, and a mapping of its children."""
        self._group_path = group_path

    def __repr__(self):
        # type: () -> str
        """Represent the instantiated class."""
        return "{}('{}', type='{}')".format(
            self.__class__.__name__, self._group_path.path, self._group_path.type_string
        )

    def __call__(self):
        # type: () -> GroupPath
        """Return the ``GroupPath``."""
        return self._group_path

    def __dir__(self):
        """Return a list of available attributes."""
        return [c.path_list[-1] for c in self._group_path.children if REGEX_ATTR.match(c.path_list[-1])]

    def __getattr__(self, attr):
        # type: (str) -> GroupAttr
        """Return the requested attribute name."""
        for child in self._group_path.children:
            if attr == child.path_list[-1]:
                return GroupAttr(child)
        raise AttributeError(attr)
