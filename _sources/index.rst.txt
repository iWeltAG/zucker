Zucker
======

*Zucker* is a Python wrapper around Sugar's `REST API`_.
The interface is loosely inspired by Django's ORM syntax.
Zucker's main goal is to abstract away Sugar's concepts as much as possible
and enable a Pythonic, type-safe way to interact with the CRM system.

.. _REST API: https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_11.0/Integration/Web_Services/REST_API/

You can see a very basic example of how it works in the following snippet.
In a nutshell, you will need to do two things to interact with a CMR server:
First, define a client which will talk with the server.
Then, build a data model in Python that matches what you have on the backend --
for every Sugar module you want to use, create a class with the corresponding properties.
Once that is done, you can use access your records much like a list or another data structure:

.. code-block:: python

  from zucker import model, RequestsClient

  # This client will use the 'requests' module as an HTTP transport library.
  # There are more to choose from here!
  crm = RequestsClient("https://crm.example.com", "zucker", "password")

  # The data model defined here should match the one on the server - although
  # you don't need to include fields that you won't use.
  class Contact(model.SyncModule, client=crm, api_name="Contacts"):
      lead_source = model.StringField()
      phone_work = model.StringField()

  # .find() returns a View, which is a lazily-fetched construct that points to
  # some data on the server, similar to a cursor or queryset in other ORMs:
  contacts = Contact.find(Contact.lead_source == "Word of mouth")

  print("All contacts got by word of mouth:")
  for contact in contacts:
    print(contact.phone_work)

That's the gist to querying records.
Did we mention that Zucker comes without any dependencies?
The only thing you need to install is some HTTP transport library --
we ship support for `requests`_ and `aiohttp`_, but using other libraries is :ref:`possible as well <implementing_clients>`.

.. _requests: https://docs.python-requests.org/en/latest/
.. _aiohttp: https://docs.aiohttp.org/en/stable/

Zucker also includes native support for Asynchronous I/O.
That means it seamlessly integrates into existing software stacks, regardless of your concurrency model.
Here is the same code as above, but with an asynchronous stack:

.. code-block:: python

  import asyncio
  from zucker import model, AioClient

  # Same as before, only we now use an asynchronous client. This one uses
  # aiohttp as the backend.
  crm = AioClient("https://crm.example.com", "zucker", "password")

  class Contact(model.AsyncModule, client=crm, api_name="Contacts"):
      lead_source = model.StringField()
      phone_work = model.StringField()

  async def demo():
      contacts = Contact.find(Contact.lead_source == "Word of mouth")

      print("All contacts got by word of mouth:")
      async for contact in contacts:
        print(contact.phone_work)

  asyncio.run(demo())

For a more in-depth guide into all these features,
see the following documentation pages:

.. toctree::
  :maxdepth: 2
  :caption: Guide

  client
  model
  views
  filters
  fields
