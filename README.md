sasbury_com_builder
===================

When I decided to update my web site, I wanted, for ease of setup and maintenance, a static site. But I also wanted to be able to write using [markdown](http://daringfireball.net/projects/markdown/). My first idea was to write a script to process the markdown and build a site, but then I ran across [this post](https://nicolas.perriault.net/code/2012/dead-easy-yet-powerful-static-website-generator-with-flask/). Using Flask and a few other plug-ins I now have a really nice, easy to maintain script for building my site.

The file site_builder.py is the script i created to build my site based on that
post. It is discussed futher on in several entries on my blog at
www.sasbury.com. The script has not been made "reusable" and contains
references to my blog, however, these are certainly editable. Of course the ftp
information required to upload the site is not included ;-).

The basic a folder structure for the site is:

	+ site
	|
	---- build
	|
	---- env 
	|
	---- src
		  |
		  ---- pages 
		  |
		  ---- static 
		  |
		  ---- templates 

where `env` is the folder for a [virtual environment](http://pypi.python.org/pypi/virtualenv) for the python packages. The packages I am using are listed in the imports, as is `future` with statement I am using.

	from __future__ import with_statement

	import sys
	import os.path
	import shutil
	import zipfile
	import itertools
	import yaml
	import markdown
	import PyRSS2Gen

	from filecmp import dircmp
	from datetime import datetime
	from flask import Flask, render_template,abort,make_response
	from flask_frozen import Freezer
	from HTMLParser import HTMLParser

The most important one is [Frozen Flask](http://pythonhosted.org/Frozen-Flask/) which will walk the flask application, using the url_for, function calls and save the site into the build folder. Unlike the post I based this project on, I didn't use FlatPages, instead I recreated the parts of that module that I needed.

