# bystander-slack
Slack app to randomly assign something to a teammate

## Setting up your slack app

After you create your app [here](https://api.slack.com/apps?new_app=1) you must configure it.

1. Under "Interactive Components", assuming your web worker is reachable at `http://bot.host.com/`, set the Request URL to `http://bot.host.com/button`.
2. Under "Slash Commands" create a command with the Request URL set to `http://bot.host.com/command`. Make sure to select the "Escape channels" option.
3. Under "OAuth & Permissions" add the following required permission scopes, then press "Install App to Workspace"
    * Add commands to Transifex (`commands`)
    * Access information about user’s public channels (`channels:read`)
    * Send messages as bystander-kouk-test (`chat:write:bot`)
    * Access basic information about the workspace’s User Groups (`usergroups:read`)
    * Access your workspace’s profile information (`users:read`)

You then should copy your verification token from "Basic information" and your oauth
token from "OAuth & Permissions" to `web/bystander/conf_private.py` like this:

```
INCOMING_TOKEN = "..."
OUTGOING_TOKEN = "xoxp-X.."
```
