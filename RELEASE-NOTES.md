# 0.8.1 — Calendar sync bugfix + Concept C layout

Calendar and Contacts refresh no longer depend on inbox loading. Google API quota pauses are separated by service. Queued Calendar refreshes survive an inbox sync error, and Calendar has an explicit refresh button.

# 0.8.0 — Concept C interface

- Integrated Mail / Calendar / People / Local drafts into the header, retaining the draggable workspace tabs and standalone windows.
- Flat icon command bar with tooltips, accessible labels, inexpensive hover fades and grouped actions.
- Cleaner sidebar, inbox, reader, calendar and shared surfaces, with a CMail Blue colour preset. Existing custom colours remain available.
- Settings → Inbox row style selects current-size cards (default) or compact single-line messages, independently of interface scale.
- Density selection is saved and updates recycled rows without rebuilding the docking workspace.
- Low-power rendering and all existing account, mail, calendar, folder, composer and AI controls retained.

# CMail 0.7.0

- Replaces the inbox ListBox with Gtk.ListView and a recycled-row factory. All cached conversations remain in the model, while GTK creates only a bounded set of row widgets around the viewport. Unchanged messages reuse model objects; refresh replaces only the changed range.
- Mailbox grouping and cache preparation run on the worker pool above 300 cached messages. Requests are coalesced and stale results from another account/folder/filter are discarded. Cached threads are loaded with one bulk query rather than one query per conversation.
- Sender photos/contact URLs are indexed once per preparation. Decoded avatars are downscaled to 96 pixels and reused in a bounded 256-entry texture cache.
- Low-power rendering is enabled by default, with a Settings toggle. Reduces shadows/gradients and reader animation, disables HTML hardware compositing/WebGL, and bounds long HTML bodies to 900 pixels with internal scrolling. Long plain text uses a 600-pixel native text viewport. The complete message remains accessible; disabling low-power mode restores full-height HTML and reader animation.
- Short plain-text emails use native GTK text instead of a WebKit browser. Collapsed thread bodies release their content. Removed HTML views stop loading, cancel pending sizing and disconnect their script/signal handlers.
- Preserves conversation folding, images/attachments, dates, reply caching, calendar actions and dockable panels. Selection opens on explicit row activation, avoiding focus-restoration opening the wrong thread after a model change.

Validation: 54 unit tests; a 10,000-message mailbox scrolling test (211 recycled row shells; unchanged refresh did not mutate model items; largest measured UI heartbeat gap about 0.3 seconds in the initial virtual-display run), long bounded HTML with hardware acceleration disabled, native plaintext, thread/image/attachment checks, optional full-height HTML and immediate replies, real mouse docking/pop-out/return, and UI-thread cleanup stress. Results do not establish performance on every integrated GPU or Wayland configuration.

# CMail 0.6.1

- Dock changes now reconcile existing GTK containers. Unchanged tab groups, split panes, floating windows and panel widgets remain mounted; a tab reorder does not unmount email WebKit views.
- Drops queue their layout change until GDK emits drag-end. The source tab and its drag surface remain intact through native drop processing.
- Dock previews are non-measuring drawing overlays. Pointer movement redraws a preview only when the target zone changes, without changing panel size requests. Drag icons contain only the panel name.
- Background inbox redraws, layout saves and routine cycle collection wait until dragging finishes.
- Adds a visible pop-out button beside each group's Layout menu. Select a workspace tab and click it to open a standalone desktop window. Closing that window returns its tabs to the main app.
- Adds the Python GTK Cairo binding to package dependencies for the drawing overlay.

Validation: 54 unit tests; actual mouse edge docking, pop-out and drag-back; dock lifecycle regression verifies delayed drop application and untouched-view mounting; split/return/reset checks. The virtual-display tests pass, but hardware/Wayland rendering performance remains unverified on the user's desktop.

# CMail 0.6.0

