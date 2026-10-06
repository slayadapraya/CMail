# Assistant and ChatGPT

**ChatGPT ↗** opens https://chatgpt.com in your default browser. If that browser already has a valid ChatGPT session, it can reuse it. Otherwise sign in there. CMail cannot inherit the sign-in or conversation from another application, and opening ChatGPT does not automatically give it access to CMail's mailbox or calendar.

**✦ Assistant** opens a single native pop-out window. This optional feature uses the OpenAI Responses API with your own key; API billing is separate from a ChatGPT subscription. Without a key, you can still use CMail's mail features and the browser shortcut.

1. Create an API key in [OpenAI Platform](https://platform.openai.com/api-keys) and configure API billing/limits there.
2. Enter the key in **Settings → Assistant → Save assistant key**. It is stored in your desktop keyring. Do not paste it into this chat.
3. The default API model is `gpt-5-mini`; you can set another Responses-compatible model supporting strict JSON schema in Settings when saving a key.
4. Open **✦ Assistant** and ask for a draft, rewrite or appointment proposal.
5. **Review email draft** opens the normal composer. You edit and press Send yourself. **Review appointment** opens a prefilled appointment form. You check the date, time and duration and press Create appointment yourself.

The assistant cannot send email or change the calendar on its own. Appointment creation uses the connected provider's primary calendar; Gmail app-password connections require Google OAuth for calendar access.

By default only your prompt and local current time are included. Checking **Include selected email and visible calendar context** explicitly includes the selected cached message and the calendar snapshots currently loaded in the app. Attachments and your whole inbox are not automatically included. Requests go directly to OpenAI; `store:false` is set. This flag does not promise zero retention under all API policies. Conversation history stays in memory until you clear it or close the assistant window. Generated drafts you open are saved locally through the normal draft mechanism.

The integration was tested with mocked API responses. No real OpenAI API call was made during development, and access, available models, quota and billing must be checked with your own API account.

References: [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create), [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [GPT-5 Mini](https://developers.openai.com/api/docs/models/gpt-5-mini), [API data controls](https://developers.openai.com/api/docs/guides/your-data).
