'''

Encodium
========

Encodium is a simple serialization and validation library.

Getting started
---------------

Here's an example object to get you started::

    from encodium import Encodium, Integer, String, Boolean

    class Person(Encodium):
        age = Integer.Definition(non_negative=True)
        name = String.Definition(max_length=50)
        diabetic = Boolean.Definition(default=True)

And here's what it looks in use::

    # raises ValidationError("Age cannot be negative").
    impossible = Person(age=-1, name='Impossible')

    # raises ValidationError("Name must not be None").
    nameless = Person(age=25)

    # Works.
    john = Person(age=25, name='John', diabetic=False)

    # Does json.
    json_representation = john.to_json()
    new_john = Person.from_json(json_representation)

    # Can read in an object from a socket.
    foreign_person = Person.recv(sock)

    # Can send an object over a socket.
    john.send(sock)

Validation
----------

Most validation in Encodium is performed automatically by the ``Definition``
objects that are set as class variables. For example::

    from encodium import Encodium, Integer, String, Boolean

    class Person(Encodium):
        age = Integer.Definition(non_negative=True)
        hat = String.Definition(default="Fedora")

Each attribute is checked against it's definition when the ``Person`` is
created::

    john = Person(age=-1)

The following arguments are included by default:

* ``optional`` -- Whether or not the attribute is allowed to be None.
* ``default`` -- The default value to set the attribute to, if it is not
  provided.

Some examples::

    # Raises ValidationError("Age cannot be None")
    john = Person()

    # lucy.hat will be set to "Fedora"
    lucy = Person(age=25)

Type checking is also included automatically::

    john = Person(age="this is not an integer")

More complex validation can be done by defining ``check()`` on the object.

A useful paradigm when using encodium is to use the following invariant:
If the object exists, then it is valid.

Here's an example to illustrates this::

    from encodium import Encodium, Bytes, ValidationError
    import hashlib

    class DataSHA256(Encodium):
        data = Bytes.Definition()
        sha256sum = Bytes.Definition()

        def check(self, changed_attributes):
            if 'data' in changed_attributes:
                expected_hash = hashlib.sha256(self.data).digest()
            else:
                # The data hasn't changed, so the current hash is valid.
                expected_hash = self.sha256sum

            if self.hash != expected_hash:
                raise ValidationError('has an invalid hash')

Custom Constraints
------------------

Constraints can be implemented by defining ``check_value()`` on the type's
``Definition`` class, as thus::

    from encodium import Encodium, ValidationError

    class Integer(Encodium):
        class Definition(Encodium.Definition):
            _encodium_type = int
            non_negative = False

            def check_value(self, value):
                if self.non_negative and value < 0:
                    raise ValidationError("must not be negative")

Note that `_encodium_type` can be used to override the expected type.
Otherwise the class that `Definition` is nested inside will be used
automatically if it inherits from `Encodium`.

Recursive Definitions
---------------------

Not yet implemented.

Sometimes it's necessary to have recursive definitions.
However, python doesn't allow a class to reference itself during construction.

To overcome this, ``Encodium.Definition('ClassName', ...)`` may be used
instead of ``ClassName.Definition(...)``, as thus::

    from encodium import Encodium, String

    class Tree(Encodium):
        left = Encodium.Definition('Tree', optional=True)
        right = Encodium.Definition('Tree', optional=True)
        value = String.Definition()

Transmitting over a Socket
--------------------------

Here's an example::

    john = Person.recv_from(sock)
    john.send_to(sock)

The default encoding is JSON, but will have the option to specify alternative
encodings soon.

'''

import sys


class ValidationError(Exception):
    ''' Raise in the case of a validation error.
    Always in a form that can be appended to the name of a field.
    e.g. _____ "cannot be greater or equal to 10"
    '''
    pass


