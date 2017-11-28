import json
import requests

from .conf import OUTGOING_TOKEN


class SlackError(Exception):
    pass


def get_usergroup(user_id):
    response = requests.post('https://slack.com/api/usergroups.users.list',
                             data={'token': OUTGOING_TOKEN,
                                   'usergroup': user_id,
                                   'include_disabled': False})
    from .tasks import logger
    logger.info("Sent request to get usergroup for user_id: '%s', response "
                "code: %s, response content: '%s' ",
                user_id, response.status_code, response.text)

    if not response.ok:
        raise SlackError("Error while contacting Slack API")

    try:
        data = response.json()
    except Exception:
        raise SlackError("Response from Slack API was not well formed")

    return data.get('ok', False) and data.get('users', [])


def user_is_active(user_id):
    response = requests.post('https://slack.com/api/users.getPresence',
                             data={'token': OUTGOING_TOKEN, 'user': user_id})
    from .tasks import logger
    logger.info("Sent request to get presense for user_id: '%s', response "
                "code: %s, response content: '%s' ",
                user_id, response.status_code, response.text)

    if not response.ok:
        raise SlackError("Error while contacting Slack API")

    try:
        data = response.json()
    except Exception:
        raise SlackError("Response from Slack API was not well formed")

    if not data.get('ok', False):
        raise SlackError(data.get('error', "Slack reported an error"))

    return data.get('presence') == "active"


def get_members(channel_id):
    response = requests.post('https://slack.com/api/channels.info',
                             data={'token': OUTGOING_TOKEN,
                                   'channel': channel_id})
    from .tasks import logger
    logger.info("Sent request to get channel info for channel_id: '%s', "
                "response code: %s, response content: '%s' ",
                channel_id, response.status_code, response.text)

    if not response.ok:
        raise SlackError("Error while contacting Slack API")

    try:
        data = response.json()
    except Exception:
        raise SlackError("Response from Slack API was not well formed")

    if not data.get('ok', False):
        raise SlackError(data.get('error', "Slack reported an error"))

    return data.get('channel', {}).get('members', [])


def post_ephemeral(channel_id, user_id, text, attachments=None):
    data = {'token': OUTGOING_TOKEN, 'channel': channel_id, 'user': user_id,
            'text': text}
    if attachments is not None:
        data['attachments'] = json.dumps(attachments)
    response = requests.post('https://slack.com/api/chat.postEphemeral',
                             data=data)
    from .tasks import logger
    logger.info("Sent ephemeral message, data was: %s, response code: %s, "
                "response content: '%s'",
                data, response.status_code, response.text)


def post_channel(channel_id, text, attachments=None):
    data = {'token': OUTGOING_TOKEN, 'channel': channel_id, 'text': text}
    if attachments is not None:
        data['attachments'] = json.dumps(attachments)
    response = requests.post('https://slack.com/api/chat.postMessage',
                             data=data)
    from .tasks import logger
    logger.info("Sent public message, data was: %s, response code: %s, "
                "response content: '%s'",
                data, response.status_code, response.text)
