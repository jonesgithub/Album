# -*- coding: utf-8 -*-
#
# jQuery File Upload Plugin GAE Python Example 2.0.1
# https://github.com/blueimp/jQuery-File-Upload
#
# Copyright 2011, Sebastian Tschan
# https://blueimp.net
#
# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT
#

from __future__ import with_statement
from google.appengine.api import files, images
from google.appengine.ext import blobstore, db
import albums
import json
import logging
import re
import urllib
import webapp2
from base import JINJA_ENVIRONMENT

MIN_FILE_SIZE = 1  # bytes
MAX_FILE_SIZE = 5000000  # bytes
IMAGE_TYPES = re.compile('image/(gif|p?jpeg|(x-)?png)')
ACCEPT_FILE_TYPES = IMAGE_TYPES


def cleanup(blob_keys):
    blobstore.delete(blob_keys)


class UploadHandler(webapp2.RequestHandler):

    def initialize(self, request, response):
        super(UploadHandler, self).initialize(request, response)
        logging.info("initialize(...)")
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.headers[
            'Access-Control-Allow-Methods'
        ] = 'OPTIONS, HEAD, GET, POST, PUT, DELETE'
        self.response.headers[
            'Access-Control-Allow-Headers'
        ] = 'Content-Type, Content-Range, Content-Disposition'

    def validate(self, fileObject):
        logging.info("validate(...)")
        if fileObject['size'] < MIN_FILE_SIZE:
            fileObject['error'] = 'File is too small'
        elif fileObject['size'] > MAX_FILE_SIZE:
            fileObject['error'] = 'File is too big'
        elif not ACCEPT_FILE_TYPES.match(fileObject['type']):
            fileObject['error'] = 'File type not allowed'
        else:
            return True
        return False

    def get_file_size(self, fileObject):
        logging.info("get_file_size(...)")
        fileObject.seek(0, 2)  # Seek to the end of the fileObject
        size = fileObject.tell()  # Get the position of EOF
        fileObject.seek(0)  # Reset the fileObject position to the beginning
        return size

    def write_blob(self, data, info):
        logging.info("write_blob(...)")
        blob = files.blobstore.create(
            mime_type=info['type'],
            _blobinfo_uploaded_filename=info['name']
        )
        with files.open(blob, 'a') as f:
            f.write(data)
        files.finalize(blob)
        return files.blobstore.get_blob_key(blob)

    def handle_upload(self):
        logging.info("handle_upload(...)")
        results = []
        blob_keys = []
        for name, fieldStorage in self.request.POST.items():  # @UnusedVariable
            if type(fieldStorage) is unicode:
                continue
            result = {}
            result['name'] = re.sub(
                r'^.*\\',
                '',
                fieldStorage.filename
            )
            result['type'] = fieldStorage.type
            result['size'] = self.get_file_size(fieldStorage.file)
            if self.validate(result):
                blob_key = str(
                    self.write_blob(fieldStorage.value, result)
                )
                blob_keys.append(blob_key)
                
#                 album_key = self.request.get('album_key')
                image_url = images.get_serving_url(
                            blob_key,
                            secure_url=self.request.host_url.startswith(
                                'https'
                            )
                        )
                result['url'] = image_url
                logging.info("url == " + result['url'])

                result['delete_type'] = 'DELETE'
                result['delete_url'] = self.request.host_url + \
                    '/?key=' + urllib.quote(blob_key, '')
                    
#                 if (IMAGE_TYPES.match(result['type'])):
#                     try:
#                         result['url'] = images.get_serving_url(
#                             blob_key,
#                             secure_url=self.request.host_url.startswith(
#                                 'https'
#                             )
#                         )
#                         result['thumbnail_url'] = result['url'] + \
#                             THUMBNAIL_MODIFICATOR
#                     except:  # Could not get an image serving url
#                         pass
#                 if not 'url' in result:
#                     result['url'] = self.request.host_url + \
#                         '/' + blob_key + '/' + urllib.quote(
#                             result['name'].encode('utf-8'), '')
#                     result['thumbnail_url'] = result['url'] + THUMBNAIL_MODIFICATOR
            results.append(result)
        return results

    def options(self):
        logging.info("options(...)")
        pass

    def head(self):
        logging.info("head(...)")
        pass

    def get(self, album_key):
        logging.info("get(...)")
        album = albums.Album.get(album_key)
        template_values = {
                           'album':album
        }

        template = JINJA_ENVIRONMENT.get_template('/templates/albumUpload.html')
        self.response.write(template.render(template_values))

    def post(self, album_key):
        logging.info("post(...)")
        
        if (self.request.get('_method') == 'DELETE'):
            return self.delete()
        album = db.Model.get(album_key) 
        result = {'files': self.handle_upload()}
        for uploaded_file in result['files']:
            picture = albums.Picture(parent=album)
            picture.name = uploaded_file['name']
            picture.image = uploaded_file['url']
            picture_key = picture.put()
            uploaded_file['picture_key'] = str(picture_key)
        s = json.dumps(result, separators=(',', ':'))
        redirect = self.request.get('redirect')
        if redirect:
            return self.redirect(str(
                redirect.replace('%s', urllib.quote(s, ''), 1)
            ))
        if 'application/json' in self.request.headers.get('Accept'):
            self.response.headers['Content-Type'] = 'application/json'
        self.response.write(s)

    def delete(self):
        logging.info("delete(...)")
        blobstore.delete(self.request.get('key') or '')


app = webapp2.WSGIApplication(
    [
        ('/upload/([^/]+)', UploadHandler)
    ],
    debug=True
)
