imgdupes
========

imgdupes is a command-line tool that finds duplicated images in a directory tree. The difference with other similar utilities (like fdupes) is that imgdupes is specifically tailored to JPEG files, and compares only the image data, specifically ignoring any metadata present in the file (EXIF info, tags, titles, orientation tag...). This makes possible to find duplicated images when one of the file's metadata has been modified by imaging software, and byte-by-byte comparators fail to report them as equal. This might happen in a number of situations, for example:

- Modifying EXIF info to adjust date taken (typically when the camera has been set at a wrong date/time)
- Adjusting rotation flag
- Adding tags, or setting title, description, rating...
 
In fact, most image manipulation suites, like Shotwell, fail to recognize that two images with different metadata might be actually the same. This casues that when user imports new photos from camera or SD card, the suite mistakenly re-import images that were already in the collection, but that had been tagged, rotated or whatever. This kind of duplicates are annoying and hard to find, and usually require human checking. imgdupes allows to automate the task of looking for image duplicates that would remain undetected by most duplicate file finder utilities.

imgdupes invocation is intentionally similar to that of the UNIX command fdupes. This is just for clarity and ease of use, but imgdupes is not meant as a direct replacement of fdupes, which is much more mature and well tested. The recommended usage is using fdupes first, to find and delete byte-by-byte duplicates, and only then using imgdupes to look for duplicates that fdupes might have missed. Even if the interface is inspired by fdupes, not all fdupes parameters are implemented, though, and there're even some differences in global behaviour (i. e. recursive exploring, which is optional in fdupes but mandatory in imgdupes), so be sure to execute imgdupes --help to check the details.

Analyzing each image chunk of data in order to compare and find for duplicates is a time consuming task. So, in order to speed up future executions, imgdupes creates a cache file inside the directory it's analyzing, containing the image signatures already generated. It's a small file, called ".signatures", and follows python pickle format. Anyway, if you don't feel comfortable with the idea of imgdupes writing to your disk, the parameter "--clean" may be used, which assures that nothing will be written to disk. The price is that all images will need to be re-analyzed each time imgdupes is executed, and with a big collection it might take a while.

As a final disclaimer, imgdupes is provided as is, and I can't be made responsible of any damages that might happen to your collection by using it. I use imgdupes myself, so I'm the first interested in that it's free of bugs, but I can't make any guarantee of that. Keep also in mind that, even if imgdupes reports that two files correspond to the same image, this might not necessarily mean that you have to delete one of them. It's up to you to decide which cases correspond to software mistakes (i. e. Shotwell re-importing an old image that's been already imported and tagged) and which are legitimate.

History:

v1.0
  Initial release
