from encodium import Encodium, Integer, String, Boolean, List, Bytes, ValidationError
import unittest
import json


class Person(Encodium):
    age = Integer.Definition(non_negative=True)
    name = String.Definition(max_length=50)
    diabetic = Boolean.Definition(default=True)
    optional = Integer.Definition(optional=True)


class Party(Encodium):
    people = List.Definition(Person.Definition())


class City(Encodium):
    parties = List.Definition(Party.Definition())


class Dad(Person):
    puns = List.Definition(String.Definition())


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

    def test_optional(self):
        john = Person(age=25, name="John")


class TestNestedTypeChecker(unittest.TestCase):
    def test_nested_type_checker(self):
        City(parties=[Party(people=[Person(age=25, name="John")])])

        def invalid_case_1():
            City(parties=[Party(people=[Person(name="John")])])

        self.assertRaises(ValidationError, invalid_case_1)

        def invalid_case_2():
            City(parties=[Party(people=City(parties=[]))])

        self.assertRaises(ValidationError, invalid_case_2)


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


class TestJsonSendAndRecv(unittest.TestCase):
    def test_json_send_and_recv(self):
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
        self.assertEqual(json.loads(mocket.received), {'age': 25, 'name': 'John', 'diabetic': True, 'optional': None})


class TestInvalidJson(unittest.TestCase):
    def test_invalid_json(self):
        self.assertRaises(ValidationError, Person.from_json, 'invalid json')
        self.assertRaises(ValidationError, Person.from_json, '"not an object"')


class TestList(unittest.TestCase):
    def test_list(self):
        class City(Encodium):
            people = List.Definition(Person.Definition(), default=[])

        city = City()
        self.assertEqual(city.people, [])
        city = City(people=[Person(age=25, name='John')])
        self.assertEqual(city.people, [Person(age=25, name='John')])
        self.assertRaises(ValidationError, City, people=[1])
        self.assertRaises(ValidationError, City, people='Not a list')


class TestBytes(unittest.TestCase):
    class Nonce(Encodium):
        data = Bytes.Definition()

    def test_bytes(self):
        blob = (123456789123456789).to_bytes(8, 'big')
        nonce = TestBytes.Nonce(data=blob)
        self.assertEqual(nonce.data, blob)
        self.assertEqual(TestBytes.Nonce.from_json(nonce.to_json()), nonce)

    def test_invalid_base64(self):
        self.assertRaises(ValidationError, TestBytes.Nonce.from_json, '{"data":"invalid base 64"}')


class TestCallableDefault(unittest.TestCase):
    def test_callable_default(self):
        counter = 0

        def next_counter():
            nonlocal counter
            try:
                return counter
            finally:
                counter += 1

        class Nonce(Encodium):
            integer = Integer.Definition(default=next_counter)

        nonce = [Nonce() for _ in range(3)]
        [self.assertEqual(nonce[i].integer, i) for i in range(3)]


class TestInheritance(unittest.TestCase):
    def test_inheritance(self):
        dad = Dad(age=60, name='Paul', puns=[])
        self.assertTrue(hasattr(dad, 'age'))


class TestListSerialization(unittest.TestCase):
    def test_list_serialization(self):
        class NonStandardJsonEncoder(Encodium):
            byteslist = List.Definition(Bytes.Definition())

        non_standard_json_encoder = NonStandardJsonEncoder(byteslist=[b'test'])
        s = non_standard_json_encoder.to_json()
        self.assertEqual(NonStandardJsonEncoder.from_json(s), non_standard_json_encoder)


if __name__ == '__main__':
    unittest.main()