- Mail, Calendar, People and Drafts now occupy persistent dockable panels. Drag their panel tabs to a view edge for horizontal/vertical splits, onto another tab to group/reorder, or outside the app to detach into a window. A highlighted area previews docking.
- Each tab group has a Layout menu with pop-out, edge-docking, return-as-tab and Reset layout actions. Closing a pop-out returns its panels to the main window. Closing the main app saves all groups, dividers, active tabs and floating-window sizes for next launch. Window positions are controlled by the desktop compositor.
- Views share one account, cache and background worker pool. Moving a panel preserves its calendar date, email selection and reader widgets. Refreshing Mail continues to update its visible cache even when Calendar has focus. Calendar/contact refresh requests keep their target while queued.
- Startup opens the last account's saved mailbox immediately, before reconnecting. Demo content is used only when no saved live account is selected. Cached mail stays readable during offline/sign-in failures.
- Reader divider preferences are saved after a short debounce instead of committing on every drag movement. HTML sizing updates are coalesced; WebKit readers share one ephemeral network session. UI-thread cycle cleanup runs less frequently, with periodic full cleanup retained.

Validation: 54 unit tests; native cached-startup, panel split/pop-out/return/reset and restore checks; actual mouse tab dragging; resize/maximize checks; existing reader/reply/calendar and refresh/quota regressions. Tests use fictional messages and mocked providers. The resize heartbeat test's largest UI gap was approximately 0.3 seconds on the virtual X11 display; this does not verify every hardware/Wayland graphics configuration.

# CMail 0.5.2

- Custom colours and dark/light choice now have their own saved palette. Switching among built-in presets and back to Custom restores that palette. Editing a built-in preset seeds Custom from its complete current palette.
- Search moves from the window title bar to the mail toolbar. Message card gaps/padding are slightly tighter. Sidebar subtitle text has a minimum readable size and sufficient vertical space at 65%; group titles are larger than their folders.
- Removes the visible folder drag grips and three-dot menus. Drag folder rows directly and right-click for folder actions. Organise folders adds New folder, backed by Google label creation, Microsoft mail-folder creation or Gmail IMAP CREATE; demo folders persist too.
- Calendar agenda rows now show Edit and Delete buttons directly, with deletion confirmation.
- More and Organise folders use one standard dropdown arrow.
- Email images load automatically when opening mail. Settings → Load email images automatically can disable it; the manual load button then remains available. Executable email markup stays blocked.
- Minimal centred blue envelope on dark grey, with a thicker continuous curved stroke and a taller, narrower shape. The icon appears in the launcher, app header and sidebar; old star branding is removed.

Validation: 50 unit tests with mocked providers, native theme/folder/layout checks at 65% and 100%, local-fixture image loading and blocking checks, and existing productivity/thread checks. No real mailbox folders were created by testing.

# CMail 0.5.1

New scalable mail icon using midnight blue, periwinkle and a crimson notification accent to match Tokyonight-Dark and Colloid-Dark. Keeps the existing desktop icon identity for upgrade compatibility.

# CMail 0.5.0

- Rebrands the app and desktop launcher to CMail. The package replaces `aster-mail`; `cmail` launches it and the old command remains an alias. Existing cache directories, application identity and keyring entries are retained.
- Inbox starts at full width. Selecting a conversation opens the reader with a 240 ms sweep and a default quarter-width message list. Back to Inbox/Escape closes it; dragged proportions persist.
- HTML bodies grow to their full content height and react to image loads, wrapping and quoted-text expansion, within one outer conversation scroll. Trusted layout measurements run in an isolated WebKit script world; email markup scripts remain disabled and CSP blocks executable mail content.
- Sidebar folders have collapsible groups, custom local groups, hide/show controls, folder menus and drag/drop reordering or regrouping. Preferences are stored separately for each account.
- A successful Gmail OAuth send caches the confirmed reply immediately, with the real message/thread IDs and composed body. Later provider data replaces it without duplicate IDs. Ambiguous sends are never marked as sent; local cache failures cannot make an accepted send retryable.
- Edit/delete calendar appointments, with a deletion confirmation and persistent demo edits. Supports timed and all-day appointment payloads for Google and Microsoft. Recurring occurrences are edited individually; a series editor is not included.
- White text colour restored. Slimmer mail command bar adds contextual reply/forward/archive/delete actions and a More menu. Removes the empty-reader slogan.

