import threading
import types
import importlib
import sys

# For now, None is always serialized as b''.
# TODO: introduce hook to make this more flexible.
# NOTE: all serialization must be at least one byte long so it can be
# differentiated from None.

# TODO: change all variables of type "field" to name "field"
#       rename all other variables called "field"
# TODO: Deal with None serialization properly.

class ValidationError(Exception):
    pass

def _encodium_get_locals(func):
    ret = None
    def tracer(frame, event, arg):
        nonlocal ret
        if event == 'return':
            ret = frame.f_locals.copy()
    # tracer is activated on next call, return or exception
    old_tracer = sys.getprofile()
    sys.setprofile(tracer)
    try:
        # trace the function call
        func()
    finally:
        # disable tracer and replace with old one
        sys.setprofile(old_tracer)
    return ret


class Field(object):
    _order = 0

    def __init__(self, **kwargs):
        # Give this instance a number, to restore ordering later.
        self._order = Field._order
        Field._order += 1

        if not hasattr(self, 'type'):

            class FieldInstance(object):

                def __init__(inner_self, *args, **kwargs):

                    # Add all the kwargs:
                    for key, value in kwargs.items():
                        setattr(inner_self, key, value)

                    # Add None for the fields that weren't set:
                    for key, field in self.get_fields():
                        if not hasattr(inner_self, key):
                            setattr(inner_self, key, None)

                    if hasattr(inner_self, 'init'):
                        inner_self.init()

                def serialize(inner_self):
                    return self.serialize(inner_self)

                def __eq__(inner_self, other):
                    if inner_self.__class__.__name__ != other.__class__.__name__:
                        return False
                    fields = self.get_fields()
                    for name, field in fields:
                        if getattr(inner_self, name) != getattr(other, name):
                            return False
                    return True

                def __setattr__(inner_self, key, value):
                    nonlocal self
                    fields = dict(self.get_fields())
                    if key in fields:
                        field = fields[key]
                        if value is None:
                            if callable(field.default):
                                value = field.default()
                            else:
                                value = field.default
                        try:
                            if value is None:
                                field.check_optional(value)
                            else:
                                field.check(value)
                                field.check_type(value)
                        except ValidationError as e:
                            # Prepend the key to the exception message
                            e.args = (key + " " + e.args[0],) + e.args[1:]
                            raise
                    inner_self.__dict__[key] = value


            self.type = type(self.__class__.__name__ + 'Instance',
                             (FieldInstance,),
                             dict(self.__class__.__dict__))

        # Add the REAL make (not a class function, instance function)

        def make(inner_self, _data=None, *args, **kwargs):
            if _data is not None:
                return inner_self.deserialize(_data)
            ret = self.type(*args, **kwargs)
            self.check(ret)
            self.check_optional(ret)
            self.check_type(ret)
            return ret

        self.make = types.MethodType(make, self)

        options = _encodium_get_locals(self.__class__.default_options)
        self.default = None
        self.optional = None
        for key, value in options.items():
            setattr(self, key, value)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def default_options():
        pass

    def check(self, instance):
        pass

    def check_optional(self, value):
        if not self.optional and value is None:
            raise ValidationError("cannot be None")

    def check_type(self, value):
        if value.__class__.__name__ != self.type.__name__:
            instance_type = value.__class__.__name__
            expected_type = self.type.__name__
            raise ValidationError("is of type " + instance_type + ", expected " + expected_type)

    def get_fields(self):
        # Default serialize is to go through each of the fields.
        if not hasattr(self.__class__, 'fields'):
            raise NotImplementedError(self.__class__.__name__ + " has no fields")
        fields = _encodium_get_locals(self.__class__.fields)
        ordered_fields = []
        for key, value in fields.items():
            if isinstance(value, Field):
                ordered_fields.append((value._order, key, value))
        ordered_fields.sort()
        return [(key, value) for _, key, value in ordered_fields]

    def serialize(self, value):
        def encode_length(length):
            encoded_length = length.to_bytes((length.bit_length()+7)>>3,'big')
            if length >= 0xfa:
                encoded_length_length = len(encoded_length)
                if encoded_length_length > 6:
                    raise ValidationError("length too big")
                encoded_length = bytes([encoded_length_length+0xf9]) + encoded_length
            return encoded_length

        array = [b'\x01']
        for key, field in self.get_fields():
            attr = getattr(value, key)
            if attr is None:
                array.append(b'\x00')
            else:
                data = field.serialize(attr)
                array.append(encode_length(len(data)))
                array.append(data)
        return b''.join(array)

    def deserialize(self, data):
        def decode_length(data, index=0):
            length = int.from_bytes(data[index:index+1],'big')
            length_length = 1
            if length >= 0xfa:
                length_length = 1 + (length-0xf9)
                length = int.from_bytes(data[index+1:index+1+(length-0xf9)],'big')
            # TODO: validation on decoded length
            return length, length_length
        i = 1
        array = []
        while i < len(data):
            length, length_length = decode_length(data, i)
            array.append(data[i+length_length:i+length_length+length])
            i += length_length + length
        kwargs = {}
        for (key, field), item in zip(self.get_fields(), array):
            if item is b'':
                kwargs[key] = None
            else:
                kwargs[key] = field.deserialize(item)
        return self.make(**kwargs)

    @classmethod
    def make(cls, *args, **kwargs):
        return cls().make(*args, **kwargs)


