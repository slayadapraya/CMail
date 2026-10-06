# Connecting CMail to Microsoft

## If your account is managed by your school

Your school controls two separate things:

1. Whether you can create an app registration in its Microsoft Entra tenant.
2. Whether your account may grant a third-party application access to school mail, contacts and calendars.

You may have permission for one but not the other. An app registered in a separate tenant can support school accounts, but it still needs the school's consent/access policy to allow it. Having a personal Outlook account does not automatically give you a tenant in which you can register this app. Microsoft's current registration guide lists an Azure account/subscription, a tenant and an appropriate role as prerequisites.

If **App registrations → New registration** is unavailable, or sign-in says **Need admin approval**, the next step is to ask school IT whether an independent mail client is permitted. A public app also needs a publisher/registration owner; the current app download contains no pre-registered client ID.

Suggested wording you can choose to send to IT:

> I'm trying a local Linux desktop mail client that accesses my mailbox through Microsoft Graph using delegated permissions and browser-based OAuth with PKCE. It stores refresh credentials in the desktop keyring and does not use an external mail-processing server. Does the school permit this type of client? If so, could you provide or approve an app registration for a limited trial? I understand school MFA and sign-in policies still apply.


## Register an application

These steps are for you or an authorised registration owner/IT administrator who already has the required Entra access.

1. Open the [Microsoft Entra admin centre](https://entra.microsoft.com/).
2. Navigate to **Entra ID → App registrations → New registration**.
3. Name the app **CMail**.
4. For a shared/public client, choose **Accounts in any organisational directory and personal Microsoft accounts**. For a school-owned trial, IT may choose a single-tenant app instead.
5. Under **Authentication**, add **Mobile and desktop applications** and register **`http://localhost`** as the redirect URI. The app binds its callback listener only to the local loopback address and uses a temporary port. Use the desktop/public-client platform, not the Web platform. No client secret is required. PKCE is used for the authorization code flow; device code/password flows are not used.
6. Add the following **Microsoft Graph delegated permissions** (not application permissions):

   | Permission | Purpose |
   |---|---|
   | `User.Read` | Read your basic profile and separate account caches |
   | `Mail.ReadWrite` | Read/update mail, prepare drafts, archive and move messages |
   | `Mail.Send` | Submit mail from your account |
   | `Contacts.ReadWrite` | Synchronise and create saved contacts |
   | `Calendars.ReadWrite` | Read calendar events and create appointments |
   | `People.Read` | Request recipient suggestions through Microsoft people search |

   The sign-in request also includes `openid`, `profile` and `offline_access`, allowing identity sign-in and refresh-token issuance.
7. Follow any school requirement for administrator consent. These delegated scopes are not permission to bypass school policy or access arbitrary users' mailboxes.
8. Copy the **Application (client) ID** from the app's Overview page.
9. Open CMail **Settings**, paste the client ID and set the tenant:
   - **`common`** for a multitenant app that supports organisational and personal accounts.
   - The school's **Directory (tenant) ID** for a school-owned single-tenant app.
10. Choose **Sign in with Microsoft**, sign in to the intended account, and complete any permission/2FA prompt. Return to the app and check that the banner shows your actual account.

Do not enter your password, client secret, refresh token or 2FA code into chat or into CMail's settings. The Application (client) ID and Directory (tenant) ID are identifiers, not credentials.

## Your fortnightly 2FA prompt

The app refreshes short-lived access credentials silently using a refresh token while Microsoft permits it. Refresh tokens do not override Conditional Access sign-in frequency, revocation or device requirements.

When fresh authentication is needed:

- Live synchronisation pauses.
- A **SIGN-IN NEEDED** banner and **Reconnect** button appear.
- Cached messages and local drafts remain available.
- You reconnect in the browser and complete the school's authentication flow.
- After a successful sign-in, the app resumes synchronisation.

The app does not automatically send queued drafts after reconnecting. Uncertain send results need checking in Outlook Sent Items before sending again.

If your school requires a compliant device, approved client, special claims challenge or other control this client does not support, it may not connect. IT can confirm the applicable policy. The first version has not been validated against these policy combinations.

## First live-account check

After permission is granted, check incoming sync, a harmless message you choose to send to yourself, archive/unread changes, contact suggestions and a test appointment. Keep Outlook on the web available while validating. No live mail has been sent by the development tests.

## Troubleshooting

- **Need admin approval / app blocked:** school consent policy; check with IT.
- **Application not found:** wrong client ID, tenant setting or supported account types.
- **Redirect URI mismatch:** register `http://localhost` under Mobile and desktop applications, using the exact documented desktop setup.
- **Keyring unavailable:** unlock the Ubuntu login keyring or enable a desktop Secret Service provider. CMail refuses to store refresh credentials in plain text.
- **Sync paused / network error:** cached content remains available; the app checks again while open. Microsoft throttling waits for the requested backoff period.
- **Send result unknown:** check Sent Items in Outlook before doing anything that could resend that message. The app retains the local send record and blocks automatic retry.
- **No school directory suggestions:** saved contacts can still work. People-search permission, account type or school access rules may limit online results.

## Microsoft reference documentation

- [Register an application and prerequisites](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app)
- [Desktop sign-in setup](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-desktop-app-sign-in)
- [Redirect URI requirements](https://learn.microsoft.com/en-us/entra/identity-platform/reply-url)
- [Configure application consent](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent)
- [Sign-in frequency and session policies](https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-session-lifetime)
- [Microsoft Graph permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [People search](https://learn.microsoft.com/en-us/graph/search-concept-person)
