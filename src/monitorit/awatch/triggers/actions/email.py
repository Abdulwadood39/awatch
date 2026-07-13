"""Compatibility shims for action modules."""

from monitorit.awatch.triggers.actions.base import LogAction, SendEmail, SlackNotify, Webhook

# individual module names used in plan
email = SendEmail
webhook = Webhook
slack = SlackNotify
log = LogAction