class String(Field):
    type = str
    def default_options():
        max_length = None
    def check(self, value):
        if self.max_length is not None and len(value) > self.max_length:
            raise ValidationError("too long")
    def serialize(self, s):
        # Pity about this, no easy way to store the empty string. :(
        return b'\x01' + s.encode('utf-8')
    def deserialize(self, data):
        return data[1:].decode('utf-8')

class Integer(Field):
    type = int
    def default_options():
        signed = True
    def serialize(self, i):
        bits=i.bit_length()
        if self.signed and i > 0 and bits%8==0:
            bits += 1
        return i.to_bytes(max((bits+7)>>3,1), 'big', signed=self.signed)
    def deserialize(self, data):
        return int.from_bytes(data, 'big', signed=self.signed)

class List(Field):
    type=list
    def __init__(self, inner_field, *args, **kwargs):
        self.inner_field = inner_field
        super().__init__(*args, **kwargs)

    def check_type(constraints, instances):
        if instances.__class__ != list:
            instances_type = instances.__class__.__name__
            raise ValidationError("is of type" + instances_type + ", expected list")
        for instance in instances:
            try:
                constraints.inner_field.check_type(instance)
            except ValidationError as e:
                e.args = ("inner element " + e.args[0],) + e.args[1:]
                raise
    def check(constraints, instances):
        for instance in instances:
            try:
                constraints.inner_field.check(instance)
            except ValidationError as e:
                e.args = ("inner element " + e.args[0],) + e.args[1:]
                raise
    def serialize(self, l):
        def encode_length(length):
            encoded_length = length.to_bytes((length.bit_length()+7)>>3,'big')
            if length >= 0xfa:
                encoded_length_length = len(encoded_length)
                if encoded_length_length > 6:
                    raise ValidationError("length too big")
                encoded_length = bytes([encoded_length_length+0xf9]) + encoded_length
            return encoded_length

        array = [b'\x01']
        for attr in l:
            if attr is None:
                array.append(b'\x00')
            else:
                data = self.inner_field.serialize(attr)
                array.append(encode_length(len(data)))
                array.append(data)
        return b''.join(array)

    def deserialize(self, data):
        def decode_length(data, index=0):
            length = int.from_bytes(data[index:index+1],'big')
            length_length = 1
            if length >= 0xfa:
                length_length = 1 + (length-0xf9)
                length = int.from_bytes(data[index+1:index+1+(length-0xf9)],'big')
            # TODO: validation on decoded length
            return length, length_length
        i = 1
        array = []
        while i < len(data):
            length, length_length = decode_length(data, i)
            array.append(self.inner_field.deserialize(data[i+length_length:i+length_length+length]))
            i += length_length + length
        return array

class Boolean(Field):
    type = bool
    def serialize(self, b):
        return (b'\x01' if b else b'\x00')
    def deserialize(self, data):
        return data == b'\x01'

class Bytes(Field):
    type = bytes
    def serialize(self, b):
        return b'\x01' + b
    def deserialize(self, data):
        return data[1:]
