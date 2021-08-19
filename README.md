# sopel-contextualreminders

An improved reminder module that adds context for long-dated reminders.

## Requirements

Python version: ```>=3.7```

## Install

Link the plugin directory ```sopel-contextualreminders``` into the Sopel modules directory.

## Configure

Add the following configuration options to the sopel configuration file (default is ```default.cfg```)

```
[ctxreminders]

# Location of the reminder file that is used as persistent storage
# Convention is to use the configuration folder and call the file
# "<basename>.contextualreminders.json"
# Leave blank to use the bot home directory
#persistence_dir =

# Maximum and minimum durations on which to add context to the reminder,
# expressed in seconds.
#
# E.g. to add context to anything over 30 days, the duration
# should be 2592000 (86400 * 30)
#
# Defaults are:
#   context_capture_max_duration = inf
#   context_capture_min_duration = 2592000
context_capture_max_duration = inf
context_capture_min_duration = 2592000

# Number of lines of chat to capture as part of the context when a
# reminder is set within the capture duration.
context_capture_chat_lines = 20

# URL to your privatebin instance additional context can be displayed
# Not providing a privatebin_url will result in no additional context
# being captured with reminders or pasted
#privatebin_url =
```

## Migrate old reminders

Old reminders will be automatically migrated from the reminder database on bot startup.

