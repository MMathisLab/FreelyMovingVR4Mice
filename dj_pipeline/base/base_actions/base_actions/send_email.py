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
    email,
    filename,
    message,
    path="/data/processeddata/summaryImgs",
    error=False,
    pipeline_name="ar_games",
):
    
    if email == "default":
        email =  fromaddr

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

    if error:
        subject = f"Sorry, the pipeline failed for Mouse: {filename.split('_')[1]}, Training performance on {filename.split('_')[2]} and {filename.split('_')[3].split('.')[0]}"
        body = message
    else:
        subject = f"Mouse: {filename.split('_')[1]}. Training Performance on {filename.split('_')[2]} {filename.split('_')[3].split('.')[0]}"
        body = f"Please find attached the {pipeline_name} summary report for the mouse {filename.split('_')[1]}. The training performance reported here is on {filename.split('_')[2]} and {filename.split('_')[3].split('.')[0]}"
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
