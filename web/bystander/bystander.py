import json
import random
import re
from uuid import uuid4

from redis import Redis

from .conf import EXPIRE_SECONDS
from .slack import (get_members, get_usergroup, post_channel, post_ephemeral,
                    user_is_active)


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
        bystander.user_ids = data['user_ids']
        bystander.usergroup_ids = data['usergroup_ids']
        bystander.here = data['here']
        bystander.text = data['text']
        bystander.rejected_user_ids = data['rejected_user_ids']

        return bystander

    def save(self):
        if self.id is None:
            self.id = str(uuid4())
        REDIS.set(self.id,
                  json.dumps({'user_ids': self.user_ids,
                              'usergroup_ids': self.usergroup_ids,
                              'here': self.here,
                              'text': self.text,
                              'requester_id': self.requester_id,
                              'channel_id': self.channel_id,
                              'rejected_user_ids': self.rejected_user_ids}),
                  ex=EXPIRE_SECONDS)

    def delete(self):
        REDIS.delete(self.id)

    def process_text(self):
        users_pat = re.compile(r'<@([^|]+)\|[^>]+>')
        usergroups_pat = re.compile(r'<!subteam\^([^|]+)\|@[^>]+>')
        here_pat = re.compile(r'<!(channel|here)>')

        # Find users
        self.user_ids = [match.groups()[0]
                         for match in users_pat.finditer(self.raw_text)]
        self.usergroup_ids = [
            match.groups()[0]
            for match in usergroups_pat.finditer(self.raw_text)
        ]
        self.here = bool(here_pat.search(self.raw_text))

        # Clean text
        self.text = users_pat.sub('', self.raw_text)
        self.text = usergroups_pat.sub('', self.text)
        self.text = here_pat.sub('', self.text)
        self.text = re.sub(r'\s+', ' ', self.text).strip()

    def resolve_usergroups(self):
        user_ids = set(self.user_ids)
        for i, usergroup_id in enumerate(self.usergroup_ids):
            user_ids |= set(get_usergroup(usergroup_id))
        self.user_ids = list(user_ids)

    def filter_out_inactive_users(self):
        self.user_ids = [user_id
                         for user_id in self.user_ids
                         if user_is_active(user_id)]

    def filter_out_users_not_in_channel(self):
        if self.here:
            self.user_ids = list(set(self.user_ids) |
                                 set(get_members(self.channel_id)))
        else:
            self.user_ids = list(set(self.user_ids) &
                                 set(get_members(self.channel_id)))

    def filter_out_requester(self):
        try:
            self.user_ids.remove(self.requester_id)
        except ValueError:
            pass

    @property
    def user_ids_left(self):
        return list(set(self.user_ids) - set(self.rejected_user_ids))

    def send_buttons(self):
        user_id = random.choice(self.user_ids_left)
        post_ephemeral(self.channel_id, user_id,
                       "<@{}>, <@{}> has asked you to:".
                       format(user_id, self.requester_id),
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
        post_channel(self.channel_id,
                     "<@{}> accepted <@{}>'s request to:".
                     format(user_id, self.requester_id),
                     [{'text': self.text}])

    def abort(self):
        post_ephemeral(self.channel_id, self.requester_id,
                       ("I'm sorry. It appears that everyone rejected your "
                        "request :cry:"),
                       [{'text': self.text}])
