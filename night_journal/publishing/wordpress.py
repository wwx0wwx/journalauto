from __future__ import annotations

import xmlrpc.client
from .base import Publisher


class WordPressPublisher(Publisher):
    def __init__(self, url: str, username: str, password: str, blog_id: int = 1):
        # url should be like https://example.com/xmlrpc.php
        self.url = url
        self.username = username
        self.password = password
        self.blog_id = blog_id

    def publish(self, title: str, body: str, description: str, category: str) -> tuple[bool, str]:
        try:
            client = xmlrpc.client.ServerProxy(self.url)
            content = {
                'post_title': title,
                'post_content': body,
                'post_excerpt': description,
                'post_status': 'publish',
                'terms_names': {'category': [category]},
            }
            post_id = client.wp.newPost(
                self.blog_id,
                self.username,
                self.password,
                content,
            )
            return True, str(post_id)
        except Exception as e:
            return False, str(e)
