from encodium import Encodium, Integer, String, Boolean, ValidationError
import unittest
import json

class Person(Encodium):
    age = Integer.Definition(non_negative=True)
    name = String.Definition(max_length=50)
    diabetic = Boolean.Definition(default=True)


class TestTypeChecker(unittest.TestCase):
    def test_encodium_type(self):
        self.assertEqual(Person.Definition._encodium_type, Person)

    def test_raises_error_on_invalid_type(self):
        self.assertRaises(ValidationError, Person, age='not a number!', name='correct', diabetic=True)
        self.assertRaises(ValidationError, Person, age=10, name='correct', diabetic=['Not a bool'])
        self.assertRaises(ValidationError, Person, age=10, name=False, diabetic=True)

    def test_raises_error_on_non_optional_parameter(self):
        self.assertRaises(ValidationError, Person)
        self.assertRaises(ValidationError, Person, age=25)
        self.assertRaises(ValidationError, Person, name="No age provided    ")


class TestValueChecker(unittest.TestCase):
    def test_raises_error_on_negative_age(self):
        self.assertRaises(ValidationError, Person, age=-1, name="John")

    def test_raises_error_on_long_name(self):
        self.assertRaises(ValidationError, Person, age=25, name="Way Too Long" * 50)

    def test_works_for_valid_attributes(self):
        john = Person(age=25, name="John")


class TestEquality(unittest.TestCase):
    def test_equality(self):
        john = Person(age=25, name="John")
        john_twin = Person(age=25, name="John")
        self.assertEqual(john, john)
        self.assertEqual(john, john_twin)
        self.assertIsNot(john, john_twin)

    def test_inequality(self):
        john = Person(age=25, name="John")
        john_senior = Person(age=55, name="John")
        lucy = Person(age=25, name="Lucy")
        self.assertNotEqual(john, john_senior)
        self.assertNotEqual(john, lucy)


class TestJsonReader(unittest.TestCase):
    def test_json_reader(self):
        class Mocket:
            def __init__(self):
                self.data = '{ "age": 25, "name": "John", "diabetic": true }\n'
                self.counter = 0

            def recv(self, buffersize, flags=None):
                ret = self.data[self.counter:self.counter + buffersize]
                self.counter += len(ret)
                return ret

            def send(self, data):
                self.received = data

        mocket = Mocket()
        john = Person.recv_from(mocket)
        john.send_to(mocket)
        self.assertEqual(json.loads(mocket.received), {'age': 25, 'name': 'John', 'diabetic': True})


"""
    self.assertEqual(Person.make(person.serialize()), person)
    self.assertEqual(person.say_hello(), "Hello, I'm John")
    self.assertRaises(ValidationError, Person(allow_hat=False).make, name='John', hat='Fedora')
    person.age = 10

    def do_validation_error():
        person.is_dead = 12

    self.assertRaises(ValidationError, do_validation_error)
    person.is_dead = True
    person.privkey = b'1234'
    self.assertEqual(Person.make(person.serialize()), person)

    def do_validation_error():
        person.name = ('too long' * 30)

    self.assertRaises(ValidationError, do_validation_error)
    person.age = 123412341234123412341234
    self.assertEqual(Person.make(person.serialize()), person)
    other_person = Person.make(name="Alice")
    self.assertNotEqual(Person.make(person.serialize()), other_person)
    person.children = [other_person]
    self.assertEqual(Person.make(person.serialize()), person)
    self.assertNotEqual(Person.make(person.serialize()), None)


def test_big_bytes(self):
    class SporeMessage(Field):
        def fields():
            method = String(max_length=100)
            payload = Bytes()

    big = b'\x00' * 1024
    message = SporeMessage.make(method='hello', payload=big)
    self.assertEqual(message.payload, SporeMessage.make(message.serialize()).payload)

"""

if __name__ == '__main__':
    unittest.main()
