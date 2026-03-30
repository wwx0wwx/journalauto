from __future__ import annotations

import json
import urllib.request
import urllib.error
from .base import Publisher


class ZhiliuPublisher(Publisher):
    """直流博客 REST API 发布器。

    config 字段:
        endpoint    完整的文章发布 API 地址，例如 https://example.com/api/posts
        token       Bearer 认证 token
        category_id 分类 ID（字符串或整数，可选）
    """

    def __init__(self, endpoint: str, token: str, category_id: str = ''):
        self.endpoint = endpoint.rstrip('/')
        self.token = token
        self.category_id = category_id

    def publish(self, title: str, body: str, description: str, category: str) -> tuple[bool, str]:
        payload: dict = {
            'title': title,
            'content': body,
            'excerpt': description,
            'status': 'publish',
        }
        if self.category_id:
            payload['category_id'] = self.category_id
        elif category:
            payload['category'] = category

        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                'Content-Type': 'application/json; charset=utf-8',
                'Authorization': f'Bearer {self.token}',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read().decode('utf-8')
                try:
                    obj = json.loads(resp_body)
                    post_id = str(obj.get('id', obj.get('post_id', '')))
                except Exception:
                    post_id = resp_body[:80]
                return True, post_id
        except urllib.error.HTTPError as e:
            return False, f'HTTP {e.code}: {e.read().decode("utf-8", errors="replace")[:200]}'
        except Exception as e:
            return False, str(e)