Validation: 44 unit tests with mocked services; native thread/HTML, follow-up UI and existing regression checks on fictional data. No real account send or calendar mutation was performed by these tests.

# Aster Mail 0.4.0

- Saved interface scale control from 65% to 120%, including text, app CSS dimensions, sender avatars and HTML reader zoom. Default is 85%; compact spacing is enabled by default.
- Five editable dark theme presets: Crimson Orbit, Cyber Mint, Violet Circuit, Deep Space and Graphite. Presets update colour pickers; individual colours can still be customised.
- Click calendar dates for their agenda, click appointments for details, and use Whole month to view all cached appointments. New appointment forms prefill the selected date. Opening the live calendar requests a refresh.
- Compact formatting controls moved directly below the composer header. New messages, replies and forwards show them; the inbox remains clear when no composer is open.
- Settings moved to a gear at the bottom of the left icon rail. The rail stays available so Settings remains reachable.
- Retains 0.3.2 refresh/quota handling and 0.3.1 WebKit crash fix.

Validation: 39 automated tests plus native productivity, broad UI and HTML/thread tests passed with fictional data and mocked services. Calendar details are read-only; invitation acceptance and recurrence editing remain unsupported. Existing caches and credentials remain in use after upgrading.

# CMail 0.3.2

- Refresh button and F5 shortcut. Manual refresh during a running batch queues the next check.
- Automatic inbox checks target ten seconds while open, and run immediately after sign-in. Contacts/calendar are refreshed manually rather than re-downloaded on every automatic inbox check.
- Initial Gmail imports yield after one 25-message batch. Each refresh checks the recent inbox page first, so arriving mail is not held behind the full historical import. Already cached recent messages are not downloaded again.
- Status distinguishes new-mail checks from older-mail import progress. Google quota pauses show a retry countdown and suspend refresh requests until retry time.
- Retains 0.3.1 main-thread cleanup fix and 0.3.0 presentation changes.

Validation: 38 automated checks, native Refresh/queue/quota regression and existing native UI checks. Provider requests are mocked; ten seconds is a polling target, not a delivery guarantee. Google backoff or network delays can extend it. No hosted push service is included.

# CMail 0.3.1

Fixes a native abort when Python collects detached GTK/WebKit view cycles on a sync worker thread. Automatic cyclic collection is disabled while the app runs, and a periodic GTK main-loop callback collects cycles on the UI thread. Normal reference counting remains active. A new native stress test replaces HTML views while worker allocations run and verifies finalization happens on the main thread.

Upgrade with apt after closing CMail. Existing mail caches, credentials and preferences remain in use.

# CMail 0.3.0

- Gmail conversation rows and expandable message history, including sent replies when opened.
- Date and time in inbox previews; Pacific/Auckland display time with NZ daylight saving, adjustable in Settings.
- Gmail category filter for Primary, Promotions, Social, Updates and Forums.
- HTML mail rendering with grey background, custom Email HTML background colour, inline CID signature images and quoted-text disclosure. Remote images remain opt-in and scripts stay disabled.
- Centred sender avatars, contact photos where available, and attachment cards with filename, size and download action.
- Shared Gmail quota pacing and bounded backoff. Initial import progress is saved every 25 messages and resumes from completed batches.
- Removed Your workspace, Personal workspace, Your communication hub and Connected workspace labels.
- Saved Show AI features toggle hides ChatGPT, Assistant and API configuration, and closes an open Assistant window.

Quit the old app before upgrading. Install the new Debian package with apt. The existing local data directory and desktop keyring credentials remain in use. Opening cached mail does not require re-importing the whole inbox; new mail continues syncing while the app is open. Google can still require renewed consent or sign-in under its policies.

Validation: 36 automated checks and two native GTK smoke tests pass with fictional data and mocked provider calls. The real Gmail account is not used by these tests. HTML rendering needs gir1.2-webkit-6.0, included in the package dependencies.
