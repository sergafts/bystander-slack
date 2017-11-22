import random
import re

from flask import Flask, request, jsonify


app = Flask(__name__)


@app.route('/', methods=['POST'])
def main():
    users_pat = re.compile(r'<@[^>]+>')
    text = request.form.get('text', '')
    users = list(set(users_pat.findall(text)))
    if len(users) < 2:
        return jsonify({
            'text': "You need to mention at least two users in your message",
        })
    selected = random.choice(users)
    username = re.search(r'<@[^|]+\|([^>]+)>', selected).groups()[0]
    text = users_pat.sub('', text)
    text = re.sub(r'\s+', ' ', text)
    return jsonify({'response_type': "in_channel",
                    'text': "@{}, you're up".format(username),
                    'attachments': [{'text': text}]})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
