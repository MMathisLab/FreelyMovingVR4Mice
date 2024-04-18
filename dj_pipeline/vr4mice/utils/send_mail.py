import glob
import os
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from os.path import basename


def send_mail(send_from, send_to, subject, text, files, server, port, password):

    msg = MIMEMultipart()
    msg["From"] = send_from
    msg["To"] = COMMASPACE.join(send_to)
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject

    msg.attach(MIMEText(text))

    list_of_files = glob.glob(
        "/app/logs/*"
    )  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    # print(latest_file)
    # for f in files or []:
    f = latest_file

    with open(f, "rb") as fil:
        part = MIMEApplication(fil.read(), Name=basename(f))
        # After the file is closed
        part["Content-Disposition"] = 'attachment; filename="%s"' % basename(f)
        msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP(server, port) as smtp:
        smtp.login(send_from, password)
        smtp.starttls(context=context)
        smtp.sendmail(send_from, send_to, msg.as_string())


def auto_send(txt):
    port = 587  # For starttls
    smtp_server = "smtp.gmail.com"
    email = ""
    sender_email = email
    receiver_email = email
    password = ""
    message = "Maushaus update: " + txt

    subject = "MH LOGS"
    files = None
    # send_mail(sender_email, receiver_email, subject, message, files, smtp_server, port, password)

    msg = MIMEMultipart()
    msg.attach(MIMEText(message))

    list_of_files = glob.glob(
        "/app/logs/*"
    )  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)

    if "final" not in txt:
        f = latest_file

        with open(f, "rb") as fil:
            part = MIMEApplication(fil.read(), Name=basename(f))
            # After the file is closed
            part["Content-Disposition"] = 'attachment; filename="%s"' % basename(f)
            msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, port) as server:
        server.ehlo()  # Can be omitted
        server.starttls(context=context)
        server.ehlo()  # Can be omitted
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
