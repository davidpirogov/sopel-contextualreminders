"""
Contextual Reminders module - general services
"""

import datetime as dt
import json
import random
import re
import time
from pathlib import Path
from string import ascii_letters
from typing import Any, Dict, List, Tuple

import privatebinapi  # type: ignore
from sopel.bot import Sopel, Trigger  # type: ignore
from sopel.config import Config  # type: ignore
from sopel.tools import get_logger  # type: ignore

from .types import ContextualReminder

log = get_logger('ctx_reminders')

BOT_MEMORY_NAMESPACE = "sopel_contextualreminders"
IPV6_TIMEOUT_TRIGGER = 60  # seconds
PASTEBIN_API_DELAY = 10  # seconds, Privatebin API configuration for batch creation of pastes
PRETTY_JSON_INDENT = 4
PRETTY_TIMEFORMAT = "%Y-%m-%d %H:%M:%S"
TEMP_FILENAME_LEN = 12
UPCOMING_REMINDERS_WITH_CONTEXT_PASTEBIN_INTERVAL = 3600  # seconds

"""
Regex compatible with standard reminder module at
https://github.com/sopel-irc/sopel-remind/blob/master/sopel_remind/backend.py#L18-L27
"""
IN_TIME_PATTERN = '|'.join([
    r'(?P<days>(?:(\d+)d)(?:\s?(\d+)h)?(?:\s?(\d+)m)?(?:\s?(\d+)s)?)',
    r'(?P<hours>(?:(\d+)h)(?:\s?(\d+)m)?(?:\s?(\d+)s)?)',
    r'(?P<minutes>(?:(\d+)m)(?:\s?(\d+)s)?)',
    r'(?P<seconds>(?:(\d+)s))',
])

IN_ARGS_PATTERN = r'(?:' + IN_TIME_PATTERN + r')\s+(?P<text>\S+.*)'

IN_RE = re.compile(IN_ARGS_PATTERN)

def get_persistence_file(config: Config) -> Path:
    """
    Gets the path to the persistence file
    """

    return Path(f"{config.ctxreminders.persistence_dir or config.core.homedir}",
        f"{config.basename}.ctxreminders.json")

def load_reminders_from_persistence(persistence_file:Path) -> Dict[str, Any]:
    """
    Loads reminders from the persistence file and prepares them into a usable map
    """

    reminders: Dict[str, Any] = {}

    if not persistence_file.exists():
        log.info("Contextual reminders persistence file does not exist at '%s'. " \
            "Starting with empty reminders list.", persistence_file.absolute())

    else:
        log.info("Loading contextual reminders from persistence file configured at '%s'",
            persistence_file.absolute())

        with open(persistence_file, mode="r", encoding="utf-8") as persistence_file_handle:
            contents = json.load(persistence_file_handle)

        if "reminders" not in contents:
            log.warning("Cannot open the contextual reminders persistence file. " \
                        "It appears to be malformed or the JSON is not in a known format. " \
                        "Starting with an empty reminders list as a result.")

            return reminders

        num_reminders = 0
        for channel in contents["reminders"]:
            for data_reminder in contents["reminders"][channel]:
                if channel not in reminders:
                    reminders[channel] = []

                reminders[channel].append(ContextualReminder(
                    set_at= dt.datetime.fromisoformat(data_reminder["set_at"]),
                    due_at=dt.datetime.fromisoformat(data_reminder["due_at"]),
                    nickname=data_reminder["nickname"],
                    channel=data_reminder["channel"],
                    message=data_reminder["message"],
                    pastebin_url=data_reminder["pastebin_url"],
                    has_context=data_reminder["has_context"],
                    context_lines=data_reminder["context_lines"]
                ))
                num_reminders += 1

        log.info("Loaded %d channels and %d total reminders from the persistence file.",
            len(reminders), num_reminders)

    return reminders

def get_channel_from_sender(trigger: Trigger) -> str:
    """
    Gets an appropriately named channel from the sender, so as to ensure that contextual
    logs only get shown to the appropriate channel or private message.
    """

    channel=str(trigger.sender)
    if trigger.sender.is_nick():
        channel=f"PRIVMSG-{trigger.hostmask}"
        log.debug("Registering private message channel for %s as context name %s",
            str(trigger.sender), channel)

    return channel

