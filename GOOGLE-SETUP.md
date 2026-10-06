# Connecting Gmail

Microsoft sign-in does not connect a Gmail mailbox. CMail offers two separate Google routes and keeps Microsoft sign-in available.

## Quick route: Gmail app password

This uses Gmail SMTP with two-step verification enabled. A Google API key is different and cannot authenticate to your inbox.

1. Keep Google two-step verification enabled.
2. Open [Google App passwords](https://myaccount.google.com/apppasswords). Create an app password named **CMail** if your account offers this option.
3. In CMail, open **Settings → Google / Gmail → Connect using a Gmail app password**.
4. Enter your Gmail address and the 16-letter app password, then **Connect Gmail**. Spaces in the password are accepted.
5. CMail verifies the login before saving the credential in the desktop keyring. Do not paste it into chat or use your ordinary Google password.

This route uses encrypted IMAP to read mail and SMTP to submit it. It supports mailbox folders, read/unread, stars, attachments, composing and recipient suggestions from cached mail. It does not import Google Contacts or connect Google Calendar. The local demo calendar remains a separate demonstration workspace; live Gmail calendar access needs the OAuth route below.

Some Google accounts do not offer app passwords, including certain managed accounts, Advanced Protection configurations and some two-step-verification configurations. Google can revoke app passwords, including after an account password change. If the app-password page is unavailable, use OAuth rather than disabling 2FA.

## Google browser sign-in: mail, calendar and contacts

1. In your own [Google Cloud project](https://console.cloud.google.com/), enable Gmail API. Enable Google Calendar API and People API if you want those services.
2. Configure Google Auth Platform branding, audience and data access. For a personal trial use External / Testing and add your own Gmail address as a test user.
3. Create an OAuth client of type **Desktop app**, then download its JSON. A Web application client or a simple API key is not suitable.
4. In CMail Settings select **Import Google OAuth JSON**. Credentials are stored in the desktop keyring; they are not copied into the mail database or source package.
5. Enable **Google Calendar** and/or **Google Contacts** if wanted, then choose **Sign in with Google**. Complete sign-in and grant the requested services in your browser.

Mail requests `gmail.modify`; optional services request `calendar.events` and `contacts`. OAuth uses a loopback callback and PKCE. If optional consent is declined, CMail does not assume permission was granted. Enable a new service and sign in again to grant it.

Google Testing-mode authorisations for these scopes can expire after seven days. Public distribution of a shared OAuth app needs a maintained registration and Google's applicable verification process; Gmail scopes can require additional review. The free source package does not include a universal Google registration.

## Check your first live connection

The development checks use mocks and fictional mail, not a real Gmail account. Check an incoming message, attachment, unread/star changes, and a message you choose to send to yourself. For OAuth also check contacts and a disposable appointment. If a send result is uncertain, check Gmail Sent before trying again; CMail blocks automatic retries.

Updates are checked every 10 seconds while CMail is open. There is no push service or always-running background daemon in this version.

References: [Google app passwords](https://support.google.com/accounts/answer/185833), [Gmail IMAP/SMTP](https://developers.google.com/workspace/gmail/imap/imap-smtp), [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [Gmail synchronisation](https://developers.google.com/workspace/gmail/api/guides/sync), [Google OAuth scopes](https://developers.google.com/workspace/gmail/api/auth/scopes).
