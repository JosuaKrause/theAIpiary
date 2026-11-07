# Copyright (C) 2024 Josua Krause
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TypedDict

from scattermind.system.names import UName

from swai_server.system.user.manager import (
    EmailChangeToken,
    ResetToken,
    UserInfo,
)


EmailConfig = TypedDict('EmailConfig', {
    "own_url": str,
    "own_email": str,
    "smtp_host": str,
    "smtp_port": int,
    "smtp_user": str,
    "smtp_pw": str,
})


def is_valid_email_config(email_config: EmailConfig) -> bool:
    if not email_config["own_url"]:
        return False
    if not email_config["own_email"]:
        return False
    if not email_config["smtp_host"]:
        return False
    if not email_config["smtp_user"]:
        return False
    return True


def send_email(
        config: EmailConfig,
        *,
        recipient_email: str,
        subject: str,
        message: str,
        ) -> None:
    if not is_valid_email_config(config):
        print(
            f"NOT SENDING EMAIL to {recipient_email}:\n"
            f"{subject}\n\n{message}")
        return
    own_email = config["own_email"]
    smtp_host = config["smtp_host"]
    smtp_port = config["smtp_port"]
    smtp_user = config["smtp_user"]
    smtp_pw = config["smtp_pw"]
    msg = MIMEMultipart()
    msg["From"] = own_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    html_message = format_email(
        EMAIL_BODY,
        {
            "email": message,
        })
    msg.attach(MIMEText(html_message, "html", "utf-8"))
    with smtplib.SMTP(smtp_host, smtp_port) as mailserver:
        mailserver.ehlo()
        mailserver.starttls()
        mailserver.ehlo()
        mailserver.login(smtp_user, smtp_pw)
        mailserver.sendmail(own_email, recipient_email, msg.as_string())
        mailserver.quit()


def format_email(text: str, replacements: dict[str, str]) -> str:
    orig_text = text
    for needle, replacement in replacements.items():
        text = text.replace(f"[{needle}]", replacement)
    start_ix = text.find("[")
    if start_ix >= 0:
        end_ix = text.find("]", start_ix)
        if end_ix >= 0:
            raise ValueError(
                f"unreplaced format {text[start_ix:end_ix + 1]} "
                f"in:\n{orig_text}")
    return text


APP_NAME = "AIpiary"


def app_str(config: EmailConfig) -> str:
    return f"<a href=\"{config['own_url']}#\">{APP_NAME}</a>"


EMAIL_BODY = """
<!DOCTYPE html>
<html lang="en">
<head></head>
<body>
[email]
</body>
</html>
"""


CREATE_USER_SUBJECT = "[creator_name] Invites You to Join the [app_name]"
CREATE_USER_EMAIL = """
<p>
Hello [new_name]!
</p>
<p>
[creator] invites you to join the [app], a unique swarm-based ML compute
engine. Here, you can contribute your computational power to create collective
intelligence, making advanced AI accessible to all. Even if you're not
contributing compute, you can still utilize the power of the swarm.
</p>
<p>
[login_text]
</p>
[discord]
<p>
Welcome,<br/>
The [app_name]!
</p>
"""


def reset_link(config: EmailConfig, reset_token: ResetToken) -> str:
    return f"{config['own_url']}/reset-password?token={reset_token}#"


def forget_link(config: EmailConfig) -> str:
    return f"{config['own_url']}/reset-password#"


FIRST_LOGIN_RESET_TOKEN = """
To log in for the first time, use the following link:
<a href="[reset_link]">[reset_link]</a><br/>
If clicking the link in the email doesn't work, try copying and pasting
it directly into the browser's address bar.<br/>
After 24 hours, the above link will expire.
In that case, use <a href="[forget_link]">[forget_link]</a>
to reset your password.
"""


FIRST_LOGIN_NO_TOKEN = """
To log in for the first time, use the following link and
enter your email to reset your password:
<a href="[forget_link]">[forget_link]</a>
"""


