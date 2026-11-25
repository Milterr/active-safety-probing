import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from asp.benchmark import dataset_sha256


class DatasetHashTests(unittest.TestCase):
    def test_hashes_use_lf_and_preserve_other_bytes(self):
        filenames = ("filesystem.json", "gold.json", "scenarios.json")
        text = '{\n  "name": "пример\\r\\n"\n}\n'.encode("utf-8")
        expected = dict.fromkeys(filenames, hashlib.sha256(text).hexdigest())

        with TemporaryDirectory() as temp:
            directory = Path(temp)
            for newline in (b"\n", b"\r\n", b"\r"):
                with self.subTest(newline=newline):
                    for name in filenames:
                        (directory / name).write_bytes(text.replace(b"\n", newline))
                    (directory / "other.json").write_bytes(b"{}")
                    self.assertEqual(dataset_sha256(directory), expected)


if __name__ == "__main__":
    unittest.main()
