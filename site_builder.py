import ftplib
import sys
import os.path
import shutil
import itertools
import yaml
import markdown
import PyRSS2Gen
import filecmp
import re

import hashlib
from getpass import getpass
from datetime import datetime
from flask import Flask, render_template,abort
from flask_frozen import Freezer
from six.moves.html_parser import HTMLParser
import six
from six.moves import input

DEBUG = True
BUILD_FOLDER = '../build'
LAST_UPLOAD_FOLDER = '../.previous_upload'
FREEZER_DESTINATION = BUILD_FOLDER

app = Flask(__name__)
app.config.from_object(__name__)
freezer = Freezer(app)

file_cache = {}

#
# From http://stackoverflow.com/questions/753052/strip-html-from-strings-in-python
#
class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

# From http://effbot.org/librarybook/ftplib.htm
def ftp_upload(ftp, uploadpath, filepath):
    ext = os.path.splitext(filepath)[1]
    if ext in (".txt", ".htm", ".html"):
        ftp.storlines("STOR " + uploadpath, open(filepath, "rb"))
    else:
        ftp.storbinary("STOR " + uploadpath, open(filepath, "rb"), 1024)

# From FTPTools, converted to python3
def makedirs(ftp, dirpath):
    """Try to create directories out of each part of `dirpath`.
    """
    pwd = ftp.pwd()
    try:
        ftp.cwd(dirpath)
    except ftplib.Error:
        pass
    else:
        return
    finally:
        ftp.cwd(pwd)

    # Then if we're still alive, split the path up.
    parts = dirpath.split('/')
    # Then iterate through the parts.
    cdir = ""
    for dir in parts:
        cdir += dir + "/"
        # No point in trying to create the directory again when we only
        # added a slash.
        if not dir:
            continue
        try:
            ftp.mkd(cdir)
        except ftplib.Error:
            pass

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

#
# Based on Flask FlatPages
#
def parsePage(string, path):

    lines = iter(string.split(u'\n'))
    extensions = ['codehilite']
    page = {}

    page['path'] = path
    page['meta_yaml'] = u'\n'.join(itertools.takewhile(six.text_type.strip, lines))
    page['content'] = u'\n'.join(lines)
    page['meta'] = yaml.safe_load(page['meta_yaml'])
    page['html'] = markdown.markdown(page['content'], extensions)
    page['summary'] = strip_tags(page['html'])[:280]+' ...' #first set of characters

    if page['meta']['tags'] is None:
        page['meta']['tags'] = []

    sshot_re = re.compile('alt="sshot:')
    page['html'] = sshot_re.sub('class="sshot" alt="sshot:', page['html'])

    return page

def processFile(path, filepath):
    mtime = os.path.getmtime(filepath)
    with open(filepath) as fd:
        content = fd.read()
    page = parsePage(content, path)
    page['mtime'] = mtime
    page['filepath'] = filepath
    return page

def processFolder(directory, path_prefix=(),pages={}):

    for name in os.listdir(directory):
        full_name = os.path.join(directory, name)
        if os.path.isdir(full_name):
            processFolder(full_name, path_prefix + (name,),pages)
        elif name.endswith('.md') and not name.startswith('_'):
            name_without_extension = name[:-len('.md')]
            new_name = name_without_extension+'.html'
            path = u'/'.join(path_prefix+(new_name,))
            pages[path] = processFile(path, full_name)
    return pages

def getPage(path,pages, default=None):
    page = None
    try:
        page = pages[path]
        filepath = page['filepath']
        mtime = os.path.getmtime(filepath)
        if(page['mtime']!=mtime):
            page = processFile(path,filepath)
    except KeyError:
        page = default

    return page

def getPageDateString(page):

    dateString = str(page['meta']['date'])

    if dateString.startswith('circa'):
        return dateString.split(' ')[1]
    elif dateString == '' or page['meta']['date'] is None:
        return -1;
    elif dateString == 'archive':
        return "2012";#rank these above circa, as a string like circa will be
    else:
        return dateString.split(' ')[0]

def getPageDate(page):
    dateString = getPageDateString(page)
    dt = datetime.strptime("2000","%Y") #if no date is set, make it in the past

    if isinstance(dateString, str) or isinstance(dateString, six.text_type):
        if len(dateString)==4:
            dt = datetime.strptime(dateString, "%Y")
        else:
            dt = datetime.strptime(dateString, "%Y-%m-%d")

    return dt

pages = processFolder(os.path.join(app.root_path,u'pages'))

#
# figure out notes versus projects and set up back links
#
projects = []
blog = []
reading_list = []

for path,page in pages.items():
    if path.startswith('projects'):
        page['parent_url'] = '/portfolio/'
        page['parent'] = 'Back to \"about me\"'
        projects.append(page)
    elif path.startswith('notes'):
        page['parent_url'] = '/notes/'
        page['parent'] = 'Back to notebook'
        blog.append(page)
    elif path.startswith('reading'):
        page['parent_url'] = '/reading/'
        page['parent'] = 'Back to reading list'
        reading_list.append(page)

#
#build rss feed from notes
#
rssItems = []

for page in blog:

    dt = getPageDate(page)

    item = PyRSS2Gen.RSSItem(
         title = page['meta']['title'],
         link = 'http://www.sasbury.com'+'/'+page['path'],
         description = page['summary'],
         guid = PyRSS2Gen.Guid('/'+page['path']),
         pubDate = dt)

    rssItems.append(item)