RESET_PASSWORD_SUBJECT = "The [app_name] - Password reset"
RESET_PASSWORD_EMAIL = """
<p>
Hello [user_name]!
</p>
<p>
We have received a request to reset your password for the [app].
Please click the link below to reset your password:
</p>
<p>
<a href="[reset_link]">[reset_link]</a>
</p>
<p>
This link will expire in 24 hours.
</p>
<p>
If you did not request a password reset, please ignore this email.
</p>
<p>
Best regards,<br/>
The [app_name]!
</p>
"""


def send_create_user(
        config: EmailConfig,
        *,
        new_email: UName,
        new_display: str,
        creator: UserInfo,
        reset_token: ResetToken | None,
        discord: str | None) -> None:
    creator_str = (
        f"<a href=\"mailto:{creator['email'].get()}\">"
        f"{creator['display_name']}</a>")
    if discord:
        discord_str = (
            f"<p>Also, join us on <a href=\"{discord}#\">Discord</a>!</p>")
    else:
        discord_str = ""
    if reset_token:
        login_text = format_email(
            FIRST_LOGIN_RESET_TOKEN,
            {
                "reset_link": reset_link(config, reset_token),
                "forget_link": forget_link(config),
            })
    else:
        login_text = format_email(
            FIRST_LOGIN_NO_TOKEN,
            {
                "forget_link": forget_link(config),
            })
    subject = format_email(
        CREATE_USER_SUBJECT,
        {
            "creator_name": creator["display_name"],
            "app_name": APP_NAME,
        })
    message = format_email(
        CREATE_USER_EMAIL,
        {
            "new_name": new_display,
            "creator": creator_str,
            "app": app_str(config),
            "app_name": APP_NAME,
            "login_text": login_text,
            "discord": discord_str,
        })
    send_email(
        config,
        recipient_email=new_email.get(),
        subject=subject,
        message=message)


def send_password_reset(
        config: EmailConfig,
        *,
        user: UserInfo,
        reset_token: ResetToken) -> None:
    subject = format_email(
        RESET_PASSWORD_SUBJECT,
        {
            "app_name": APP_NAME,
        })
    message = format_email(
        RESET_PASSWORD_EMAIL,
        {
            "user_name": user["display_name"],
            "reset_link": reset_link(config, reset_token),
            "app": app_str(config),
            "app_name": APP_NAME,
        })
    send_email(
        config,
        recipient_email=user["email"].get(),
        subject=subject,
        message=message)


def confirm_email_link(config: EmailConfig, token: EmailChangeToken) -> str:
    return f"{config['own_url']}/confirm-email?token={token}#"


def mailto_str(email: str, name: str) -> str:
    return (
        f"<a href=\"mailto:{html.escape(email)}\">{html.escape(name)}</a>")


def hours_str(seconds: float) -> str:
    hours = max(1, round(seconds / 3600.0))
    return f"{hours} hour{'' if hours == 1 else 's'}"


EMAIL_CHANGE_CONFIRM_SUBJECT = "The [app_name] - Confirm your new email"
EMAIL_CHANGE_CONFIRM_EMAIL = """
<p>
Hello [user_name]!
</p>
<p>
[requester] asked to change the email of your [app] account from
[old_email] to this address. To confirm the change, click the link below:
</p>
<p>
<a href="[confirm_link]">[confirm_link]</a>
</p>
<p>
Afterwards you log in with this address and your current password, and your
worker bees have to use this address as well. The link expires in [expires].
</p>
<p>
If you did not expect this email, ignore it: nothing changes without the
confirmation.
</p>
<p>
Best regards,<br/>
The [app_name]!
</p>
"""


