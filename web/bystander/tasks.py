import datetime

from celery import Celery
from celery.utils.log import get_task_logger

from .bystander import Bystander, BystanderError
from .conf import TIMEOUT_SECONDS


app = Celery('tasks', broker="redis://redis:6379/0")
logger = get_task_logger(__name__)


def eta():
    return (datetime.datetime.now() +
            datetime.timedelta(seconds=TIMEOUT_SECONDS))


@app.task(name="bystander:begin")
def begin(raw_text, requester_id, channel_id):
    b = Bystander(raw_text, requester_id, channel_id)
    b.figure_out_recipients()
    logger.info("Beginning bystander request, data is: %s", b.pprint())
    if len(b.possible_recipients) < 2:
        b.send_not_enough_recipients()
    else:
        b.ackgnowledge()
        b.save()  # needed to include id with the buttons message
        b.send_next()
        b.save()
        timeout.apply_async(args=(b.id, b.pending_user_id), eta=eta())


@app.task(name="bystander:timeout")
def timeout(id, pending_user_id):
    try:
        b = Bystander.load(id)
    except BystanderError:
        return  # abort
    if pending_user_id != b.pending_user_id:
        return  # abort
    b.timeout()
    b.figure_out_recipients()
    logger.info("Timeout for bystander request, data is '%s'", b.pprint())
    if len(b.possible_recipients) < 1:
        b.abort()
        b.delete()
    else:
        b.send_next()
        b.save()
        timeout.apply_async(args=(b.id, b.pending_user_id), eta=eta())


@app.task(name="bystander:accept")
def accept(id, user_id):
    b = Bystander.load(id)
    logger.info("Bystander request accepted, data is '%s', the user that "
                "accepted is '%s'", b.pprint(), user_id)
    b.accept(user_id)
    b.delete()


@app.task(name="bystander:reject")
def reject(id, user_id):
    b = Bystander.load(id)
    b.reject(user_id)
    logger.info("Bystander request rejected, data is '%s', the user that "
                "rejected is '%s'", b.pprint(), user_id)
    b.figure_out_recipients()
    if len(b.possible_recipients) < 1:
        b.abort()
        b.delete()
    else:
        b.send_next()
        b.save()
        timeout.apply_async(args=(b.id, b.pending_user_id), eta=eta())