def save_reminders_to_persistence(
    persistence_file: Path,
    reminders: List[ContextualReminder]) -> None:
    """
    Saves a List of reminders into a persistence file
    """

    # Write the output to a random file and move into the correct location
    output_file_path = get_temp_file_path(persistence_file, TEMP_FILENAME_LEN)
    output_data = {
        "reminders": reminders,
        "saved_at": dt.datetime.utcnow(),
        "version": 1
    }

    try:
        file_mode = "w"
        with open(output_file_path.absolute(), file_mode) as write_file:
            json.dump(
                output_data,
                fp=write_file,
                sort_keys=False,
                skipkeys=True,
                indent=PRETTY_JSON_INDENT,
                default=json_serialiser
            )

        output_file_path.replace(persistence_file)

    except OSError:
        log.error("Error while trying to save file '%s'",
            output_file_path.absolute(), exc_info=True)

        # Clean up our temporary file since there was an error in writing the output
        # We do not need to unlink on success because the file is replaced
        if output_file_path.exists():
            output_file_path.unlink()

def get_temp_file_path(persistence_file:Path, filename_len: int) -> Path:
    """
    Generates a temporary file path and returns the path
    """
    random_file_name = "".join(random.choice(ascii_letters) for i in range(filename_len))
    output_file_path = Path(persistence_file.parent, random_file_name)

    return output_file_path

def json_serialiser(obj) -> str:
    """ Serialises known types to their string versions """

    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()

    if isinstance(obj, ContextualReminder):
        return obj.serialize()

    raise TypeError("Type '{}' is not JSON serializable".format(type(obj)))

def setup(bot: Sopel) -> None:
    """
    Contextual Reminders setup and initialization methods
    """
    persistence_file = get_persistence_file(bot.settings)
    if not BOT_MEMORY_NAMESPACE in bot.memory:
        bot.memory[BOT_MEMORY_NAMESPACE] = {
            "reminders":{},
            "context_buffer":{}
        }

    bot.memory[BOT_MEMORY_NAMESPACE]["reminders"] = \
        load_reminders_from_persistence(persistence_file)

def shutdown(bot: Sopel):
    """
    Contextual Reminders teardown methods
    """
    trigger_save_persistence_file(bot)

    try:
        # Remove the contextual reminders namespace from the bot memory
        del bot.memory[BOT_MEMORY_NAMESPACE]
    except KeyError:
        pass

def trigger_save_persistence_file(bot: Sopel) -> None:
    """
    Triggers a saving of the bot namespace to the persistence file
    """
    persistence_file = get_persistence_file(bot.settings)
    save_reminders_to_persistence(persistence_file, bot.memory[BOT_MEMORY_NAMESPACE]["reminders"])

def parse_reminder_string(word_line: str) -> Tuple[dt.timedelta, str]:
    """
    Parses a reminder string into ``timedelta`` and ``str`` components
    """

    parse_result = IN_RE.match(word_line)

    if not parse_result:
        raise ValueError(f"Invalid arguments: {word_line}")

    groups = parse_result.groups()
    message = groups[-1]

    days, hours, minutes, seconds = 0, 0, 0, 0
    if groups[0]:
        days, hours, minutes, seconds = (int(i or 0) for i in groups[1:5])
    elif groups[5]:
        hours, minutes, seconds = (int(i or 0) for i in groups[6:9])
    elif groups[9]:
        minutes, seconds = (int(i or 0) for i in groups[10:12])
    else:
        seconds = int(groups[13] or 0)

    delta = dt.timedelta(
        days=days,
        seconds=seconds,
        minutes=minutes,
        hours=hours)

    return (delta, message)


def create_reminder(bot: Sopel, trigger: Trigger, time_delta: dt.timedelta,
    channel:str, message:str) -> ContextualReminder:
    """
    Creates a reminder object based on the supplied parameters
    """

    channel=trigger.sender
    if trigger.sender.is_nick():
        channel="PRIVMSG"

    reminder = ContextualReminder(
        set_at=trigger.time,
        due_at=trigger.time + time_delta,
        nickname=trigger.nick,
        channel=channel,
        message=message,
        pastebin_url="",
        has_context=False,
        context_lines=[]
    )

    conf_min_delta = bot.settings.ctxreminders.context_capture_min_duration or 0
    conf_max_delta = bot.settings.ctxreminders.context_capture_max_duration or 0

    if time_delta.total_seconds() >= conf_min_delta \
        and time_delta.total_seconds() <= conf_max_delta:
        snapshot_ts = dt.datetime.utcnow().strftime(PRETTY_TIMEFORMAT)
        reminder.has_context = True
        reminder.context_lines.append(f"Snapshot for {channel} created at {snapshot_ts} (UTC)")
        reminder.context_lines.append(
            "---------------------------------------------------------------")
        reminder.context_lines.extend(capture_context_snapshot(bot, channel))
        reminder.context_lines.append(
            "-----------------------------//--------------------------------")

    return reminder

