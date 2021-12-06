.. _fields:

Field reference
===============

This page lists all the available field types to use in models.

.. hint::
  Some examples on this page return filter objects. These are be intended to be
  used when :ref:`filtering results <filtering>`, for example when calling
  :meth:`~zucker.model.module.BoundModule.find`.

Scalar fields
-------------

Scalar fields are used values where data from the Sugar backend can be directly
mapped to some Python equivalent without any side effects. That means that these
values can also be serialized and deserialized without using a model at all.
Further, scalar fields don't depend on any state or other records.

This field type is mainly used for primitive data types. All of them inherit
from this common base class and share a few options for filtering:

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

Relationships
-------------

