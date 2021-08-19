"""
Configuration section for contextual reminders plugin
"""
import math

from sopel.config import Config  # type: ignore
from sopel.config.types import FilenameAttribute  # type: ignore
from sopel.config.types import StaticSection, ValidatedAttribute

from .types import NumberAttribute


class ContextualRemindersSection(StaticSection): # pylint: disable=too-few-public-methods
    """Defined in the ``[ctxreminders]`` config section """

    persistence_dir = FilenameAttribute(name="persistence_dir", relative=True, directory=True)
    """
    Folder to put the reminders file into. Default to the config"s homedir.
    This location is relative to the homedir and will be used to store the
    remind database file.

    The file itself will looks like ``<basename>.contextualreminders.json``.
    """

    context_capture_min_duration = NumberAttribute(
        name="context_capture_min_duration",
        # lower_bound=0,
        # upper_bound=math.inf,
        default=2592000)
    """
    Absolute duration which defines the lower bound of time for a reminder
    in which context capture is permitted.

    Default minimum period is any reminder duration that is >30 days (86400 * 30 = 2592000)
    """

    context_capture_max_duration = NumberAttribute(
        name="context_capture_max_duration",
        # lower_bound=0,
        # upper_bound=math.inf,
        default=math.inf)
    """
    Absolute duration which defines the upper bound of time for a reminder
    in which context capture is permitted.

    Default maximum period is any reminder duration
    """

    context_capture_chat_lines = NumberAttribute(
        name="context_capture_chat_lines",
        default=20
    )
    """
    Number of lines of chat to capture as part of the context when a reminder
    is set within the capture duration.

    Default capture lines is 20
    """

    pastebin_url = ValidatedAttribute(
        name="pastebin_url",
        default=""
    )
    """
    The privatebin URL used for pasting additional context

    Default is ""
    """

    pastebin_expiration = ValidatedAttribute(
        name="pastebin_expiration",
        default="5min"
    )
    """
    The expiration duration for pastes

    Default is 5min
    """


def initialize_bot_settings(settings: Config) -> Config:
    """
    Initialises the settings that are used within the bot to manage the contextual reminders
    """

    settings.define_section("ctxreminders", ContextualRemindersSection)

    settings.ctxreminders.configure_setting(
        "persistence_dir",
        "In which folder do you want to store the reminders file?",
        default=settings.core.homedir)

    settings.ctxreminders.configure_setting(
        "context_capture_min_duration",
        "What is the minimum duration (in seconds) for reminders to save contextual chat logs? " \
            "Default 30 days (2592000)",
        default=2592000)

    settings.ctxreminders.configure_setting(
        "context_capture_max_duration",
        "What is the minimum duration (in seconds) for reminders to save contextual chat logs? " \
            "Default no limit (inf)",
        default=math.inf)

    settings.ctxreminders.configure_setting(
        "context_capture_chat_lines",
        "How many lines of chat to save with reminders that have context? Default 20",
        default=20)

    settings.ctxreminders.configure_setting(
        "pastebin_url",
        "What is the pastebin url (PrivateBin)? Default ''",
        default=20)

    settings.ctxreminders.configure_setting(
        "pastebin_expiration",
        "Expiration of pastebin pastes? Default 5min",
        default="5min")

    return settings