def capture_context_snapshot(bot: Sopel, channel_name: str) -> List[str]:
    """
    Captures a snapshot of the current context buffer and returns as a list of strings
    """

    return bot.memory[BOT_MEMORY_NAMESPACE]["context_buffer"][channel_name]

def add_message_to_context_buffer(bot: Sopel, channel:str, message:str) -> None:
    """
    Adds a message to the context buffer and ensures that the buffer doesn't grow
    """

    maximum_buffer_lines = bot.settings.ctxreminders.context_capture_chat_lines

    if channel not in bot.memory[BOT_MEMORY_NAMESPACE]["context_buffer"]:
        bot.memory[BOT_MEMORY_NAMESPACE]["context_buffer"][channel] = []

    channel_messages_buffer: List[str] = bot.memory[BOT_MEMORY_NAMESPACE]["context_buffer"][channel]
    channel_messages_buffer.append(message)

    if len(channel_messages_buffer) > maximum_buffer_lines and len(channel_messages_buffer) >= 1:
        discard_message = channel_messages_buffer.pop(0)
        del discard_message


def persist(bot: Sopel, channel:str, reminder:ContextualReminder) -> None:
    """
    Adds the reminder to the appropriate file and saves all reminders
    """

    # NOTE
    # This is a potential slow spot if there are lots of reminders and channels
    # and should be upgraded to a more scalable and/or async persistence method
    persistence_file = get_persistence_file(bot.settings)

    if channel not in bot.memory[BOT_MEMORY_NAMESPACE]["reminders"]:
        bot.memory[BOT_MEMORY_NAMESPACE]["reminders"][channel] = []

    bot.memory[BOT_MEMORY_NAMESPACE]["reminders"][channel].append(reminder)
    save_reminders_to_persistence(persistence_file, bot.memory[BOT_MEMORY_NAMESPACE]["reminders"])

def get_active_reminders(bot: Sopel) -> Dict[str, List[ContextualReminder]]:
    """
    Gets the reminders currently active in the bot
    """
    return bot.memory[BOT_MEMORY_NAMESPACE]["reminders"]

def set_active_reminders(bot: Sopel, reminders: Dict[str, List[ContextualReminder]]) -> None:
    """
    Sets the active reminders that should be recorded
    """
    bot.memory[BOT_MEMORY_NAMESPACE]["reminders"] = reminders

def get_formatted_reminder_message(reminder: ContextualReminder) -> str:
    """
    Gets a formatted reminder message based on the supplied reminder
    """

    message = reminder.message
    if reminder.has_context and len(reminder.pastebin_url) > 0:
        message = f"{message} (More at {reminder.pastebin_url})"

    log.debug("Message prepared for sending %s", message)
    return message

def create_pastebin_url(bot: Sopel, reminder: ContextualReminder) -> str:
    """
    Creates a pastebin url for the reminder
    """

    log.debug("Getting privatebin config")
    pastebin_url = bot.settings.ctxreminders.pastebin_url
    pastebin_expiration = bot.settings.ctxreminders.pastebin_expiration

    log.debug("Privatebin URL: %s and Expiration: %s", pastebin_url, pastebin_expiration)

    log.debug("Creating pastebin")
    context_lines = "\n".join(reminder.context_lines)

    log.debug("Prepared context lines: \n%s", context_lines)
    paste_response = privatebinapi.send(
        pastebin_url,
        text=context_lines,
        password=None,
        proxies={},
        expiration=pastebin_expiration
        )

    if "full_url" not in paste_response:
        raise ValueError(f"Could not determine the pastebin url for reminder {reminder}. "\
            f"Response was {paste_response}")

    return paste_response['full_url']



