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

.. autoclass:: zucker.model.fields.base.MutableNumericField
  :members:
  :special-members: __lt__, __lte__, __gt__, __gte__
  :exclude-members: load_value, serialize

URLs
~~~~

URLs can be accessed with this field:

.. autoclass:: zucker.model.FloatField
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

IDs
~~~

Record IDs can be accessed using fields of this type:

.. autoclass:: zucker.model.IdField
  :members:
  :exclude-members: load_value, serialize

Relationships
-------------

Sugar offers a `number of ways`_ to model bidirectional data relationships.
The main way is by using *relationship links*.
Here, a link is defined between two module types and both models get a corresponding field.
In Zucker, use this field to access a link:

.. _number of ways: https://support.sugarcrm.com/Knowledge_Base/Studio_and_Module_Builder/Introduction_to_Relationships_and_Relate_Fields/

.. autoclass:: zucker.model.RelatedField
  :members:
