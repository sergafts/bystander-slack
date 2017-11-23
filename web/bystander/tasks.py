from celery import Celery

from .bystander import Bystander, BystanderError
from .slack import post_ephemeral, SlackError

app = Celery('tasks', broker="redis://redis:6379/0")


@app.task
def start_bystander(raw_text, requester_id, channel_id):
    bystander = Bystander(raw_text, requester_id, channel_id)
    bystander.process_text()
    try:
        bystander.resolve_usergroups()
        bystander.filter_out_inactive_users()
    except SlackError as e:
        post_ephemeral(channel_id, requester_id,
                       ("Something went wrong while trying to contact the "
                        "Slack API, please try again later. Error was:"),
                       [{'text': str(e)}])
    bystander.filter_out_requester()

    if len(bystander.user_ids) < 2:
        post_ephemeral(channel_id, requester_id,
                       "You need to specify at least 2 users in your request")
        return

    bystander.save()
    bystander.send_buttons()


@app.task
def accept_bystander(id, user_id, channel_id, requester_id):
    try:
        bystander = Bystander.load(id)
    except BystanderError:
        post_ephemeral(channel_id, requester_id,
                       ("It looks like your request has timed out before "
                        "someone could accept it, please try again"))
        post_ephemeral(channel_id, user_id,
                       ("It looks like this request has timed out before "
                        "you could accept it"))
    else:
        bystander.accept(user_id)
        bystander.delete()


@app.task
def reject_bystander(id, user_id, channel_id, requester_id):
    try:
        bystander = Bystander.load(id)
    except BystanderError:
        post_ephemeral(channel_id, requester_id,
                       ("It looks like your request has timed out before "
                        "someone could accept it, please try again"))
        post_ephemeral(channel_id, user_id,
                       ("It looks like this request has timed out before "
                        "you could accept it"))
    bystander.reject(user_id)
    if bystander.user_ids_left:
        bystander.save()
        bystander.send_buttons()
    else:
        bystander.abort()
        bystander.delete()
