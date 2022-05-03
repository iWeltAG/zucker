.. _filtering:

Filtering results
=================

When constructing a :class:`~zucker.model.view.View` object, you can filter
results using a dictionary object in the format defined by Sugar (see the last
section on this page for more details on this approach). Since building this
object is cumbersome and not type-safe, Zucker provides a system to build these
queries for you. It works by using the existing fields you have defined in the
model.

For example, to search for contacts by their name, pass the following:

  >>> Contact.find(Contact.first_name == "Paul")

Some filters can also be inverted. The following examples will reveal contacts
not found through online research. Both these options are identical:

  >>> Contact.find(~(Contact.lead_source == "Online"))
  >>> Contact.find(Contact.lead_source != "Online")

To combine two or more filters, use logical AND and OR operators. For example:

  >>> Contact.find(
  ...       (Contact.lead_source == "Online")
  ...       | (Contact.email_opt_out == False)
  ... )

To produce an AND, you can also pass the filters directly to the ``.find()``
method:

  >>> Contact.find(
  ...       Contact.lead_source == "Marketing",
  ...       Contact.email_opt_out == True
  ... )

See the :ref:`complete field reference <fields>` for details on the individual
filtering methods you can use.

Internal representation
-----------------------

Internally, all these filters get compiled to the MongoDB-like query
dictionaries the Sugar backend accepts. In most cases, it is also possible to
directly provide an object like this instead of using the query-building API.
You may need to resort to doing this if the specific filtering feature isn't
implemented in Zucker yet.

The `Sugar Developer Guide`_ gives a more complete overview of this syntax. In
short, these objects are composed of keys which denote the field to be checked
and a corresponding value that field should have. This object can be passed when
creating views (for example when calling ``.find()`` on a module or when
filtering an existing view):

.. _Sugar Developer Guide: https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_9.0/Integration/Web_Services/REST_API/Endpoints/module_GET/#Filter_Expressions

  >>> Contact.find({
  ...    "lead_source": "Online",
  ...    "email_opt_out": True,
  ...    "phone_mobile": { "$starts": "+49" }
  ... })
  <filtered view on Contact>

Just like with the Zucker-built query objects, you can pass more than one which
will be AND-ed together. This will produce the same result as the last example:

  >>> Contact.find(
  ...    { "lead_source": "Online" },
  ...    { "email_opt_out": True },
  ...    { "phone_mobile": { "$starts": "+49" } }
  ... )
  <filtered view on Contact>

While it is entirely possible to write all queries directly like this, it is not
recommended because then you give up type safety. Instead, try to use the fields
directly as much as possible and only fall back to raw dictionaries where no
corresponding filter API from Zucker exists yet:

  >>> Contact.find(
  ...    Contact.lead_source == "Online",
  ...    Contact.email_opt_out == True,
  ...    { "phone_mobile": { "$starts": "+49" } }
  ... )
  <filtered view on Contact>
