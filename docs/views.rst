Module views
============

Once a data model has been :ref:`defined <defining-modules>`, you can begin to
retrieve individual module instance from the server, which are called *records*.
The main way to do this is using the :meth:`~zucker.model.Module.find` method
directly on the module class:

  >>> Contact.find()
  <view on Contact>

What you get here is a :class:`~zucker.model.view.View`. Views point to a subset
of records in a module. They contain filtering information and may also be
refined using ranges (see below). An important thing to note here is that views
are lazy, which means that no data will be fetched until it is explicitly
requested. For example, a view doesn't know it's own length until ``len()`` is
called. Views can therefore be copied, modified and refined without actually
hitting the server.

.. note::
  If you're familiar with Django, you will find that a View is much like a
  `QuerySet`_, although the filtering syntax is a bit different.

  .. _QuerySet: https://docs.djangoproject.com/en/3.2/ref/models/querysets/

Basic view operations
---------------------

To get items out of a view, use the same syntax as with regular lists:

  >>> view = Contact.find()
  >>> view[4]
  <Contact object at ...>
  >>> list(view[2:6])
  [<Contact object at ...>, <Contact object at ...>, <Contact object at ...>, <Contact object at ...>]

.. hint::
  When using the asynchronous API, you will need to ``await`` all methods that
  (potentially) return record objects, including the array syntax. The example
  above would be:

    >>> await view[4]

  For the sake of brevity, the documentation will use the synchronous syntax.

These indexes adhere to whatever order the view is currently in. If you know
the ID of a record, you can also retrieve it directly:

  >>> view["17b245ae-b5d9-4b50-8bfb-32d8ce64c1f8"]
  <Contact object at ...>

Any objects you take out of a view this way will be of the
:class:`~zucker.model.Module` subtype that initially created the view. In this
case, you will receive ``Contact`` objects.

Alternative to the array syntax, you can also use the
:meth:`~zucker.model.view.View.get_by_index` or
:meth:`~zucker.model.view.View.get_by_id` methods.
Both raise errors (:exc:`IndexError` or :exc:`KeyError`) when no matching record is found.

Iteration
~~~~~~~~~

When iterating over a view, it will yield all records one by one:

  >>> for record in view:
  ...     # Do something

Views also support the :func:`reversed` protocol for iterating backwards:

  >>> for record in reversed(view):
  ...     # Do something

Slicing
~~~~~~~

While large views will only fetch necessary data when, it is also possible to
limit a view to a specific subset using the normal slice syntax. Here are some
typical examples:

  >>> view[4:] # Start with the fourth item
  >>> view[2:6] # Limit to items 2, 3, 4 and 5 (if present)
  >>> view[:20] # Return at most 20 entries

The step parameter is also supported, which makes a fully valid way to swap the
view's ordering. This is how :meth:`~zucker.model.view.View.reversed` is
implemented:

  >>> view[::-1] # Reverse the entire view order

Another use for the step option is to skip every n-th item (although this may
not be as efficient resource-wise because these requests are not batched):

  >>> view[::2] # Only return evenly-indexed items
  >>> view[2::3] # Skip until index 2, and from then take only every third item

When slicing like this, a new view is created. Since views are immutable, each
change will produce a new copy. This also means that slicing can be chained
with other calls:

  >>> new_view = view.reversed()[2:]
  >>> for record in view[:4]:
  ...     # Do something

Full API
--------

.. autoclass:: zucker.model.view.View
  :members:
  :member-order: bysource
