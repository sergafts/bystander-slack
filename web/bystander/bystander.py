import json
import random
import re
from uuid import uuid4

from redis import Redis

from .conf import EXPIRE_SECONDS
from .slack import get_usergroup, post_ephemeral, user_is_active, post_channel


REDIS = Redis('redis', '6379')


class BystanderError(Exception):
    pass


class Bystander(object):
    def __init__(self, raw_text, requester_id, channel_id):
        self.id = None

        self.raw_text = raw_text
        self.requester_id = requester_id
        self.channel_id = channel_id
        self.rejected_user_ids = []

    @classmethod
    def load(cls, id):
        data = REDIS.get(id)

        if data is None:
            raise BystanderError("Request has likely expired")

        data = json.loads(data)

        bystander = cls(data['text'], data['requester_id'], data['channel_id'])
        bystander.id = id
        bystander.user_ids = data['users']
        bystander.text = data['text']
        bystander.rejected_user_ids = data['rejected_user_ids']

        return bystander

    def save(self):
        if self.id is None:
            self.id = uuid4().bytes
        REDIS.set(self.id,
                  json.dumps({'user_ids': self.user_ids,
                              'text': self.text,
                              'requester_id': self.requester_id,
                              'channel_id': self.channel_id,
                              'rejected_user_ids': self.rejected_user_ids}),
                  ex=EXPIRE_SECONDS)

    def delete(self):
        REDIS.delete(self.id)

    def process_text(self):
        users_pat = re.compile(r'<@[^>]+>')

        # Find users
        user_strings = list(set(users_pat.findall(self.raw_text)))
        self.user_ids = [
            re.search(r'<@([^|]+)\|[^>]+>', user_string).groups()[0]
            for user_string in user_strings
        ]

        # Clean text
        self.text = users_pat.sub('', self.raw_text)
        self.text = re.sub(r'\s+', ' ', self.text).strip()

    def resolve_usergroups(self):
        to_remove, to_add = [], []
        for i, user_id in enumerate(self.user_ids):
            users = get_usergroup(user_id)
            if users:
                to_remove.append(i)
                to_add.extend(users)
        for i in reversed(to_remove):
            del self.user_ids[i]
        self.user_ids.extend(to_add)
        self.user_ids = list(set(self.user_ids))

    def filter_out_inactive_users(self):
        self.user_ids = [user_id
                         for user_id in self.user_ids
                         if user_is_active(user_id)]

    def filter_out_requester(self):
        try:
            self.user_ids.remove(self.requester_id)
        except ValueError:
            pass

    @property
    def user_ids_left(self):
        return list(set(self.user_ids) - set(self.rejected_user_ids))

    def send_buttons(self):
        user_id, username = random.choice(self.user_ids_left)
        post_ephemeral(self.channel_id, user_id,
                       "<@{}> has asked you to:".format(self.requester_id),
                       [{'text': self.text},
                        {'text': "Are you up for it:?",
                         "callback_id": "{}:{}".format(self.id,
                                                       self.requester_id),
                         "attachment_type": "default",
                         "actions": [{'name': "yes", 'text': "Accept",
                                      'type': "button", 'value': "yes",
                                      'style': "primary"},
                                     {'name': "no", 'text': "Reject",
                                      'type': "button", 'value': "no",
                                      'style': "danger"}]}])

    def reject(self, user_id):
        self.rejected_user_ids.append(user_id)

    def accept(self, user_id):
        post_channel(self.channel_id, "<@{}> accepted <@{}>'s request to:",
                     [{'text': self.text}])

    def abort(self):
        post_ephemeral(self.channel_id, self.requester_id,
                       ("I'm sorry. It appears that everyone rejected your "
                        "request :cry:"),
                       [{'text': self.text}])
