import unittest
import os, shutil
from jpegdupes import jpegdupes
# import jpegdupes.jpegdupes


""" To run all tests in this class, from the root of the respository run:
    python -m unittest tests.test_jpegdupes
"""


class A(object):
    """ Used for mocking command line arguments. """



class TestJpegDupes(unittest.TestCase):

    IMAGES_DIR = "tests/images"
    LIBRARY_DIR = "tests/library"
    TOFILTER_DIR = "tests/tofilter"
    LIBRARY_SUBDIR = LIBRARY_DIR + "/sub"
    TOFILTER_SUBDIR = TOFILTER_DIR + "/subfolder"
    

    @classmethod
    def setUpClass(cls):
        os.makedirs(cls.LIBRARY_SUBDIR)
        os.makedirs(cls.TOFILTER_SUBDIR)
        for img in [jpg for jpg in os.listdir(cls.IMAGES_DIR) if jpg != "leo.jpg"]:
            shutil.copy2(cls.IMAGES_DIR + os.path.sep + img, cls.LIBRARY_SUBDIR)
        for img in ("/donatello2.jpg", "/Raphael2.jpeg", "/leo.jpg", "/mikey.jpg"):
            shutil.copy2(cls.IMAGES_DIR + img, cls.TOFILTER_SUBDIR)

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

        # Out of the 6 images, 1 was not copied to the library (leo.jpg), 2 duplicates should have been deleted
        self.assertEqual(len(list(os.listdir(self.LIBRARY_SUBDIR))), len(list(os.listdir(self.IMAGES_DIR)))-3, "Expected only 3 files in library")
        for img in ("/donatello2.jpg", "/Raphael.jpeg"):
            self.assertFalse(os.path.isfile(self.LIBRARY_SUBDIR + img), img)
        self.assertTrue(os.path.isfile(self.LIBRARY_DIR + jpegdupes.JPEG_CACHE_FILE), jpegdupes.JPEG_CACHE_FILE)

    def test_filterfolder(self):
        """ The filterfolder function should detect that leo.jpg is not yet present in the library folder.
            The older files should be recognized as duplicates and deleted.
        """
        tofilter = self.TOFILTER_DIR
        library = self.LIBRARY_DIR
        jpegdupes.filter_folder(tofilter, library, delete=True)

        self.assertTrue(os.path.isfile(self.TOFILTER_SUBDIR + "/leo.jpg"))
        for img in ("/donatello2.jpg", "/Raphael2.jpeg", "/mikey.jpg"):
            self.assertFalse(os.path.isfile(self.TOFILTER_SUBDIR + img), img)
        self.assertTrue(os.path.isfile(library  + jpegdupes.JPEG_CACHE_FILE), "File not found {}".format(library + jpegdupes.JPEG_CACHE_FILE))
        self.assertTrue(os.path.isfile(tofilter + jpegdupes.JPEG_CACHE_FILE), "File not found {}".format(tofilter + jpegdupes.JPEG_CACHE_FILE))

