### Whatsapp

> [!WARNING]
> WIP 🚧: Not meant for use yet!

Official whatsapp integration for frappe crm

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app whatsapp
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/whatsapp
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### Features

- Receive incoming messages via Meta webhook (text, buttons, interactive, images, audio, documents, video, stickers)
- Auto-create WhatsApp Profiles for new contacts
- Send outgoing template and text messages
- Message status tracking (Sent, Delivered, Read, Failed)
- WhatsApp Template management (create, sync, push to Meta)
- Multiple WhatsApp Business Accounts
- 6 built-in Frappe Notifications (message received/sent/failed, status updated, template approved/rejected)
- Server Script hooks via standard Frappe lifecycle (after_insert, after_save, etc. on Whatsapp Message)

### Planned

- Bulk Sending
- Catalog Upload + Catalog Based Templates
- Group management
- Calling features
- Reaction support
- Attach field for outgoing media messages
- Auto-block profile after N consecutive failed messages

### License

mit