def check_upcoming_reminders(bot: Sopel) -> Dict[str, List[ContextualReminder]]:
    """
    Checks the upcoming reminders and returns the reminders that:
        1) will be notifyable in the next UPCOMING_REMINDERS_WITH_CONTEXT_PASTEBIN_INTERVAL seconds
        2) have context
        3) do not have an existing pastebin URL
    """

    upcoming_reminders: Dict[str, List[ContextualReminder]] = {}

    active_reminders = get_active_reminders(bot)
    current_ts = dt.datetime.utcnow()
    for channel in active_reminders:
        for reminder in active_reminders[channel]:
            # Match on elapsing time to reminder (reminder_delta), has_context, & empty pastebin_url
            reminder_delta: dt.timedelta = reminder.due_at - current_ts
            if reminder_delta.total_seconds() < UPCOMING_REMINDERS_WITH_CONTEXT_PASTEBIN_INTERVAL \
                and reminder.has_context \
                and len(reminder.pastebin_url) == 0:

                if channel not in upcoming_reminders:
                    upcoming_reminders[channel] = []

                upcoming_reminders[channel].append(reminder)

    log.debug("There are %d pastebin entries upcoming in the next %d seconds that require " \
                "pastebin urls created for the entries.",
                len(upcoming_reminders), UPCOMING_REMINDERS_WITH_CONTEXT_PASTEBIN_INTERVAL)

    return upcoming_reminders


def create_pastebin_entries(bot: Sopel,
    upcoming_reminders: Dict[str, List[ContextualReminder]]) -> \
        Dict[str, List[ContextualReminder]]:
    """
    Loops through all the supplied upcoming reminders and creates individual
    pastebin entries for each one
    """
    if len(upcoming_reminders) == 0:
        return {}

    log.debug("Creating %d pastebin entries", len(upcoming_reminders))

    start_all_pastebin_ts = time.time()
    last_api_call_ts = 0.0
    for channel in upcoming_reminders:
        idx_reminder = 0
        for reminder in upcoming_reminders[channel]:
            # Only create pastebin urls for reminders that do not have pastebins
            if len(reminder.pastebin_url) == 0:
                log.debug(reminder)
                log.debug("Creating pastebin url for reminder based on the last API call")

                tentative_api_call_ts = time.time()
                last_api_call_delta_ts = tentative_api_call_ts - last_api_call_ts
                if PASTEBIN_API_DELAY > last_api_call_delta_ts:
                    sleep_delay_ts = PASTEBIN_API_DELAY - last_api_call_delta_ts
                    log.debug("Avoiding hitting the pastebin API too quickly. Last call was %d " \
                            "seconds ago and we need to wait %d seconds.",
                            last_api_call_delta_ts, sleep_delay_ts)

                    time.sleep(sleep_delay_ts)

                    log.debug("Waited a total of %d seconds. Proceeding to upload paste %d of %d " \
                        "in channel %s.", sleep_delay_ts, idx_reminder + 1,
                        len(upcoming_reminders[channel]), channel)

                start_individual_pastebin_ts = time.time()
                reminder.pastebin_url = create_pastebin_url(bot, reminder)
                idx_reminder += 1
                end_individual_pastebin_ts = time.time()
                last_api_call_ts = end_individual_pastebin_ts

                log.debug("Individual reminder %s took %d seconds", reminder.message,
                    end_individual_pastebin_ts - start_individual_pastebin_ts)

                paste_creation_ts = end_individual_pastebin_ts - start_individual_pastebin_ts
                if IPV6_TIMEOUT_TRIGGER < paste_creation_ts:
                    log.warning("Creating a paste took %d seconds. Check your IPv6/IPv4 config. " \
                        "Are you using an IPv4-only pastebin and trying to access it via IPv6?",
                        paste_creation_ts)


    end_all_pastebin_ts = time.time()
    log.debug("Total reminder took %d seconds", end_all_pastebin_ts - start_all_pastebin_ts)

    return upcoming_reminders

def update_reminders_pastebin_url(bot: Sopel,
    updated_reminders: Dict[str, List[ContextualReminder]]) -> None:
    """
    Receives a list of updated reminders and applies the pastebin URL and saves the list
    to persistence file
    """

    if len(updated_reminders) == 0:
        return

    active_reminders = get_active_reminders(bot)
    for channel in active_reminders:
        for reminder in active_reminders[channel]:
            if channel in updated_reminders:
                for updated_reminder in updated_reminders[channel]:
                    if reminder == updated_reminder:
                        reminder.pastebin_url = updated_reminder.pastebin_url
                        break

    set_active_reminders(bot, active_reminders)
    trigger_save_persistence_file(bot)