EMAIL_CHANGE_NOTICE_SUBJECT = "The [app_name] - Email change requested"
EMAIL_CHANGE_NOTICE_EMAIL = """
<p>
Hello [user_name]!
</p>
<p>
[requester] asked to change the email of your [app] account from this
address to [new_email]. A confirmation link was sent there; the email changes
once the link is used.
</p>
<p>
If you do not want this change, contact [requester] before then.
</p>
<p>
Best regards,<br/>
The [app_name]!
</p>
"""


EMAIL_CHANGED_SUBJECT = "The [app_name] - Your email was changed"
EMAIL_CHANGED_EMAIL = """
<p>
Hello [user_name]!
</p>
<p>
The email of your [app] account was changed from this address to
[new_email]. You were logged out everywhere: log in with [new_email] and
your password from now on.
</p>
<p>
If you did not expect this, contact us at [contact].
</p>
<p>
Best regards,<br/>
The [app_name]!
</p>
"""


def send_email_change_confirm(
        config: EmailConfig,
        *,
        user: UserInfo,
        new_email: UName,
        requester: UserInfo,
        token: EmailChangeToken,
        expires_in: float) -> None:
    """
    Sends the confirmation link of a pending email change to the new address.

    Args:
        config (EmailConfig): The email configuration.
        user (UserInfo): The account (with its current email).
        new_email (UName): The new email.
        requester (UserInfo): Who asked for the change.
        token (EmailChangeToken): The token of the pending change.
        expires_in (float): How long the token is valid, in seconds.
    """
    subject = format_email(
        EMAIL_CHANGE_CONFIRM_SUBJECT,
        {
            "app_name": APP_NAME,
        })
    message = format_email(
        EMAIL_CHANGE_CONFIRM_EMAIL,
        {
            "user_name": html.escape(user["display_name"]),
            "requester": mailto_str(
                requester["email"].get(), requester["display_name"]),
            "old_email": html.escape(user["email"].get()),
            "confirm_link": confirm_email_link(config, token),
            "expires": hours_str(expires_in),
            "app": app_str(config),
            "app_name": APP_NAME,
        })
    send_email(
        config,
        recipient_email=new_email.get(),
        subject=subject,
        message=message)


def send_email_change_notice(
        config: EmailConfig,
        *,
        user: UserInfo,
        new_email: UName,
        requester: UserInfo) -> None:
    """
    Tells the current address of an account that a change of its email was
    requested and whom to contact to object.

    Args:
        config (EmailConfig): The email configuration.
        user (UserInfo): The account (with its current email).
        new_email (UName): The new email.
        requester (UserInfo): Who asked for the change.
    """
    subject = format_email(
        EMAIL_CHANGE_NOTICE_SUBJECT,
        {
            "app_name": APP_NAME,
        })
    message = format_email(
        EMAIL_CHANGE_NOTICE_EMAIL,
        {
            "user_name": html.escape(user["display_name"]),
            "requester": mailto_str(
                requester["email"].get(), requester["display_name"]),
            "new_email": html.escape(new_email.get()),
            "app": app_str(config),
            "app_name": APP_NAME,
        })
    send_email(
        config,
        recipient_email=user["email"].get(),
        subject=subject,
        message=message)


def send_email_changed(
        config: EmailConfig,
        *,
        user: UserInfo,
        old_email: UName) -> None:
    """
    Tells the former address of an account that its email was changed.

    Args:
        config (EmailConfig): The email configuration.
        user (UserInfo): The account (with its new email).
        old_email (UName): The former email.
    """
    subject = format_email(
        EMAIL_CHANGED_SUBJECT,
        {
            "app_name": APP_NAME,
        })
    message = format_email(
        EMAIL_CHANGED_EMAIL,
        {
            "user_name": html.escape(user["display_name"]),
            "new_email": html.escape(user["email"].get()),
            "contact": mailto_str(config["own_email"], config["own_email"]),
            "app": app_str(config),
            "app_name": APP_NAME,
        })
    send_email(
        config,
        recipient_email=old_email.get(),
        subject=subject,
        message=message)
