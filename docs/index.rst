Zucker
======

*Zucker* is a Python wrapper around Sugar's
`REST API <https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_11.0/Integration/Web_Services/REST_API/>`_.
The interface is loosely inspired by Django's ORM syntax. Zucker's main goal is
to abstract away Sugar's concepts as much as possible and enable a Pythonic,
type-safe way to interact with the CRM system.

A very basic example of how to use the library can be seen in the following
snippet. In a nutshell, you will need to do two things: define a module and
create a client. Module classes define any interactions that can be performed
on server-side records, including any fields that are present. This definition
should match the data model on the server. Once a model has been created, it
is used like this:

.. code-block:: python

  from zucker.synchronous import model, RequestsClient

  # This client will use the 'requests' module as an HTTP transport library. See
  # the documentation for other client options (including asynchronous ones).
  crm = RequestsClient("https://crm.example.com", "zucker", "password")

  # The data model defined here should match the one on the server - although
  # unneeded fields can be omitted.
  class Contact(crm.Module, api_name="Contacts"):
      lead_source = model.StringField()
      phone_work = model.StringField()

  # .find() returns a View, which is a lazyly-fetched construct that points to
  # some data on the server, similar to a cursor or queryset:
  contacts = Contact.find(Contact.lead_source == "Word of mouth")

  for contact in contacts:
    print(contact.phone_work)

Zucker is backend-agnostic, meaning you can use any (even your own) HTTP library
that is already integrated into you projects without requiring additional
dependencies when implementing Sugar CRM requests. We also ship native support
for asynchronous I/O. Here is the same code from above, but instead of using
`requests`_ it uses `aiohttp`_ as the underlying HTTP client:

.. _requests: https://docs.python-requests.org/en/latest/
.. _aiohttp: https://docs.aiohttp.org/en/stable/

.. code-block:: python

  import asyncio
  from zucker.asynchronous import model, AioClient

  # Same as above, only we now use an asynchronous client. This one uses aiohttp
  # as the backend.
  crm = AioClient("https://crm.example.com", "zucker", "password")

  class Contact(crm.Module, api_name="Contacts"):
      lead_source = model.StringField()
      phone_work = model.StringField()

  async def demo():
      contacts = Contact.find(Contact.lead_source == "Word of mouth")
      async for contact in contacts:
        print(contact.phone_work)

  asyncio.run(demo())

For a more in-depth guide into all these features, see the following
documentation pages:

.. toctree::
  :maxdepth: 2
  :caption: Guide

  client
  model
  views
  filters
  fields
