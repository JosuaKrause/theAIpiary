# Copyright (c) 2024 Josua Krause - All Rights Reserved
#
# THE CONTENTS OF THIS PROJECT ARE PROPRIETARY AND CONFIDENTIAL.
# UNAUTHORIZED COPYING, TRANSFERRING OR REPRODUCTION OF THE CONTENTS OF
# THIS PROJECT, VIA ANY MEDIUM IS STRICTLY PROHIBITED.
#
# The receipt or possession of the source code and/or any parts thereof does
# not convey or imply any right to use them for any purpose other than the
# purpose for which they were provided to you.
#
# The software is provided "AS IS", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose and non infringement. In no event shall the
# authors or copyright holders be liable for any claim, damages or other
# liability, whether in an action of contract, tort or otherwise, arising from,
# out of or in connection with the software or the use or other dealings in the
# software.
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the software.
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from scattermind.system.names import UName

from swai_server.env import envload_int, envload_str


def send_email(
        *,
        recipient_email: str,
        subject: str,
        message: str,
        ) -> None:
    own_email = envload_str("OWN_EMAIL", default="")
    smtp_host = envload_str("SMTP_HOST", default="")
    smtp_port = envload_int("SMTP_PORT", default=587)
    smtp_user = envload_str("SMTP_USER", default="")
    smtp_pw = envload_str("SMTP_PW", default="")
    if not own_email or not smtp_host or not smtp_user:
        print(
            f"NOT SENDING EMAIL to {recipient_email}:\n"
            f"{subject}\n\n{message}")
        return
    msg = MIMEMultipart()
    msg["From"] = own_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "text/html", "utf-8"))
    with smtplib.SMTP(smtp_host, smtp_port) as mailserver:
        mailserver.ehlo()
        mailserver.starttls()
        mailserver.ehlo()
        mailserver.login(smtp_user, smtp_pw)
        mailserver.sendmail(own_email, recipient_email, msg.as_string())
        mailserver.quit()


APP_NAME = "AIpiary"
CREATE_USER_SUBJECT = "[creator] Invites You to Join the [app]"
CREATE_USER_EMAIL = """
Dear [new],

[creator] invites you to join the [app], a unique swarm-based ML compute
engine. Here, you can contribute your computational power to create collective
intelligence, making advanced AI accessible to all. Even if you're not
contributing compute, you can still utilize the power of the swarm.

Please activate your account by clicking here.

If you need assistance, our support team is ready to help.

Best
"""


def send_create_user(new_user: UName, creator_name: str) -> None:
    pass
