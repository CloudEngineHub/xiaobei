"""Keep media readiness independent of submission acceptance."""


class VideoReadinessError(RuntimeError):
    def __init__(self, readiness):
        self.readiness = readiness
        super().__init__('video readiness is unconfirmed; note submission was not attempted')


def classify_transcode(success, message, response):
    response = response if isinstance(response, dict) else {}
    transport = response.get('_xiaobei_query') or {}
    status = transport.get('http_status')
    if not success:
        if status == 401 or response.get('code') in (401, -100) or any(
            text in str(message) for text in ('无登录信息', '未登录', '登录已失效')
        ):
            reason = 'auth_unavailable'
        elif transport.get('kind') == 'network_error':
            reason = 'network_error'
        elif isinstance(status, int) and status >= 500:
            reason = 'server_error'
        else:
            reason = 'query_rejected'
        return {'state': 'readiness_unknown', 'reason': reason}
    data = response.get('data')
    if not isinstance(data, dict) or not data:
        return {'state': 'readiness_unknown', 'reason': 'empty_response'}
    if (data.get('hasFirstFrame') is True or data.get('has_first_frame') is True
            or data.get('firstFrameFileId') or data.get('first_frame_file_id')
            or data.get('status') in (2, 'success', 'SUCCESS')):
        return {'state': 'ready'}
    return {'state': 'pending'}
