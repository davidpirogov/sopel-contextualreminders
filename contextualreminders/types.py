"""
Types used by the plugin for managing configuration
"""
import datetime as dt
from dataclasses import dataclass
from math import inf
from numbers import Number
from typing import List

from sopel.config.types import ValidatedAttribute  # type: ignore
from sopel.tools import get_logger  # type: ignore

log = get_logger('ctx_reminders')

class NumberAttribute(ValidatedAttribute):
    """
    A descriptor for numeric settings in a :class:`StaticSection`.

    :param str name: the attribute name to use in the config file
    """

    def __init__(self, name, default=None):
        super().__init__(name, default=default)

    def parse(self, value):
        """Check the supplied ``value`` against valid numeric options

        :param str value: the value loaded from the config file
        :return: the ``value``, if it is valid
        :rtype: str
        :raise ValueError: if ``value`` is not a numeric type
        """

        try:
            # attempt to convert to number type
            if "." in value:
                value_num = float(value)
            elif value == "inf":
                value_num = inf # math.inf (type: float)
            else:
                value_num = int(value)
            return value_num
        except ValueError as number_conversion_error:
            if isinstance(value, Number):
                return value

            val_err_message = f'Value {value} supplied in attribute "{self.name}" must be a number.'
            raise ValueError(val_err_message) from number_conversion_error

@dataclass(repr=True, eq=True, order=True)
class ContextualReminder():
    """
    An instance of an individual reminder
    """

    # pylint: disable=too-many-instance-attributes
    # The number is reasonable in this case.

    set_at: dt.datetime
    """ When the reminder was set in UTC """

    due_at: dt.datetime
    """ When the reminder is due to be notfied in UTC """

    nickname: str
    """ The nickname that needs to be reminded """

    channel: str
    """ The channel sender or private message"""

    message: str
    """ The message to pass on to the nickname """

    pastebin_url: str
    """ The pastebin url for this reminder """

    has_context: bool
    """ Flag that determines if there is additional context """

    context_lines: List[str]
    """ A list of strings that contains the context """

    def serialize(self):
        """
        Serializing method for contextual reminders
        """
        return {
            "set_at": self.set_at.isoformat(timespec="seconds"),
            "due_at": self.due_at.isoformat(timespec="seconds"),
            "nickname": self.nickname,
            "channel": self.channel,
            "message": self.message,
            "pastebin_url": self.pastebin_url,
            "has_context": self.has_context,
            "context_lines": self.context_lines,
        }
