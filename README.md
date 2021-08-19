# sopel-contextualreminders

An improved reminder module that adds context for long-dated reminders.

## Requirements

Python version: ```>=3.7```
Sopel version: ```>=7.1.0```

## Install

TODO: publish on pypi


**Important: Disable** the bundled remind module by adding it to the core exclude section in the
```default.cfg``` file:

```
[core]
exclude =
    remind
```

### Dev Setup

Install the directory ```sopel-contextualreminders``` locally with pip and use the sopel-plugins
command to activate it.

While the minimum Python target version is 3.7, more recent versions are encouraged. Use of pyenv
is also encouraged.

Assuming an already existing directory ```./sopel-config``` that contains the default.cfg file

```
pyenv install 3.7.10 && pyenv virtualenv 3.7.10 sopel-contextualreminders
pyenv activate sopel-contextualreminders
git clone git@github.com:davidpirogov/sopel-contextualreminders.git ./sopel-contextualreminders
cd ./sopel-contextualreminders && pip install .
```

If you have not set up sopel bot yet, set up and enable the plugin. **Note**: If you use the
```--config-dir``` configuration option, you need to set the db_filename in the ```[core]```
configuration section, e.g. ```db_filename = default.db```

```
sopel-config init --config-dir ./sopel-config
sopel-plugins enable contextualreminders --config-dir ./sopel-config
sopel --config-dir ./sopel-config
```

## Configure

Add the following configuration options to the sopel configuration file (default is ```default.cfg```)

```
[ctxreminders]
# Location of the reminder file that is used as persistent storage
# Convention is to use the configuration folder and call the file
# "<basename>.contextualreminders.json"
# Leave blank to use the bot home directory
# persistence_dir =

# Maximum and minimum durations on which to add context to the reminder,
# expressed in seconds.
#
# E.g. to add context to anything over 10 days, the duration
# should be 864000 (86400 * 10)
#
# Defaults are:
#   context_capture_max_duration = inf
#   context_capture_min_duration = 864000
context_capture_max_duration = inf
context_capture_min_duration = 864000

# Number of lines of chat to capture as part of the context when a
# reminder is set within the capture duration.
context_capture_chat_lines = 20

# URL to your privatebin where additional context can be displayed
# Not providing a privatebin_url will result in no additional context
# being captured or displayed
#pastebin_url =

# Paste expiration timeframe in privatebin format
# Full details https://github.com/PrivateBin/PrivateBin/blob/master/cfg/conf.sample.php#L117-L125
# Default options are:
#   5min, 10min, 1hour, 1day, 1week, 1month, 1year, never
pastebin_expiration = 1year
```

## Migrate old reminders

Old reminders will be automatically migrated from the reminder database on bot startup.

