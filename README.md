# CMail

**Work in progress — experimental desktop software.** CMail is a free, open-source Linux mail client with a customizable interface, dockable workspaces, calendar, contacts, and optional writing assistance. Built with Python, GTK4, and libadwaita; licensed under MIT.

CMail is actively being developed. Performance, rendering, provider compatibility, and account setup still need work. Bugs and freezes may occur. Keep access to your provider's official mail app while trying it. CMail is independent software and is not affiliated with Microsoft, Google, or OpenAI.

Current experimental version: **0.8.1**.

## Features

- Gmail and Microsoft mail: inbox/folder browsing, composing, replies, reply-all, forwarding, archive, trash, unread state, and stars/flags.
- Conversation threads with collapsible messages, local date/time display, HTML formatting, inline images, and attachment downloads.
- Rich-text composer with bold, italic, underline, links, colours, recipient suggestions, and attachments. Local drafts and send-status tracking.
- Calendar month/day browsing, appointment creation, visible edit/delete actions, and all-day appointments through supported providers.
- Saved contacts and recipient autocomplete; access to a school/work directory depends on the provider and administrator permissions.
- Dockable Mail, Calendar, People, and Drafts tabs: split left/right/above/below, group/reorder tabs, detach into standalone desktop windows, and restore saved layouts.
- Themes, a persistent custom colour palette, interface scaling, compact spacing, column sizing, and controls to hide parts of the interface.
- Folder groups, drag/drop organisation, show/hide controls, and supported provider folder/label creation.
- Cached mail at startup, offline reading of loaded messages, manual refresh/F5, periodic checks while open, and provider quota/backoff handling.
- Recycled inbox rows, background processing for large mailboxes, bounded avatar textures, and low-power rendering enabled by default.
- Optional assistant for drafting/rewording emails and proposing calendar entries for review. Hide all AI features in Settings. The browser ChatGPT shortcut opens your own browser session; the in-app assistant requires your own OpenAI API key and separate API billing.

## Supported accounts

These integrations are implemented; they are not a guarantee that every account or organisation will permit access.

| Connection | Mail | Calendar / contacts | Setup |
| --- | --- | --- | --- |
| Gmail using Google OAuth | Yes | Optional, through Google APIs | Your own Google Desktop OAuth registration; enable the required APIs and permitted/test users |
| Gmail using an app password | Yes, through IMAP/SMTP | Use Google OAuth for these | Google two-step verification and an eligible app password |
| Outlook.com / Microsoft 365 using Microsoft Graph | Implemented | Implemented for permitted primary-calendar and contact access | Your own Microsoft Entra desktop app registration; organisational admin consent may be required |

A Gmail address used to sign into Microsoft does not make its Gmail mailbox available through Microsoft Graph. Use the Gmail connection for Gmail mail. School/work sign-in, MFA, consent, and device-compliance policies still apply.

Account setup guides: [Google / Gmail](GOOGLE-SETUP.md), [Microsoft](SETUP.md), [optional assistant](ASSISTANT.md).

## Install on Ubuntu

Ubuntu 24.04 and newer are the intended target, including Ubuntu 26 desktop. GTK **4.12+**, libadwaita, WebKitGTK **6.0**, Python **3.10+**, and a working desktop Secret Service/keyring are required. The package uses system libraries; package availability on other distributions has not been verified. No cross-distribution compatibility guarantee is made.

