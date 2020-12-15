import unittest
import os, shutil
from jpegdupes import jpegdupes


""" To run all tests in this class, from the root of the respository run:
    python -m unittest tests.test_jpegdupes
"""


class A(object):
    """ Used for mocking command line arguments. """



class TestJpegDupes(unittest.TestCase):

    LIBRARY_DIR = "tests/library"
    TOFILTER_DIR = "tests/tofilter"
    IMAGES_DIR = "tests/images"

    @classmethod
    def setUpClass(cls):
        os.makedirs(cls.LIBRARY_DIR)
        os.makedirs(cls.TOFILTER_DIR)
        for img in [jpg for jpg in os.listdir(cls.IMAGES_DIR) if jpg != "leo.jpg"]:
            shutil.copy2(cls.IMAGES_DIR + os.path.sep + img, cls.LIBRARY_DIR)
        for img in ("/donatello2.jpg", "/Raphael2.jpeg", "/leo.jpg", "/mikey.jpg"):
            shutil.copy2(cls.IMAGES_DIR + img, cls.TOFILTER_DIR)

    @classmethod
    def tearDownClass(cls):
        # return
        shutil.rmtree(cls.LIBRARY_DIR)
        shutil.rmtree(cls.TOFILTER_DIR)

    def test_remove_duplicates(self):
        """ The function should recognize and delete two duplicate images. """
        args = A()
        args.directory = self.LIBRARY_DIR
        args.delete = True
        args.auto = True
        args.clean = False
        args.sameline = True
        args.method = "MD5"

        # for some unkown reason the line
        # colsize = int(os.popen("stty size", "r").read().split()[1])
        # fails when running unittests from within visual studio code, so we mock this
        from unittest import mock
        with mock.patch("jpegdupes.jpegdupes.get_terminal_width", return_value=150):
            jpegdupes.remove_duplicates(args)

        self.assertEquals(len(list(os.listdir(self.LIBRARY_DIR))), len(list(os.listdir(self.IMAGES_DIR)))-2, "Only 2 images should be deleted")
        for img in ("/donatello2.jpg", "/Raphael.jpeg"):
            self.assertFalse(os.path.isfile(self.LIBRARY_DIR + img), img)
