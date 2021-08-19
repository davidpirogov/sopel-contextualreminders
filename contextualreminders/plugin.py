"""
Contextual reminders plugin for Sopel IRC bot
"""
import datetime as dt
import threading
import time
from pathlib import Path
from typing import Dict, List

from sopel import plugin, tools  # type: ignore
from sopel.bot import Sopel, SopelWrapper  # type: ignore
from sopel.config import Config  # type: ignore
from sopel.trigger import Trigger  # type: ignore

from . import config, ctx_service
from .types import ContextualReminder

log = tools.get_logger('ctx_reminders')

BOT_MEMORY_LOCK = threading.RLock()
CHECK_UPCOMING_REMINDERS_WITH_CONTEXT_INTERVAL = 5  # 60 seconds
CHECK_REMINDER_JOBS_INTERVAL = 2  # seconds
MAX_MESSAGES_BOT_REPLY = 5


def setup(bot: SopelWrapper) -> None:
    """
    Setup for the plugin
    """
    bot.settings.define_section("ctxreminders", config.ContextualRemindersSection)
    ctx_service.setup(bot)

def shutdown(bot: SopelWrapper) -> None:
    """
    Shutdown for the plugin
    """
    ctx_service.shutdown(bot)


def configure(settings: Config) -> None:
    """
    Configuration for the plugin
    """

    settings = config.initialize_bot_settings(settings)

    if len(settings.remind.location) > 0:
        Path(settings.remind.location).mkdir(exist_ok=True)


@plugin.rule(r'.*')
def capture_message_in_buffer(bot: SopelWrapper, trigger: Trigger) -> None:
    """
    Captures relevant log messages and stores them in the correct context buffer
    """

    channel = ctx_service.get_channel_from_sender(trigger)

    # Record any op/voice/normal modifiers to the nick
    modifier = " "
    if channel in bot.channels:
        if bot.channels[channel].has_privilege(trigger.nick, plugin.ADMIN) or \
           bot.channels[channel].has_privilege(trigger.nick, plugin.OP) or \
           bot.channels[channel].has_privilege(trigger.nick, plugin.OPER):
            modifier = "@"

        elif bot.channels[channel].has_privilege(trigger.nick, plugin.VOICE):
            modifier = "+"

    # Record ACTION or CTCP as formatted messages
    if "intent" in trigger.tags:
        intent = trigger.tags["intent"]

        if intent == "ACTION":
            message = f"* {str(trigger.nick)} {trigger.plain}"
        else:
            message = f"CTCP query to {channel} from {str(trigger.nick)}: {intent}"

    else:
        message = f"<{modifier}{trigger.nick}> {trigger.plain}"

    formatted_timestamp = trigger.time.strftime(ctx_service.PRETTY_TIMEFORMAT)

    with BOT_MEMORY_LOCK:
        ctx_service.add_message_to_context_buffer(bot, channel,
            f"[{formatted_timestamp}] {message}")


@plugin.commands('in')
def reminder_in(bot: SopelWrapper, trigger: Trigger) -> None:
    """
    Trigger command for the bot to store a reminder
    """

    args = trigger.group(2)
    if args is None:
        bot.reply("Please specify when and what you would like to be reminded about")

    try:
        time_delta, message = ctx_service.parse_reminder_string(args)
    except ValueError:
        bot.say("Sorry, I didn't understand that")

    channel = ctx_service.get_channel_from_sender(trigger)
    reminder = ctx_service.create_reminder(bot, trigger, time_delta, channel, message)

    with BOT_MEMORY_LOCK:
        ctx_service.persist(bot, channel, reminder)

    ack_reminder_reponse_format = "I will remind you that {}"
    ack_reminder_reponse = ""
    if time_delta.days == 0:
        # Show just H:M:S
        ack_reminder_reponse = ack_reminder_reponse_format.format(
            f'at {reminder.due_at.strftime("%H:%M:%S")}')
    else:
        # Show full timestamp incl. day
        ack_reminder_reponse = ack_reminder_reponse_format.format(
            f'on {reminder.due_at.strftime("%Y-%m-%d")} at ' \
                f'{reminder.due_at.strftime("%H:%M:%S")} (UTC)'
        )

    bot.reply(ack_reminder_reponse)


@plugin.interval(CHECK_REMINDER_JOBS_INTERVAL)
def check_ctx_reminder_jobs(bot: Sopel) -> None:
    """
    Interval method to check reminders and notify people
    """

    if not bot.backend.connected or len(bot.channels) == 0:
        log.debug("Not running check_ctx_reminder_jobs due to bot not being connected " \
                  "or not yet joined any channels")
        return

    reminders_as_at = dt.datetime.utcnow()
    is_dirty = False
    with BOT_MEMORY_LOCK:
        active_reminders = ctx_service.get_active_reminders(bot)
        for channel in active_reminders:
            channel_reminders: List[ctx_service.ContextualReminder] = active_reminders[channel]
            for reminder in channel_reminders:
                if reminder.due_at < reminders_as_at and can_deliver_reminder(bot, reminder):
                    reminder_text = ctx_service.get_formatted_reminder_message(reminder)

                    if channel[0:7] == "PRIVMSG":
                        bot.say(reminder_text, reminder.nickname,
                            max_messages=MAX_MESSAGES_BOT_REPLY)
                    else:
                        bot.reply(reminder_text, channel, reminder.nickname)

                    is_dirty = True
                    active_reminders[channel].remove(reminder)

        if is_dirty:
            ctx_service.set_active_reminders(bot, active_reminders)
            ctx_service.trigger_save_persistence_file(bot)


def can_deliver_reminder(bot: Sopel, reminder: ContextualReminder) -> bool:
    """
    Checks to see if the nicknames are online and the reminder can be delivered
    """

    channel = reminder.channel
    if channel[0:7] == "PRIVMSG":
        # Match the hostname of the user in order to send them a private message
        user_hostmask = channel[8:]
        for user_key in bot.users:
            if user_hostmask == bot.users[user_key].hostmask:
                return True
    else:
        # Loop over the non-private messaging bot's channels and post the reminder there
        if channel in bot.channels:
            bot_channel = bot.channels[channel]
            if reminder.nickname in bot_channel.users:
                return True

    # User is not online in either privmsg or in a channel
    return False


@plugin.interval(CHECK_UPCOMING_REMINDERS_WITH_CONTEXT_INTERVAL)
def interval_check_upcoming_reminders(bot: Sopel) -> None:
    """
    Interval method to check reminders and notify people
    """

    if not bot.backend.connected or len(bot.channels) == 0:
        log.debug("Not running check_upcoming_reminders due to bot not being connected " \
                  "or not yet joined any channels")
        return

    start_ts = time.time()
    with BOT_MEMORY_LOCK:
        upcoming_reminders = ctx_service.check_upcoming_reminders(bot)

    if len(upcoming_reminders) == 0:
        # No upcoming reminders in the check horison
        return

    updated_reminders: Dict[str, List[ctx_service.ContextualReminder]] = \
        ctx_service.create_pastebin_entries(bot, upcoming_reminders)

    log.debug("There are %d reminders to update with new pastebin urls", len(updated_reminders))
    with BOT_MEMORY_LOCK:
        ctx_service.update_reminders_pastebin_url(bot, updated_reminders)

    end_ts = time.time()
    log.debug("Time taken to check upcoming reminders: %d seconds", end_ts - start_ts)
