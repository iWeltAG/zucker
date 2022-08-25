.. _fields:

Field reference
===============

This page lists all the available field types to use in models.

.. hint::
  Some examples on this page return filter objects.
  These should be used when :ref:`filtering results <filtering>`,
  for example when calling :meth:`~zucker.model.module.BoundModule.find`.

Scalar fields
-------------

Scalar fields are used where values from the Sugar backend can be directly mapped to some Python equivalent without any side effects.
That means that these values can also be serialized and deserialized without using a model at all.
Further, scalar fields mostly don't depend on any state or other records.

This field type is mainly used for primitive data types.
All of them inherit from this common base class and share a few options for filtering:

.. autoclass:: zucker.model.fields.base.ScalarField
  :members:
  :special-members: __eq__, __ne__
  :exclude-members: load_value, serialize

Strings
~~~~~~~

For text data, use a string field:

.. autoclass:: zucker.model.StringField
  :members:
  :exclude-members: load_value, serialize

Booleans
~~~~~~~~

Boolean fields store either ``True`` or ``False``:

.. autoclass:: zucker.model.BooleanField
  :members:
  :exclude-members: load_value, serialize

Numbers
~~~~~~~

Depending on the type of number stored, use one of these two fields:

.. autoclass:: zucker.model.IntegerField
  :members:
  :exclude-members: load_value, serialize

.. autoclass:: zucker.model.FloatField
  :members:
  :exclude-members: load_value, serialize

Both of these fields share an API for filtering:

.. autoclass:: zucker.model.fields.base.NumericField
  :members:
  :special-members: __lt__, __lte__, __gt__, __gte__
  :exclude-members: load_value, serialize

URLs
~~~~

URLs can be accessed with this field:

.. autoclass:: zucker.model.URLField
  :members:
  :exclude-members: load_value, serialize

Emails
~~~~~~

Sugar exposes emails with two APIs: a legacy version and a new version.
The new version supports connecting any number of emails to a record and treats them like a link.
This also allows setting metadata on emails, for example to opt out of communication.
The legacy version exposes two fields ``email1`` and ``email2`` on the record which map to the first and second email provided through the first method.
See the `documentation`_ for more details.

.. _documentation: https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_11.2/Architecture/Email_Addresses/#REST_API

Zucker currently only supports the legacy API through this field:

.. autoclass:: zucker.model.LegacyEmailField
  :members:
  :exclude-members: load_value, serialize

  Normally, this field is used like this (with the second instance being optional):

  .. code-block:: python

    class Lead(model.UnboundModule):
        email1 = model.LegacyEmailField()
        email2 = model.LegacyEmailField()

Enumerations
~~~~~~~~~~~~

The Sugar Studio allows to define fields of a type called *Dropdown*.
This field type allows users to select exactly one out of a predefined set of values.
Zucker maps these fields to Python's :mod:`enum` types:

.. autoclass:: zucker.model.EnumField
  :members:
  :exclude-members: load_value, serialize

  Define an enum and use the field like this:

  .. code-block:: python

    import enum

    class LeadSource(enum.Enum):
      DEFAULT = ""
      OTHER = "Other"
      EXISTING_CUSTOMER = "Existing Customer"
      DIRECT_MAIL = "Direct Mail"
      COLD_CALL = "Cold Call"
      WORD_OF_MOUTH = "Word of mouth"
      # ...

    class Lead(model.UnboundModule):
        lead_source = model.EnumField(LeadSource)

  Again, note the ``DEFAULT`` field.

.. note::
  In the metadata API, Sugar represents these fields with the additional
  parameter ``options``. Other than that, enumerations are regular text fields.

IDs
~~~

Record IDs can be accessed using fields of this type:

.. autoclass:: zucker.model.IdField
  :members:
  :exclude-members: load_value, serialize

Note that modules automatically receive a field of this type with the name ``id``.

Relationships
-------------

Sugar offers a `number of ways`_ to model bidirectional data relationships.
The main way is by using *relationship links*.
Here, a link is defined between two module types and both models get a corresponding field.
In Zucker, use this field to access a link:

.. _number of ways: https://support.sugarcrm.com/Knowledge_Base/Studio_and_Module_Builder/Introduction_to_Relationships_and_Relate_Fields/

.. autoclass:: zucker.model.RelatedField
  :members:

Implementing fields
-------------------

Next to the already mentioned :class:`~zucker.model.fields.base.ScalarField` and :class:`~zucker.model.fields.base.NumericField`, there are also other base classes available to use when implementing custom field types.
In fact, most of the above scalar fields above actually implement the mutable variants:

.. autoclass:: zucker.model.fields.base.MutableScalarField
  :members:

.. autoclass:: zucker.model.fields.base.MutableNumericField
  :members:

A field being mutable means that when a field ``name`` is used on a ``Record`` record type, both of the following will work:

.. code-block:: python

    the_name = record.name  # Get the name of a record object
    record.name = "New Name"  # Set a new value

To implement a scalar field, choose and applicable superclass and override it.
Scalar fields require two generic arguments - native type and an API type.
The latter is the type of data the Sugar API returns for the field and should be a JSON type.
Normally, this will be one of the JSON-native scalars :class:`str`, :class:`int`, :class:`float` or :class:`bool`.
The native type may be the same, but can also be something different.
This is the rich Python type that the API response gets converted into.
A typical example here is for dates, which are typically encoded as strings and returned as native :class:`~datetime.datetime` objects.

To handle this conversion, you will need to implement these two methods on the new field class:

.. automethod:: zucker.model.fields.base.ScalarField.load_value
.. automethod:: zucker.model.fields.base.ScalarField.serialize

.. note::
  When setting the value of a mutable field, you can provide both the native as well as the API type.
  For a hypothetical ``BirdField`` field on a ``Zoo`` model, this would both be possible:

  >>> the_bird = zoo.bird
  >>> the_bird
  <Bird object at ...>
  >>> zoo.bird = the_bird  # Set the field value using the native data type
  >>> zoo.bird = "zazu"  # Set the field value using the API type (assuming birds serialize to strings)

  This is why the :meth:`~zucker.model.fields.base.ScalarField.serialize` takes both input types.

Numeric fields only have one generic argument, as the native and API types are assumed to be the same.
