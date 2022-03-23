#!/usr/bin/env python3
#
# Copyright (C) 2021 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for mainline_modules_sdks.py."""
import re
from pathlib import Path
import os
import tempfile
import unittest
import zipfile
from unittest import mock

import mainline_modules_sdks as mm

MAINLINE_MODULES_BY_APEX = dict((m.apex, m) for m in mm.MAINLINE_MODULES)


class FakeSnapshotBuilder(mm.SnapshotBuilder):
    """A fake snapshot builder that does not run the build.

    This skips the whole build process and just creates some fake sdk
    modules.
    """

    @staticmethod
    def create_sdk_library_files(z, name):
        z.writestr(f"sdk_library/public/{name}-removed.txt", "")
        z.writestr(f"sdk_library/public/{name}.srcjar", "")
        z.writestr(f"sdk_library/public/{name}-stubs.jar", "")
        z.writestr(f"sdk_library/public/{name}.txt", "")

    def create_snapshot_file(self, name, version):
        zip_file = Path(self.get_sdk_path(name, version))
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("Android.bp", "")
            if name.endswith("-sdk"):
                self.create_sdk_library_files(z, re.sub(r"-.*$", "", name))

    def build_snapshots(self, build_release, sdk_versions, modules):
        # Create input file structure.
        sdks_out_dir = Path(self.get_mainline_sdks_path())
        sdks_out_dir.mkdir(parents=True, exist_ok=True)
        # Create a fake sdk zip file for each module.
        for module in modules:
            for sdk in module.sdks:
                for sdk_version in sdk_versions:
                    self.create_snapshot_file(sdk, sdk_version)


