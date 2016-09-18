import os
import unittest

import pyinsane


class TestSaneGetDevices(unittest.TestCase):
    module = None

    def set_module(self, module):
        self.module = module

    def setUp(self):
        if self.module is None:
            pyinsane.init()
            self.module = pyinsane

    def test_get_devices(self):
        devices = self.module.get_devices()
        if len(devices) == 0:
            # if there are no devices found, create a virtual device.
            # see sane-test(5) and /etc/sane.d/test.conf
            self.module.Scanner("test")._open()
            devices = self.module.get_devices()
        self.assertTrue(len(devices) > 0)

    def tearDown(self):
        pass


class TestSaneOptions(unittest.TestCase):
    module = None

    def set_module(self, module):
        self.module = module

    def setUp(self):
        if self.module is None:
            pyinsane.init()
            self.module = pyinsane
        self.devices = self.module.get_devices()
        self.assertTrue(len(self.devices) > 0)

    def test_get_option(self):
        for dev in self.devices:
            for (k, v) in dev.options.items():
                if v.capabilities.is_active():
                    self.assertNotEqual(v.value, None)
                else:
                    self.assertRaises(pyinsane.PyinsaneException, lambda: v.value)

    def test_set_option(self):
        for dev in self.devices:
            dev.options['mode'].value = "Gray"
            val = dev.options['mode'].value
            self.assertEqual(val, "Gray")

    def __set_opt(self, dev, opt_name, opt_val):
        dev.options[opt_name].value = opt_val

    def test_set_inexisting_option(self):
        for dev in self.devices:
            self.assertRaises(KeyError, self.__set_opt, dev, 'xyz', "Gray")

    def test_set_invalid_value(self):
        for dev in self.devices:
            self.assertRaises(pyinsane.PyinsaneException, self.__set_opt, dev, 'mode', "XYZ")

    def test_set_inactive_option(self):
        for dev in self.devices:
            noncolor = [x for x in dev.options["mode"].constraint if x != "Color"]
            if len(noncolor) == 0:
                self.skipTest("scanner does not support required option")
            if not "three-pass" in dev.options.keys():
                self.skipTest("scanner does not support option 'three-pass'")
            dev.options["mode"].value = noncolor[0]
            # three-pass mode is only active in color mode
            self.assertRaises(pyinsane.PyinsaneException, self.__set_opt, dev, 'three-pass', 1)

    def tearDown(self):
        for dev in self.devices:
            del(dev)
        del(self.devices)


class TestSaneScan(unittest.TestCase):
    module = None

    def set_module(self, module):
        self.module = module

    def setUp(self):
        if self.module is None:
            pyinsane.init()
            self.module = pyinsane
        devices = self.module.get_devices()
        self.assertTrue(len(devices) > 0)
        self.dev = devices[0]

    def test_simple_scan_lineart(self):
        try:
            self.dev.options['mode'].value = "Lineart"
        except pyinsane.PyinsaneException:
            self.dev.options['mode'].value = "Gray"
            self.dev.options['depth'].value = 1
        scan_session = self.dev.scan(multiple=False)
        try:
            assert(scan_session.scan is not None)
            while True:
                scan_session.scan.read()
        except EOFError:
            pass
        img = scan_session.images[0]
        self.assertNotEqual(img, None)

    def test_simple_scan_gray(self):
        try:
            self.dev.options['mode'].value = "Gray"
        except pyinsane.PyinsaneException:
            self.skipTest("scanner does not support required option")
        scan_session = self.dev.scan(multiple=False)
        try:
            while True:
                scan_session.scan.read()
        except EOFError:
            pass
        img = scan_session.images[0]
        self.assertNotEqual(img, None)

    def test_simple_scan_color(self):
        try:
            self.dev.options['mode'].value = "Color"
        except pyinsane.PyinsaneException:
            self.skipTest("scanner does not support required option")
        scan_session = self.dev.scan(multiple=False)
        try:
            while True:
                scan_session.scan.read()
        except EOFError:
            pass
        img = scan_session.images[0]
        self.assertNotEqual(img, None)

    def test_multi_scan_on_flatbed(self):
        try:
            self.dev.options['source'].value = "Flatbed"
            self.dev.options['mode'].value = "Color"
        except pyinsane.PyinsaneException:
            self.skipTest("scanner does not support required option")
        scan_session = self.dev.scan(multiple=True)
        try:
            while True:
                scan_session.scan.read()
        except EOFError:
            pass
        self.assertEqual(len(scan_session.images), 1)
        self.assertNotEqual(scan_session.images[0], None)

    def test_multi_scan_on_adf(self):
        adf_found = False
        pages = 0
        if "ADF" in self.dev.options['source'].constraint:
            self.dev.options['source'].value = "ADF"
            adf_found = True
        else:
            for srcname in self.dev.options['source'].constraint:
                # sane-test uses 'Automatic Document Feeder' instead of ADF
                # WIA uses 'feeder'
                if "feeder" in srcname.lower():
                    self.dev.options['source'].value = srcname
                    if os.name != "nt":
                        pages = 10 # sane-test scans give us 10 pages
                    adf_found = True
        self.assertTrue(adf_found)
        self.dev.options['mode'].value = "Color"
        if not adf_found:
            self.skipTest("scanner does not support required option")
            return
        scan_session = self.dev.scan(multiple=True)
        try:
            while True:
                try:
                    scan_session.scan.read()
                except EOFError:
                    pass
        except StopIteration:
            pass
        self.assertEqual(len(scan_session.images), pages)

    def test_expected_size(self):
        try:
            self.dev.options['source'].value = "Flatbed"
            self.dev.options['mode'].value = "Color"
        except pyinsane.PyinsaneException:
            self.skipTest("scanner does not support required option")
        scan_session = self.dev.scan(multiple=False)
        scan_size = scan_session.scan.expected_size
        self.assertTrue(scan_size[0] > 100)
        self.assertTrue(scan_size[1] > 100)
        scan_session.scan.cancel()

    def test_get_progressive_scan(self):
        try:
            self.dev.options['source'].value = "Flatbed"
            self.dev.options['mode'].value = "Color"
        except pyinsane.PyinsaneException:
            self.skipTest("scanner does not support required option")
        scan_session = self.dev.scan(multiple=False)
        last_line = 0
        expected_size = scan_session.scan.expected_size
        try:
            while True:
                scan_session.scan.read()

                self.assertEqual(scan_session.scan.available_lines[0], 0)
                current_line = scan_session.scan.available_lines[1]
                self.assertTrue(last_line <= current_line)
                last_line = current_line

                img = scan_session.scan.get_image(0, current_line)
                self.assertEqual(img.size[0], expected_size[0])
                self.assertEqual(img.size[1], current_line)
        except EOFError:
            pass
        self.assertTrue(last_line <= current_line)
        self.assertEqual(current_line, expected_size[1])
        last_line = current_line
        img = scan_session.scan.get_image(0, current_line)
        self.assertEqual(img.size[0], expected_size[0])
        self.assertEqual(img.size[1], current_line)

        img = scan_session.images[0]
        self.assertNotEqual(img, None)

    def tearDown(self):
        del(self.dev)