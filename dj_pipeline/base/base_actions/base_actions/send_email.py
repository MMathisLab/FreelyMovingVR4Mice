import configparser
import os
import smtplib
import sys
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from base_actions.utils.logger import Logger

logger = Logger.get_logger()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

config = configparser.ConfigParser()
config.read("config.ini")  # Update password path if necessary


def email(
    key,
    email,
    filename,
    message,
    path="/data/processeddata/summaryImgs",
    error=False,
    pipeline_name="AR pipeline",
):

    if email == "default":
        email = fromaddr

    logger.info(f"Sending email to {email}, file {filename}")

    try:
        email_password = config.get("Email", "password")
        fromaddr = config.get("Email", "email")

    except configparser.NoSectionError:
        logger.warning("Error: section not found in config.ini")
        return

    toaddr = [fromaddr, email] if email and (email != fromaddr) else [fromaddr]
    msg = MIMEMultipart()
    msg["From"] = fromaddr
    msg["To"] = ", ".join(toaddr)

    text = msg.as_string()

    mouse = key["mouse_name"]
    day = key["day"]
    attempt = key["attempt"]
    if error:
        subject = f"{pipeline_name} pipeline failed for Mouse: {mouse}, Training performance on day {day} and attempt {attempt}."
        body = message
    else:
        subject = f"{pipeline_name}: Mouse: {mouse}. Training Performance on day {day}, attempt {attempt}."
        body = f"Please find attached the {pipeline_name} summary report for the mouse {mouse}. The training performance reported here is on {day} and attempt {attempt}"
        msg.attach(MIMEText(body, "plain"))

        try:
            # Construct the full path to the file
            file_path = os.path.join(path, filename)

            # Check if the file exists
            if os.path.exists(file_path):
                attachment = open(file_path, "rb")
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition", f"attachment; filename={filename}"
                )
                msg.attach(part)
            else:
                raise FileNotFoundError(f"File not found: {file_path}")

        except Exception as e:
            logger.warning(f"Error handling file: {e}")

    msg["Subject"] = subject

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(fromaddr, email_password)  # Use the password read from the config file
    text = msg.as_string()
    server.sendmail(fromaddr, toaddr, text)
    server.quit()

    logger.info(f"Email concerning {filename} sent to {toaddr}")
