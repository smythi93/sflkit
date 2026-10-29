"""Tests for the Defects4J runner helpers.

The full pipeline (checkout/compile/run) requires a local Defects4J + JDK 11 and
is exercised manually; here we cover the parts that do not need Defects4J:
per-file instrumentation with fallback, and JLib-call insertion.
"""

import json
import os
import shutil
import tempfile
import unittest

from sflkit.language.language import Language
from sflkit.runners.defects4j import instrument_directory
from sflkitlib.events import EventType


class InstrumentDirectoryTest(unittest.TestCase):
    VALID = (
        "public class Valid {\n"
        "    static int f(int x) { if (x > 0) { return x; } return 0; }\n"
        "}\n"
    )
    # not valid Java -> must be copied verbatim rather than crash the run
    BROKEN = "public class Broken { this is not java <<< }\n"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sflkit_d4j_")
        self.src = os.path.join(self.tmp, "src")
        self.dst = os.path.join(self.tmp, "dst")
        os.makedirs(os.path.join(self.src, "pkg"))
        with open(os.path.join(self.src, "pkg", "Valid.java"), "w") as fp:
            fp.write(self.VALID)
        with open(os.path.join(self.src, "pkg", "Broken.java"), "w") as fp:
            fp.write(self.BROKEN)
        # a non-source file must be copied through unchanged
        with open(os.path.join(self.src, "pkg", "data.txt"), "w") as fp:
            fp.write("resource")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_instrument_with_fallback(self):
        mapping = os.path.join(self.tmp, "mapping.json")
        instrumented, copied, events = instrument_directory(
            Language.JAVA,
            [EventType.LINE, EventType.BRANCH, EventType.FUNCTION_ENTER],
            self.src,
            self.dst,
            mapping,
        )
        self.assertEqual(1, instrumented)
        self.assertEqual(1, copied)
        self.assertGreater(len(events), 0)

        valid = open(os.path.join(self.dst, "pkg", "Valid.java")).read()
        self.assertIn("de.cispa.sflkitlib.JLib", valid)
        self.assertIn("addFunctionEnterEvent", valid)

        # the broken file is preserved verbatim (no instrumentation)
        broken = open(os.path.join(self.dst, "pkg", "Broken.java")).read()
        self.assertEqual(self.BROKEN, broken)
        self.assertNotIn("JLib", broken)

        # non-source files are copied through
        self.assertTrue(os.path.isfile(os.path.join(self.dst, "pkg", "data.txt")))

        # the mapping is written and matches the returned events
        with open(mapping) as fp:
            self.assertEqual(len(events), len(json.load(fp)))


if __name__ == "__main__":
    unittest.main()
