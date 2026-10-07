# CMail

A free, open-source Linux mail and calendar app built with Python, GTK4, and libadwaita. **Work in progress.**

## Features

- Gmail and Microsoft Outlook / Microsoft 365 accounts.
- Cached mail, conversation threads, HTML emails, attachments, and rich-text replies.
- Calendar viewing, event creation, editing, and deletion; contacts and address suggestions.
- Compact or card-style inbox, custom colours, scaling, and low-power rendering.
- Draggable tabs, split panels, and standalone windows.
- Optional writing assistant; AI controls can be hidden. API use requires your own key and may cost money.

## Install on Ubuntu

Download the `.deb` from [Releases](https://github.com/slayadapraya/CMail/releases/latest), close CMail, then run:

```bash
sudo apt install ./cmail_0.8.2_all.deb
cmail
```

Requires Python 3.10+, GTK 4.12+, libadwaita, and WebKitGTK 6.0. The package declares its dependencies.

## Account setup

- **Google:** [setup guide](GOOGLE-SETUP.md). OAuth supports mail, Calendar, and Contacts; a Gmail app password supports mail only.
- **Microsoft:** [setup guide](SETUP.md). Requires an Entra application registration. School/work accounts may require administrator approval.

## Current limitations

One connected account at a time. Mail refresh uses polling; Google quotas may pause syncing. Google Calendar currently loads the primary calendar. Some Outlook features are not implemented.

Tokens use the system keyring. Mail and event caches are stored locally under `~/.local/share/aster-mail` and are not encrypted. Remote email images can be disabled in Settings.

## Run from source

Install the dependencies listed in `build-package.sh`, then:

```bash
bash run.sh
```

Run unit tests with `python3 -m unittest discover -s tests`.

[Changelog](RELEASE-NOTES.md) · [Assistant setup](ASSISTANT.md) · [MIT license](LICENSE)
