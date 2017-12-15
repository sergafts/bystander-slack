import json

from flask import Flask, request, jsonify, abort

from .conf import INCOMING_TOKEN
from .tasks import begin, accept, reject


app = Flask(__name__)


@app.route('/command', methods=['POST'])
def command():
    if request.form.get('token', None) != INCOMING_TOKEN:
        abort(401)

    try:
        raw_text = request.form['text']
        user_id = request.form['user_id']
        channel_id = request.form['channel_id']
    except KeyError:
        return jsonify({'response_type': "ephemeral",
                        'text': ("I'm sorry, your request appears to be "
                                 "malformed, please try again")})

    app.logger.info("Got request with raw_text: '%s', user_id: '%s', "
                    "channel_id: '%s'",
                    raw_text, user_id, channel_id)
    begin.delay(raw_text, user_id, channel_id)
    return ""


@app.route('/button', methods=['POST'])
def button():
    # Maybe key errors and stuff here, look out
    data = json.loads(request.form['payload'])

    if data['token'] != INCOMING_TOKEN:
        abort(401)

    id = data['callback_id']
    user_id = data['user']['id']

    if data['actions'][0]['name'] == "yes":
        accept.delay(id, user_id)
    else:
        reject.delay(id, user_id)

    return ""
