#!/usr/bin/env python3

import os
import shutil
import argparse
from enum import Enum

import requests
from bs4 import BeautifulSoup


class MediaType(Enum):
    IMAGE = 1
    VIDEO = 2


class Post:
    def __init__(self, post_id, post_author, post_title, media_type, media_url, preview_url):
        self.post_id = post_id
        self.post_user = post_author
        self.post_title = post_title
        self.media_type = media_type
        self.media_url = media_url
        self.preview_url = preview_url


class Grabber:
    def __init__(self, profile_name):
        self.profile_name = profile_name
        self.session = requests.Session()
        self.posts = []

    def prepare_auth(self, session_id, user_agent):
        auth_cookie = {
            'domain': '.onlyfans.com',
            'expires': None,
            'name': 'sess',
            'path': '/',
            'value': session_id,
            'version': 0
        }
        self.session.cookies.set(**auth_cookie)
        self.session.headers = {'User-Agent': user_agent}

    def parse_posts(self, posts):
        for post in posts:
            post_id = post['data-id']
            post_author = post.select('div[class="g-user-username"]')[0].text.strip().lstrip('@')
            try:
                post_title = post.select('div[class="b-post__text"]')[0].text.strip()
            except IndexError:
                post_title = ""

            if post.select('div[class="video-wrapper"]'):
                try:
                    preview_url = post.select('video')[0]['poster']
                    media_url = post.select('source[type="video/mp4"]')[0]['src']
                    self.posts.append(Post(post_id, post_author, post_title, MediaType.VIDEO, media_url, preview_url))
                    print('- Added video from post {}'.format(post_id))
                except (IndexError, KeyError) as e:
                    print('[!] Error while processing post {}'.format(post_id))
                    continue
            elif post.select('div[class="swiper-wrapper"]'):
                try:
                    media_urls = []
                    figures = post.select('figure[class^="swiper-slide"]')
                    for figure in figures:
                        if figure['data-full'] not in media_urls:
                            media_urls.append(figure['data-full'])
                            self.posts.append(Post(post_id, post_author, post_title, MediaType.IMAGE, figure['data-full'], None))
                            print('- Added image from post {}'.format(post_id))
                except (IndexError, KeyError) as e:
                    print('[!] Error while processing post {}'.format(post_id))
                    continue
            else:
                try:
                    media_url = post.select('a[data-toggle="lightbox"]')[0]['href']
                    self.posts.append(Post(post_id, post_author, post_title, MediaType.IMAGE, media_url, None))
                    print('- Added image from post {}'.format(post_id))
                except (IndexError, KeyError) as e:
                    print('[!] Error while processing post {}'.format(post_id))
                    continue

    def grab_start_page(self):
        r = self.session.get('https://onlyfans.com/{}'.format(self.profile_name))

        soup = BeautifulSoup(r.text, 'lxml')
        posts = soup.select('div[class^="b-post b-post_"]')
        if posts:
            print('[!] Found {} posts on the start page'.format(len(posts)))
            self.parse_posts(posts)
            self.check_for_more_pages(soup)
        else:
            print('[!] No posts found, there seems to be a problem')

    def check_for_more_pages(self, soup):
        data_more = soup.select('span[data-more]')
        if data_more:
            print('[!] Fetching additional page')
            self.grab_additional_page(data_more[0]['data-more'])
        else:
            print('[!] Nothing more to process')

    def grab_additional_page(self, more_id):
        headers = {'Referer': 'https://onlyfans.com/'}
        data = {'data': more_id}
        r = self.session.post('https://onlyfans.com/component/entities/post/more', data=data, headers=headers)
        soup = BeautifulSoup(r.text, 'lxml')
        posts = soup.select('div[class^="b-post b-post_"]')
        if posts:
            print('[!] Found {} more posts'.format(len(posts)))
            self.parse_posts(posts)
        self.check_for_more_pages(soup)

    def download_posts(self):
        base_path = self.profile_name
        os.makedirs(base_path, exist_ok=True)
        os.makedirs(os.path.join(base_path, 'images'), exist_ok=True)
        os.makedirs(os.path.join(base_path, 'videos'), exist_ok=True)
        for post in self.posts:
            if post.media_type == MediaType.IMAGE:
                folder = 'images'
            elif post.media_type == MediaType.VIDEO:
                folder = 'videos'
            else:
                continue
            path = os.path.join(base_path, folder, os.path.basename(post.media_url))
            path_hidden = os.path.join(base_path, folder, '.', os.path.basename(post.media_url))

            if not os.path.exists(path):
                print('- Downloading {}'.format(path))
                r = self.session.get(post.media_url, stream=True)
                with open(os.path.join(path_hidden), 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
                shutil.move(path_hidden, path)
            else:
                print('- File already exists {}'.format(path))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', type=str, help='profile to archive')
    parser.add_argument('session', type=str, help='active browser session')
    parser.add_argument('user_agent', type=str, help='user agent of used browser')
    parser.add_argument('--no-download', action='store_true', help='do not download files')
    args = parser.parse_args()

    grabber = Grabber(args.profile)
    grabber.prepare_auth(args.session, args.user_agent)
    grabber.grab_start_page()
    if args.no_download:
        for post in grabber.posts:
            print(post.media_url)
    else:
        grabber.download_posts()