Download the [experimental CMail 0.8.1 Debian package](https://github.com/slayadapraya/CMail/releases/download/v0.8.1/cmail_0.8.1_all.deb). In the directory containing the download:

```bash
sudo apt update
sudo apt install ./cmail_0.8.1_all.deb
cmail
```

You can also launch **CMail** from your applications menu. Close an existing CMail instance before installing an update. Upgrades retain local account settings and caches.

A first launch offers fictional demo data until you connect an account in Settings. Demo messages are never sent. Once a live account has been saved, startup shows its cached mailbox and reconnects in the background.

### Run or build from source

```bash
git clone https://github.com/slayadapraya/CMail.git
cd CMail
sudo apt install python3 python3-gi python3-gi-cairo python3-requests \
  gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 \
  gir1.2-secret-1 gir1.2-webkit-6.0 gnome-keyring
bash run.sh
```

The source runner uses `/usr/bin/python3`, so Ubuntu's GTK bindings are available. To build the package locally:

```bash
bash build-package.sh ./cmail_0.8.1_all.deb
```

### Performance options

Leave **Settings → Low-power rendering** enabled initially. It reduces visual effects and animations and limits long HTML bodies to a scrollable rendering area. All message content remains accessible. Turning it off restores full-height HTML rendering, which can cost more memory and rendering time.

If freezes persist, close CMail and compare one launch using GTK's software fallback:

```bash
GSK_RENDERER=cairo cmail
```

This changes only that launch and can increase CPU work; it is not guaranteed to be faster. See the [GTK renderer documentation](https://docs.gtk.org/gtk4/running.html).

## Current limitations

- Experimental, with ongoing performance and reliability work. Automated/mock tests do not establish compatibility with every GPU, desktop compositor, or live account.
- One connected account at a time; no unified multi-account inbox yet.
- Periodic polling while the app is open, not guaranteed instant push delivery. No background mail service when closed; imports, throttling, and network conditions can delay updates.
- Your own OAuth registrations are required. No shared public registration or credentials are bundled. Google verification/test-user restrictions and Microsoft admin approval may apply.
- Not a complete Outlook/Gmail replacement: no PST import, shared-mailbox interface, rules editor, meeting-invitation/RSVP interface, recurring-series editor, remote mailbox search, or automatic app updates.
- Primary calendar/month view; Microsoft mail-folder browsing currently lists top-level folders. Contacts and directory suggestions depend on permission and account type.
- Current outgoing attachment limits: combined **2.5 MB for Microsoft**, **20 MB for Gmail**. Local drafts reference attachment files on your computer.
- HTML active content is stripped and sender colours are adapted to the reader. Exact provider-webmail rendering is not guaranteed. Remote images load by default; disable this in Settings if preferred.
- An accepted send request is not proof of delivery. Ambiguous sends are retained for review and are never automatically retried.

## Privacy

**This repository contains application source, synthetic test fixtures, and a package built from that source. It contains no real mailbox cache, account configuration, OAuth credentials, API keys, tokens, or personal screenshots.**

At runtime, mail requests go directly to the chosen provider. CMail has no application-owned mail relay. Optional assistant requests go directly to OpenAI when requested; selected-email/calendar context is opt-in. Loading remote email images contacts the sender's image servers and may expose that the message was opened.

Credentials are stored through the desktop keyring. Mail, contacts, calendar snapshots, settings, and drafts are cached locally under `~/.local/share/aster-mail/` for compatibility with earlier versions. The cache has restricted file permissions but **is not encrypted**. Signing out removes the stored credential and retains cached data. Do not commit this directory or include it in bug reports.

Please redact addresses, message content, OAuth files, tokens, and account identifiers before posting screenshots or logs. Report credential exposure privately rather than including the credential in a public issue.

## Development and testing

```bash
/usr/bin/python3 -m unittest discover -s tests -p 'test_*.py'
```

The current suite has 56 unit tests, plus native GTK checks for conversations, attachments/images, immediate replies, calendar editing, cached startup, dock layouts, actual tab dragging, and UI-thread cleanup. Tests use fictional data and mocked providers.

Native checks need a virtual display and Pillow:

```bash
sudo apt install xvfb xauth python3-pil xdotool
ASTER_DATA_DIR=/tmp/cmail-perf-test PYTHONPATH=. GDK_BACKEND=x11 \
  GSK_RENDERER=cairo GSETTINGS_BACKEND=memory \
  xvfb-run -a /usr/bin/python3 tests/smoke_performance.py
```

A synthetic 10,000-conversation run used 211 recycled row shells and measured a largest UI heartbeat gap of approximately 0.3 seconds on a virtual display. These figures are development evidence, not a performance promise for all PCs.

See [release notes](RELEASE-NOTES.md). Contributions and reproducible, redacted bug reports are welcome.

### Interface update (0.8.1)

Concept C introduces a flat icon toolbar, integrated header navigation, calmer surfaces and a CMail Blue preset. Settings → Inbox row style lets you retain current-sized message cards or switch to compact single-line rows. Interface scaling is independent; draggable dock tabs, panel splits and standalone windows remain supported.