class Field:
    ''' This class included for backwards compatibility. '''

    def __init__(self, *args, **kwargs):
        ''' Displays an error message to stderr and raises an exception. '''
        msg = "Use of encodium.Field is Deprecated.\n"
        msg += "This change will break backwards compatibility\n"
        msg += "For a quickfix, change:\n"
        msg += "    from encodium import ___\n"
        msg += "to\n"
        msg += "    from encodium.deprecated import ___\n"
        sys.stderr.write(msg)
        raise Exception("Upgrade Encodium")


class EncodiumMeta(type):
    def __init__(cls, name, bases, dict):
        super().__init__(name, bases, dict)
        # If this is not the base class, create some useful variables.
        if name != 'Encodium':

            # Used for type checking.
            if not hasattr(cls.Definition, '_encodium_type'):
                cls.Definition._encodium_type = cls

            # Used to easily access the fields (can be overriden)
            if not hasattr(cls.Definition, '_encodium_fields'):
                cls._encodium_fields = []
                for key, value in dict.items():
                    if isinstance(value, Encodium.Definition):
                        cls._encodium_fields.append(key)


class Encodium(metaclass=EncodiumMeta):
    ''' This is the base class for all Encodium objects.
    '''

    class Definition:
        optional = False
        default = None

        def __init__(self, **kwargs):
            # Copy across kwargs.
            for key, value in kwargs.items():
                self.__dict__[key] = value

        def check_type(self, value):
            if not self.optional and value is None:
                raise ValidationError('cannot not be None')
            expected = self._encodium_type
            actual = value.__class__
            if not issubclass(actual, expected):
                message = 'is supposed to be type ' + str(expected)
                message += ', but was set to something of type ' + str(actual) + '.'
                raise ValidationError(message)

        def check_attribute(self, value):
            pass


    def __init__(self, *args, **kwargs):
        for field in self._encodium_fields:
            if field not in kwargs:
                definition = self.__class__.__dict__[field]
                kwargs[field] = definition.default

        self.change(**kwargs)

    def __eq__(self, other):
        if self.__class__ == other.__class__:
            for field in self._encodium_fields:
                if self.__dict__[field] != other.__dict__[field]:
                    return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def change(self, **kwargs):
        changed_attributes = {}
        for field, value in kwargs.items():
            if field not in self._encodium_fields:
                # TODO: decide how to handle this case.
                sys.stderr.write("Warning: Argument " + field +
                                 " provided but isn't a field for" +
                                 " Encodium type " + self.__class__.__name__)
            else:
                definition = self.__class__.__dict__[field]

                try:
                    definition.check_type(value)
                    if value is not None:
                        definition.check_value(value)
                    changed_attributes[field] = value
                except ValidationError as e:
                    # Prepend the name of the field to the exception message
                    e.args = (field + " " + e.args[0],) + e.args[1:]
                    raise

        backup = {}
        for field, value in changed_attributes.items():
            try:
                backup[field] = self.__dict__[field]
            except KeyError:
                backup[field] = None
            self.__dict__[field] = value

        try:
            self.check(changed_attributes.keys())
        except ValidationError as e:
            # Restore the backup before re-raising.
            for field, value in backup:
                self.__dict__[field] = value
            raise

    def check(self, changed_attributes):
        pass


class Integer(Encodium):
    class Definition(Encodium.Definition):
        _encodium_type = int
        non_negative = False

        def check_value(self, value):
            if self.non_negative and value < 0:
                raise ValidationError("must not be negative")


class String(Encodium):
    class Definition(Encodium.Definition):
        _encodium_type = str
        max_length = None

        def check_value(self, value):
            if self.max_length is not None and len(value) >= self.max_length:
                raise ValidationError("was set to a string of length " +
                                      str(len(value)) +
                                      " but cannot be longer than " +
                                      str(self.max_length))


class Boolean(Encodium):
    class Definition(Encodium.Definition):
        _encodium_type = bool

        def check_value(self, value):
            pass