rssItems.sort(key=lambda rssItem: rssItem.pubDate, reverse=True)

rss = PyRSS2Gen.RSS2(
    title = "sasbury.com feed",
    link = "http://www.sasbury.com",
    description = "sasbury.com RSS feed",
    docs = '',
    lastBuildDate = datetime.utcnow(),
    items = rssItems
    )

rssFeed = rss.to_xml('utf-8')

#
#set up routes
#
@app.route('/')
def index():
    sorted_blog = sorted(blog, reverse=True, key=getPageDate)
    sorted_projects = sorted(projects, reverse=True, key=getPageDate )
    return render_template('index.html', notes=sorted_blog[:6],projects=sorted_projects[:2]
                            ,projCount=len(projects),noteCount=len(blog))

@app.route('/notes/')
def notes():
    sorted_blog = sorted(blog, reverse=True, key=getPageDate)
    return render_template('notes.html', notes=sorted_blog)

@app.route('/notes/sasbury_rss.xml')
def rss():
    return rssFeed, 200, {'Content-Type': 'application/xml; charset=utf-8'}

@app.route('/portfolio/')
def portfolio():
    sorted_projects = sorted(projects, reverse=True, key=getPageDate )
    return render_template('portfolio.html', projects=sorted_projects)

@app.route('/books/')
def books():
    return render_template('book_sites.html')

@app.route('/reading/')
def reading():
    sorted_reading_list = sorted(reading_list)
    return render_template('reading.html',book_list=sorted_reading_list)

@app.route('/tag/<string:tag>/')
def tag(tag):

    tagged = []

    for path,page in pages.items():
        tags = page['meta']['tags']
        if tag in tags:
            tagged.append(page)

    sorted_pages = sorted(tagged, reverse=True, key=getPageDate)
    return render_template('tag.html', pages=sorted_pages, tag=tag)

@app.route('/<path:path>')
def page(path):
    page = getPage(path,pages)

    if not page:
        abort(404)

    if path.startswith('notes'):
        return render_template('note.html', page=page)
    else:
        return render_template('page.html', page=page)

#
# include book sites for freeze
#
@freezer.register_generator
def books_url_generator():
    # URLs as strings
    yield '/books/ejava.html'
    yield '/books/ejava2.html'
    yield '/books/jfc.html'
    yield '/books/lxatwork.html'

#
# Main app code
#
if __name__ == '__main__':

    if len(sys.argv) > 1 and sys.argv[1] == "build":


        if not os.path.exists(BUILD_FOLDER):
            print("Creating build folder")
            os.mkdir(BUILD_FOLDER)

        print("Compiling and saving site")
        freezer.freeze()

    elif len(sys.argv) > 1 and sys.argv[1] == "upload":

        if not os.path.exists(BUILD_FOLDER):
            print("No build folder, build first!")
        else:
            if not os.path.exists(LAST_UPLOAD_FOLDER):
                print("Creating placeholder last upload folder")
                os.mkdir(LAST_UPLOAD_FOLDER)

            ftpuser = input("User: ")
            pw = getpass("Password: ")
            print("Connecting to sasbury.com and uploading new version")
            ftp = ftplib.FTP("ftp.sasbury.com")
            ftp.login(ftpuser, pw)
            #sasburyHost.mirror_to_remote(BUILD_FOLDER,"/")

            for root, dirs, files in os.walk(BUILD_FOLDER):
                for name in files:
                    if name.startswith("."):
                        print("skipping dot file ", name)
                        continue

                    path = os.path.join(root,name)
                    otherPath = path.replace(BUILD_FOLDER,LAST_UPLOAD_FOLDER)
                    uploadPath = path.replace(BUILD_FOLDER,'')
                    uploadDir = root.replace(BUILD_FOLDER, '')

                    makedirs(ftp, uploadDir)

                    if not os.path.exists(otherPath):
                        print("uploading new file ", path, " to ", uploadPath)
                        ftp_upload(ftp, uploadPath, path)
                    else:
                        try:
                            hashOne = md5(path)
                            hashTwo = md5(otherPath)
                        except:
                            hashOne = 1
                            hashTwo = 2

                        if hashOne != hashTwo:
                            print("uploading changed file ", path, " to ", uploadPath)
                            ftp_upload(ftp, uploadPath, path)
                        #else:
                            #print "skipping unchanged file ", path

            for root, dirs, files in os.walk(LAST_UPLOAD_FOLDER):
                for name in files:
                    if name.startswith("."):
                        continue

                    path = os.path.join(root,name)
                    otherPath = path.replace(LAST_UPLOAD_FOLDER, BUILD_FOLDER)
                    uploadPath = path.replace(LAST_UPLOAD_FOLDER, '')
                    if not os.path.exists(otherPath):
                        print("deleting ", uploadPath, otherPath, path)
                        ftp.delete(uploadPath)

            ftp.quit()

            print("Removing last upload folder")
            shutil.rmtree(LAST_UPLOAD_FOLDER)

            if os.path.exists(BUILD_FOLDER):
                print("Moving build to last upload folder")
                os.rename(BUILD_FOLDER,LAST_UPLOAD_FOLDER)

    elif len(sys.argv) > 1 and sys.argv[1] == "static":

        freezer.run(port=8080)

    elif len(sys.argv) > 1 and sys.argv[1] == "public":

        app.run(host='0.0.0.0',port=8080)

    else:

        app.run(port=8080)
