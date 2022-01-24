Connecting and using a client
=============================

.. currentmodule:: zucker.client.base

To connect to a running Sugar server, use one of the provided client classes.
These clients act as a middleware between some HTTP library and the other Zucker
components. That means that every client type uses a different underlying
transport library. You can use this to create your own client if you are already
using another requests library that isn't natively supported by Zucker yet.
Further, the client implementation will determine whether actions will be
synchronous or `asychronous`_. In general, all clients need to be initialized
with the URL of the server and a pair of OAuth credentials:

.. _asychronous: https://docs.python.org/3/library/asyncio.html

  >>> crm = SomeClient("https://sugar.local", "username", "password")

.. note::
  By default, this will connect using the ``zucker`` `API platform`_. Make sure
  to create it in the admin section on the server or provide another platform
  name using the ``client_platform`` parameter. See the constructor
  :meth:`~__init__` documentation for more
  parameters.

  .. _API platform: https://support.sugarcrm.com/Documentation/Sugar_Versions/11.1/Pro/Administration_Guide/Developer_Tools/#Configure_API_Platforms

See the bottom of this page for a full list of clients. Once the client has been
created, you can go ahead and :ref:`define a data model <defining-modules>` that
matches the server's. This will be the main way to use Zucker's ORM system.

Client API
----------

Clients are declared as follows. This is the definition of the base superclass
for all clients, synchronous and asynchronous:

.. autoclass:: BaseClient
   :special-members: __init__

.. currentmodule:: zucker.client.base.BaseClient

Closing
~~~~~~~

.. automethod:: zucker.client.base.BaseClient.close

  .. note::
    This method may be synchronous or asychronous, depending on the client.

Metadata
~~~~~~~~

The Metadata API yields information about the Sugar server's configuration and
data model. If you would like to query this API, you might also want to read
`this blog post`_ from Sugar. Since metadata fetching can take quite a while,
it needs to be initiated explicitly:

.. _this blog post: https://sugarclub.sugarcrm.com/dev-club/b/dev-blog/posts/3-tips-for-using-the-sugar-metadata-api

.. automethod:: zucker.client.base.BaseClient.fetch_metadata

  **Example.** Pass a list of metadata types that should be cached to this
  method:

    >>> crm.fetch_metadata("server_info", "full_module_list")
    >>> await async_crm.fetch_metadata("server_info")

  .. hint::
    Here is a non-exhaustive list of these type names:
    ``hidden_subpanels``,
    ``currencies``,
    ``module_tab_map``,
    ``labels``,
    ``ordered_labels``,
    ``config``,
    ``relationships``,
    ``server_info``,
    ``logo_url``,
    ``languages``,
    ``full_module_list``,
    ``modules``,
    ``modules_info``,
    ``fields``,
    ``filters``,
    ``views``,
    ``layouts``,
    ``datas``

Like :meth:`close`, this method may block or be awaitable, depending on the
client. The other following methods and properties (concerning server
metadata) only parse the information fetched here and are therefore
synchronous. In general, cached metadata entries can be retrieved like this:

.. automethod:: zucker.client.base.BaseClient.get_metadata_item

Parts of the metadata API are also exposed via their own properties:

.. autoproperty:: zucker.client.base.BaseClient.module_names
.. autoproperty:: zucker.client.base.BaseClient.server_info

Supported modules
~~~~~~~~~~~~~~~~~

Clients expose the list of all supported modules under the
:attr:`module_names` property:

  >>> crm.fetch_metadata("full_module_list")  # Otherwise an UnfetchedMetadataError is raised
  >>> list(crm.module_names)
  ["Leads", "Contacts", ...]

To check if a given module is supported, use the ``in`` operator:

  >>> "Contacts" in crm
  True
  >>> "NonexistentModule" in crm
  False

This call supports both modules names as strings as well as actual
:class:`~zucker.model.Module` classes.

Generic requests
~~~~~~~~~~~~~~~~

You can also use the client instance to perform generic authenticated HTTP
requests against the server:

.. automethod:: zucker.client.base.BaseClient.request

  .. note::
    Depending on the client implementation, this method will be synchronous or
    asynchronous.

The first request will cause the authentication flow to run. Use this property
if you need to check for that case:

.. autoproperty:: zucker.client.base.BaseClient.authenticated

Bundled clients
---------------

Zucker currently bundles two client implementations:

``RequestsClient`` (synchronous)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: zucker.RequestsClient

``AioClient`` (asynchronous)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: zucker.AioClient

Implementing your own client
----------------------------

If you are already using an HTTP library that isn't supported by Zucker yet,
you can write your own client. This isn't much work — you basically only need
to implement the :meth:`raw_request` method. Choose one of
:class:`~zucker.client.base.SyncClient` or
:class:`~zucker.client.base.AsyncClient` as the base class. As a reference, have
a look at the provided client implementations — they also inherit from the two
aforementioned base classes.

.. autoclass:: zucker.client.base.SyncClient

.. autoclass:: zucker.client.base.AsyncClient
