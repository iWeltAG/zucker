Data model
==========

Most other Sugar clients return data queried from the server -- for example a
list of records -- more or less exactly as they receive it from the server.
That means that all fields from the server will be made available, without
further processing. While this has some benefits (like being able to quickly
evaluate the available data over a large number of modules), Zucker takes a
bit of a different approach.

In order to interact with records from the CRM system, you must first define a
*data model*. This is basically a one-to-one copy of the content structure
that the server defines into special Python classes, much like other ORM
libraries do. Once this definition has been created, these classes are used to
interact with the server. Using this approach has a number of benefits:

- Records are now rich Python objects which can have their own methods for
  further data processing, instead of plain dictionaries.
- Filtering statements can be expressed in a
  :ref:`more Pythonic way <filtering>`.
- The model can be validated against the current server schema, which ensures
  that we are always working against a known state.
- Support for static typing using the :mod:`typing` module.

.. _defining-modules:

Defining modules
----------------

To define a module, you need to create a subclass of Zucker's
:class:`~zucker.model.module.BaseModule` base class. This is done by using
either :class:`~zucker.model.SyncModule` or :class:`~zucker.model.AsyncModule`
as the superclass, depending on the client implementation. This type of module
is also referred to as a *bound* module because it is fixed to the client it is
initialized with. Inside your class, define fields with the same name as they
appear in the API:

.. code-block:: python

  from zucker import model

  crm = SomeClient(...)

  # Here, the 'Contact' module is bound to the 'crm' client:
  class Contact(model.SyncModule, client=crm, api_name="Contacts"):
      first_name = model.StringField()
      lead_source = model.StringField()
      phone_mobile = model.StringField()
      phone_work = model.StringField()
      email_opt_out = model.BooleanField()

If you in an asynchronous environment, use ``model.AsyncModule`` instead. Note
that it is not possible (and not supported) to mix synchronous models with
asynchronous clients or vice-versa.

Extending the model
~~~~~~~~~~~~~~~~~~~

Make sure to use the correct :ref:`field types <fields>`, depending on the
server's database schema. You don't need to recreate the entire model here,
either -- only defining the fields you will actually use is encouraged for two
reasons:

#. Changes to other parts of the data model won't impact your implementation
   if you are ignoring the fields (by not defining them).
#. Zucker will evaluate the list of fields you have defined and only fetch the
   relevant data, decreasing the total amount of bandwidth needed.

You can name the class whatever you want, but make sure the name in the generic
(square brackets) matches the name of the class. In case you are not using
Python :module:`typing`, you can also leave out the generic entirely.

If the class has a different name as the corresponding Sugar module, you need to
provide the latter as an `api_name` parameter. This will mostly be the case for
plural naming and Sugar and singular class names in Python models.

Since this module is a normal Python class, you can also define your own
methods, which will be available to use:

.. code-block:: python

  class Contact(...):
      ...

      @property
      def actual_phone(self) -> Optional[str]:
          return self.phone_mobile or self.phone_work or None

Now, all contact objects have a computed property ``actual_phone``, which will
refer to the first defined phone number.

Reusing models with multiple clients
------------------------------------

Having multiple clients can be beneficial if you are connecting to different CRM
servers at the same time. It may also occur that multiple projects need to
access the same Sugar instance. In order to minimize duplicate code, model
base classes can be created and used as additional superclasses when defining
a client-bound module. To aid with this pattern, Zucker provides an
:class:`~zucker.model.UnboundModule` class. As the name already implies, these
modules are referred to as *unbound* because they don't belong to a specific
client yet.

.. code-block:: python

  from zucker import model, RequestsClient, AioClient

  class BaseContact(model.UnboundModule):
      first_name = model.StringField()
      lead_source = model.StringField()
      phone_mobile = model.StringField()
      phone_work = model.StringField()

      @property
      def actual_phone(self) -> Optional[str]:
          return self.phone_mobile or self.phone_work or None

  alpha_crm = RequestsClient("https://alpha.example.com", "zucker", "password")
  beta_crm = AioClient("https://alpha.example.com", "zucker", "wordpass")

  class AlphaContact(model.SyncModule, BaseContact, client=alpha_crm, api_name="Contacts"):
    pass

  class BetaContact(model.AsyncModule, BaseContact, client=beta_crm, api_name="Contacts"):
      # This field will only be present on BetaContact instances:
      email_opt_out = model.BooleanField()

In the example above, contacts from the *alpha* CRM will be synchronous and
those from the other client will be asynchronous. This can be helpful when you
share the base models in multiple codebases.

API Reference
-------------

All bound modules define the following API. You don't need to implement the
abstract methods, as their implementation is already provided when you use the
synchronous or asynchronous modules as a superclass.

.. autoclass:: zucker.model.module.BoundModule
  :members:
  :special-members: __eq__
  :member-order: bysource

.. _codegen:

Using the code generation pipeline
----------------------------------

Instead of to manually defining modules, you can also make use of Zucker's code
generation system that will use Sugar's `metadata API`_ to find out which fields
are supported in the ORM.

.. _metadata API: https://sugarclub.sugarcrm.com/dev-club/b/dev-blog/posts/3-tips-for-using-the-sugar-metadata-api

.. note::
  Please remember that the code generated by these features should be treated as
  a guideline and may not be suitable for all cases (many fields aren't
  supported yet). Also note that this system is still under development.

Inspecting
~~~~~~~~~~

Before actually generating Python code, use the ``inspect`` command to narrow
down search results and find those you actually need. It works like this:

.. code-block:: shell

  python -m zucker.codegen -b "https://crm.example.com" -u "admin" -P inspect

This will output a list of all modules Zucker can find, with their corresponding
fields. See ``python -m zucker.codegen -h`` for more options.
