import email, smtplib, ssl
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def zipfile(fldr) :
    os.system(f"7z a {fldr}.7z {fldr}")

## test data 
#subject = "An email with attachment from Python"
#body = "This is an email with attachment sent from Python"
#receiver_email = "venkateshks2304@gmail.com"
#attachments = "b.py"

sender_email = "210050164@iitb.ac.in"
password = "cdf2b956d1fc735b967d6fcfe0481ed7"

def send_mail(receiver_email,subject,body = "",attachments = []) : 
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    
    
    if type(attachments) == str : attachments = [attachments]
    for filename in attachments : 
        with open(filename, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {os.path.basename(filename)}",
        )
        message.attach(part)
    
    text = message.as_string()
    
    # Log in to server using secure context and send email
    context = ssl.create_default_context()
    context.set_ciphers("DEFAULT")
    
    with smtplib.SMTP("smtp-auth.iitb.ac.in", 587) as server:
        server.starttls(context=context)
        server.login(sender_email, password)
        print( server.sendmail(sender_email, receiver_email, text) )