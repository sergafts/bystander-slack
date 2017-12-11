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
    """ Wrapper for the whole logic of the application.

        See tasks.py for the main interface.
    """

    USERS_PAT = re.compile(r'<@([^|]+)\|[^>]+>')
    USERGROUPS_PAT = re.compile(r'<!subteam\^([^|]+)\|@[^>]+>')

    def __init__(self, raw_text, requester_id, channel_id):
        self.requester_id = requester_id
        self.channel_id = channel_id

        # Users explicitly provided by bystander command
        self.user_ids = set((match.groups()[0]
                             for match in self.USERS_PAT.finditer(raw_text)))
        # Usergroups explicitly provided by bystander command
        self.usergroup_ids = set((
            match.groups()[0]
            for match in self.USERGROUPS_PAT.finditer(raw_text)
        ))
        # Clean text
        text = self.USERS_PAT.sub('', raw_text)
        text = self.USERGROUPS_PAT.sub('', text)
        self.text = re.sub(r'\s+', ' ', text).strip()

        (self.timed_out, self.rejected, self.pending_user_id,
         self.possible_recipients, self.id) = set(), set(), None, set(), None

    @classmethod
    def load(cls, id):
        data = REDIS.get(id)
        if data is None:
            raise BystanderError("Could not find the request in storage")
        try:
            data = json.loads(data)
        except Exception:
            raise BystanderError("Could not decode the request from storage")

        b = cls("", data['requester_id'], data['channel_id'])
        (b.user_ids, b.usergroup_ids, b.text, b.timed_out, b.rejected,
         b.pending_user_id, b.id) = (set(data['user_ids']),
                                     set(data['usergroup_ids']), data['text'],
                                     set(data['timed_out']),
                                     set(data['rejected']),
                                     data['pending_user_id'], id)

        return b

    def save(self):
        if self.id is None:
            self.id = str(uuid4())
        REDIS.set(
            self.id,
            json.dumps({'requester_id': self.requester_id,
                        'channel_id': self.channel_id,
                        'user_ids': list(self.user_ids),
                        'usergroup_ids': list(self.usergroup_ids),
                        'text': self.text,
                        'timed_out': list(self.timed_out),
                        'rejected': list(self.rejected),
                        'pending_user_id': self.pending_user_id}),
            ex=EXPIRE_SECONDS,
        )

    def delete(self):
        if self.id is None:
            raise BystanderError("Tried to delete a non-existing bystander "
                                 "instance")
        REDIS.delete(self.id)

    def pprint(self):
        return json.dumps({
            'requester_id': self.requester_id,
            'channel_id': self.channel_id,
            'user_ids': list(self.user_ids),
            'usergroup_ids': list(self.usergroup_ids),
            'text': self.text,
            'timed_out': list(self.timed_out),
            'rejected': list(self.rejected),
            'pending_user_id': self.pending_user_id,
            'id': self.id,
            'possible_recipients': list(self.possible_recipients),
        })

    def figure_out_recipients(self):
        all_candidates = self.user_ids

        # Resolve usergroups
        for usergroup_id in self.usergroup_ids:
            all_candidates |= set(get_usergroup(usergroup_id))

        # Filter out not in channel
        all_candidates &= set(get_members(self.channel_id))

        # Filter out requester
        all_candidates -= {self.requester_id}

        # Filter out inactive
        all_candidates = set((user_id
                              for user_id in all_candidates
                              if user_is_active(user_id)))

        self.possible_recipients = (all_candidates -
                                    self.timed_out -
                                    self.rejected)

    def ackgnowledge(self):
        post_ephemeral(self.channel_id, self.requester_id,
                       "Roger, will assign the task to a teammate",
                       [{'text': self.text}])

    def send_next(self):
        """ Send the message with the buttons to a randomly selected user in
            the request
        """

        self.pending_user_id = random.choice(list(self.possible_recipients))
        post_ephemeral(self.channel_id, self.pending_user_id,
                       "<@{}>, <@{}> has asked you to:".
                       format(self.pending_user_id, self.requester_id),
                       [{'text': self.text},
                        {'text': "Are you up for it:?",
                         "callback_id": self.id,
                         "attachment_type": "default",
                         "actions": [{'name': "yes", 'text': "Accept",
                                      'type': "button", 'value': "yes",
                                      'style': "primary"},
                                     {'name': "no", 'text': "Reject",
                                      'type': "button", 'value': "no",
                                      'style': "danger"}]}])

    def timeout(self):
        if not self.pending_user_id:
            raise BystanderError("Called timeout without a pending user")
        post_ephemeral(self.channel_id, self.pending_user_id,
                       "I'm sorry, you took too much time to respond and now "
                       "the request is timed out for you :cry:",
                       [{'text': self.text}])
        self.timed_out.add(self.pending_user_id)
        self.pending_user_id = None

    def send_not_enough_recipients(self):
        post_ephemeral(self.channel_id, self.requester_id,
                       "I'm sorry, I could not find at least two recipients "
                       "for your request :cry:",
                       [{'text': self.text}])

    def abort(self):
        attachments = [{'text': self.text}]
        if self.rejected:
            attachments.append({
                'text': "People that rejected: {}".format(
                    ", ".join(("<@{}>".format(user) for user in self.rejected))
                )
            })
        if self.timed_out:
            attachments.append({
                'text': "People that timed out: {}".format(
                    ", ".join(("<@{}>".format(user)
                               for user in self.timed_out))
                )
            })
        post_ephemeral(self.channel_id, self.requester_id,
                       "I'm sorry, I have to abort the bystander request; "
                       "there are not enough users left to send the request "
                       "to :cry:",
                       attachments)

    def accept(self, user_id):
        post_channel(self.channel_id,
                     "<@{}> accepted <@{}>'s request to:".
                     format(user_id, self.requester_id),
                     [{'text': self.text}])

    def reject(self, user_id):
        if not self.pending_user_id or user_id != self.pending_user_id:
            raise BystanderError("Reject called for wrong user")
        self.rejected.add(user_id)
        self.pending_user_id = None
