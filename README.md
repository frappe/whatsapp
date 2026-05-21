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

### Features Supported

- Creation of whatsapp template
- Sending whatsapp template and normal messages ( [under normal conversation window](https://github.com/ps173/frappe-whatsapp/blob/main/whatsapp/whatsapp) )

### Upcoming Features (Priority Order)

- Bulk Sending
- Catalog Upload + Catalog Based Templates
- Media messages (non template)
- Group management
- Calling features

### License

mit
