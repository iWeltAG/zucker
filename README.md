# <div style="text-align: center">Zucker</div>

[![Tests and style linting](https://github.com/iWeltAG/zucker/actions/workflows/commit_checks.yml/badge.svg)](https://github.com/iWeltAG/zucker/actions/workflows/commit_checks.yml)
![](https://img.shields.io/badge/python-3.7+-blue)

Zucker is a Python library for
[Sugar CRM](https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_11.2/)
with a simple, readable API. Features:

- No dependencies (except for an HTTP client of your choice)
- Native support for both synchronous and
  [asyncio](https://docs.python.org/3/library/asyncio.html) paradigms
- Schema introspection that extracts supported fields from a Sugar server to
  speed up development
- ORM-like feel that abstracts away details of the upstream API
- Fully type-checked (internal and external code)

To get started, have a look at the
[Documentation](https://iweltag.github.io/zucker/). If
you find that something is missing, feel free to open an issue.

## What does it look like?

First, connect to a Sugar server. Then you can define a model that matches what
you have on the backend (use the [introspection features](#) to speed up this
process!):

```python
from zucker import model, RequestsClient

crm = RequestsClient("https://crm.example.com", "zucker", "password")

class Contact(model.SyncModule, client=crm, api_name="Contacts"):
    lead_source = model.StringField()
    phone_work = model.StringField()


contacts = Contact.find(Contact.lead_source == "Word of mouth")
for contact in contacts:
    print(contact.phone_work)
print(",".join(contact.phone_work for contact in contacts[:3]))
```

Again, see the
[Documentation](https://iweltag.github.io/zucker/) for
more examples.

## License

[MIT](https://github.com/iWeltAG/zucker/blob/main/LICENSE)