class TestProduceDist(unittest.TestCase):

    def test(self):
        """Verify the dist/mainline-sdks directory is populated correctly"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_out_dir = os.path.join(tmp_dir, "out")
            os.mkdir(tmp_out_dir)
            tmp_dist_dir = os.path.join(tmp_dir, "dist")
            os.mkdir(tmp_dist_dir)

            modules = [
                MAINLINE_MODULES_BY_APEX["com.android.art"],
                MAINLINE_MODULES_BY_APEX["com.android.ipsec"],
                # Create a google specific module.
                mm.aosp_to_google(MAINLINE_MODULES_BY_APEX["com.android.wifi"]),
            ]

            subprocess_runner = mm.SubprocessRunner()

            snapshot_builder = FakeSnapshotBuilder(
                subprocess_runner=subprocess_runner,
                out_dir=tmp_out_dir,
            )

            build_releases = [
                mm.Q,
                mm.R,
                mm.S,
                mm.LATEST,
                mm.LEGACY_BUILD_RELEASE,
            ]

            producer = mm.SdkDistProducer(
                subprocess_runner=subprocess_runner,
                snapshot_builder=snapshot_builder,
                dist_dir=tmp_dist_dir,
            )

            producer.produce_dist(modules, build_releases)

            files = []
            for abs_dir, _, filenames in os.walk(tmp_dist_dir):
                rel_dir = os.path.relpath(abs_dir, tmp_dist_dir)
                for f in filenames:
                    files.append(os.path.join(rel_dir, f))
            # pylint: disable=line-too-long
            self.assertEqual(
                [
                    # Legacy copy of the snapshots, for use by tools that don't support build specific snapshots.
                    "mainline-sdks/current/com.android.art/host-exports/art-module-host-exports-current.zip",
                    "mainline-sdks/current/com.android.art/sdk/art-module-sdk-current.zip",
                    "mainline-sdks/current/com.android.art/test-exports/art-module-test-exports-current.zip",
                    "mainline-sdks/current/com.android.ipsec/sdk/ipsec-module-sdk-current.zip",
                    "mainline-sdks/current/com.google.android.wifi/sdk/wifi-module-sdk-current.zip",
                    # Build specific snapshots.
                    "mainline-sdks/for-S-build/current/com.android.art/host-exports/art-module-host-exports-current.zip",
                    "mainline-sdks/for-S-build/current/com.android.art/sdk/art-module-sdk-current.zip",
                    "mainline-sdks/for-S-build/current/com.android.art/test-exports/art-module-test-exports-current.zip",
                    "mainline-sdks/for-S-build/current/com.android.ipsec/sdk/ipsec-module-sdk-current.zip",
                    "mainline-sdks/for-S-build/current/com.google.android.wifi/sdk/wifi-module-sdk-current.zip",
                    "mainline-sdks/for-latest-build/current/com.android.art/host-exports/art-module-host-exports-current.zip",
                    "mainline-sdks/for-latest-build/current/com.android.art/sdk/art-module-sdk-current.zip",
                    "mainline-sdks/for-latest-build/current/com.android.art/test-exports/art-module-test-exports-current.zip",
                    "mainline-sdks/for-latest-build/current/com.android.ipsec/sdk/ipsec-module-sdk-current.zip",
                    "mainline-sdks/for-latest-build/current/com.google.android.wifi/sdk/wifi-module-sdk-current.zip",
                    # Legacy stubs directory containing unpacked java_sdk_library artifacts.
                    "stubs/com.android.art/sdk_library/public/art-removed.txt",
                    "stubs/com.android.art/sdk_library/public/art-stubs.jar",
                    "stubs/com.android.art/sdk_library/public/art.srcjar",
                    "stubs/com.android.art/sdk_library/public/art.txt",
                    "stubs/com.android.ipsec/sdk_library/public/ipsec-removed.txt",
                    "stubs/com.android.ipsec/sdk_library/public/ipsec-stubs.jar",
                    "stubs/com.android.ipsec/sdk_library/public/ipsec.srcjar",
                    "stubs/com.android.ipsec/sdk_library/public/ipsec.txt",
                    "stubs/com.google.android.wifi/sdk_library/public/wifi-removed.txt",
                    "stubs/com.google.android.wifi/sdk_library/public/wifi-stubs.jar",
                    "stubs/com.google.android.wifi/sdk_library/public/wifi.srcjar",
                    "stubs/com.google.android.wifi/sdk_library/public/wifi.txt",
                ],
                sorted(files))


def path_to_test_data(relative_path):
    """Construct a path to a test data file.

    The relative_path is relative to the location of this file.
    """
    this_file = __file__
    # When running as a python_test_host (name=<x>) with an embedded launcher
    # the __file__ points to .../<x>/<x>.py but the .../<x> is not a directory
    # it is a binary with the launcher and the python file embedded inside. In
    # that case a test data file <rel> is at .../<x>_data/<rel>, not
    # .../<x>/<x>_data/<rel> so it is necessary to trim the base name (<x>.py)
    # from the file.
    if not os.path.isfile(this_file):
        this_file = os.path.dirname(this_file)
    # When the python file is at .../<x>.py (or in the case of an embedded
    # launcher at .../<x>/<x>.py) then the test data is at .../<x>_data/<rel>.
    this_file_without_ext, _ = os.path.splitext(this_file)
    return os.path.join(this_file_without_ext + "_data", relative_path)


def read_test_data(relative_path):
    with open(path_to_test_data(relative_path), "r", encoding="utf8") as f:
        return f.read()


class TestSoongConfigBoilerplateInserter(unittest.TestCase):

    def apply_transformations(self, src, transformations, expected):
        producer = mm.SdkDistProducer(
            subprocess_runner=mock.Mock(mm.SubprocessRunner),
            snapshot_builder=mock.Mock(mm.SnapshotBuilder),
            script=self._testMethodName,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "Android.bp")
            with open(path, "w", encoding="utf8") as f:
                f.write(src)

            mm.apply_transformations(producer, tmp_dir, transformations)

            with open(path, "r", encoding="utf8") as f:
                result = f.read()

        self.maxDiff = None
        self.assertEqual(expected, result)

    def test_common_mainline_module(self):
        """Tests the transformations applied to a common mainline module.

        This uses ipsec as an example of a common mainline module. This checks
        that the correct Soong config module types and variables are used and
        that it imports the definitions from the correct location.
        """
        src = read_test_data("ipsec_Android.bp.input")

        expected = read_test_data("ipsec_Android.bp.expected")

        module = MAINLINE_MODULES_BY_APEX["com.android.ipsec"]
        transformations = module.transformations()

        self.apply_transformations(src, transformations, expected)

    def test_art(self):
        """Tests the transformations applied to a the ART mainline module.

        The ART mainline module uses a different Soong config setup to the
        common mainline modules. This checks that the ART specific Soong config
        module types, variable and imports are used.
        """
        src = read_test_data("art_Android.bp.input")

        expected = read_test_data("art_Android.bp.expected")

        module = MAINLINE_MODULES_BY_APEX["com.android.art"]
        transformations = module.transformations()

        self.apply_transformations(src, transformations, expected)


class TestFilterModules(unittest.TestCase):

    def test_no_filter(self):
        modules = mm.filter_modules(mm.MAINLINE_MODULES)
        self.assertEqual(modules, mm.MAINLINE_MODULES)

    def test_with_filter(self):
        os.environ["TARGET_BUILD_APPS"] = "com.android.art"
        modules = mm.filter_modules(mm.MAINLINE_MODULES)
        expected = MAINLINE_MODULES_BY_APEX["com.android.art"]
        self.assertEqual(modules, [expected])


if __name__ == "__main__":
    unittest.main(verbosity=2)
