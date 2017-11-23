import json
import requests

from .conf import TOKEN


class SlackError(Exception):
    pass


def get_usergroup(user_id):
    response = requests.get('https://slack.com/api/usergroups.users.list',
                            params={'token': TOKEN, 'usergroup': user_id,
                                    'include_disabled': False})
    if not response.ok:
        raise SlackError("Error while contacting Slack API")

    try:
        data = response.json()
    except Exception:
        raise SlackError("Response from Slack API was not well formed")

    return data.get('ok', False) and data.get('users', [])


def user_is_active(user_id):
    response = requests.post('https://slack.com/api/users.getPresence',
                             data={'token': TOKEN, 'user': user_id})

    if not response.ok:
        raise SlackError("Error while contacting Slack API")

    try:
        data = response.json()
    except Exception:
        raise SlackError("Response from Slack API was not well formed")

    if not data.get('ok', False):
        raise SlackError(data.get('error', "Slack reported an error"))

    return data.get('presence') == "active"


def post_ephemeral(channel_id, user_id, text, attachments=None):
    data = {'token': TOKEN, 'channel': channel_id, 'user': user_id,
            'text': text}
    if attachments is not None:
        data['attachments'] = json.dumps(attachments)
    requests.post('https://slack.com/api/chat.postEphemeral', data=data)


def post_channel(channel_id, text, attachments=None):
    data = {'token': TOKEN, 'channel': channel_id, 'text': text}
    if attachments is not None:
        data['attachments'] = json.dumps(attachments)
    requests.post('https://slack.com/api/chat.postMessage', data=data)
