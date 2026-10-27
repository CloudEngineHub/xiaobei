"""Classify Model Studio errors without treating every HTTP 403 as model absence."""
import json


class BailianAPIError(Exception):
    def __init__(self, status: int, body: str):
        self.code, self.body = status, body
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        self.service_code = str(parsed.get('code', ''))
        self.request_id = str(parsed.get('request_id', ''))
        token = self.service_code.lower()
        if any(x in token for x in ('allocationquota', 'freetieronly', 'arrearage', 'insufficientbalance', 'quotaexhausted')):
            self.category = 'quota_or_billing'
        elif status == 401 or any(x in token for x in ('invalidapikey', 'unauthorized', 'authentication')):
            self.category = 'authentication'
        elif any(x in token for x in ('modelnotfound', 'modelnotexist', 'modelnotavailable', 'modelnotsupported')) or (status == 404 and 'model' in token):
            self.category = 'model_unsupported'
        elif status == 429 or 'throttl' in token or 'ratelimit' in token:
            self.category = 'rate_limit'
        elif status >= 500:
            self.category = 'service'
        else:
            self.category = 'invalid_request_or_permission'
        super().__init__(f'{self.category}: HTTP {status}, code={self.service_code}, request_id={self.request_id}')
