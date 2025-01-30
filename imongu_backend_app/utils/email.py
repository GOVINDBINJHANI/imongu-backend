import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from decouple import config

def send_email(subject, recipient, html_content, sender=""):

    if not sender:
        sender = config("FROM_EMAIL")
    message = MIMEMultipart()
    message.attach(MIMEText(html_content, "html"))
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient

    LOGIN_EMAIL = config("EMAIL_HOST_USER")
    LOGIN_PASSWORD = config("EMAIL_HOST_PASSWORD")

    print(LOGIN_EMAIL,LOGIN_PASSWORD)
    with smtplib.SMTP(config("EMAIL_HOST"), config("EMAIL_PORT")) as server:
        server.starttls()
        server.login(LOGIN_EMAIL, LOGIN_PASSWORD)
        server.send_message(message)


def send_invite_email(email, invite_url, user_name):
    subject = "Invitation to join our company"
    hyperlink_text = "Accept invite"
    custom_message_1 = "Hi! 👋,"
    custom_message_2 = f"{user_name} has invited you to join our company"
    custom_message_3 = f"Your email: {email}"
    custom_message_4 = """This invitation will expire in 24 hours, so please accept it before then! ⏳.
                        If you forget to accept the invitation, you can go to the login page and reset your password."""
    custom_message_5 = "😊 Thanks,"
    custom_message_6 = "Your iMongu team"
    
    # Create the HTML content with the custom message, hyperlink, and a line break
    html_content = f"""
    <html>
    <head></head>
    <body>
        <p>{custom_message_1}</p>
        <p>{custom_message_2}</p>
        <p>{custom_message_3}</p>
        <p><a href="{invite_url}">{hyperlink_text}</a></p>
        <p>{custom_message_4}</p>
        <p>{custom_message_5}<br>{custom_message_6}</p>
    </body>
    </html>
    """

    send_email(subject, email, html_content)


def send_verify_token_email(email, verify_url):
    subject = "Hi! Confirm Your Signup"
    hyperlink_text = "Click here to verify your account"
    custom_message_1 = "Hi! 👋,"
    custom_message_2 = "You are almost there! Please click the link below to verify your email address."
    custom_message_3 = (
        "If you didn’t ask to verify your email, you can ignore this email."
    )
    custom_message_4 = "😊  Thanks,"
    custom_message_5 = "Your iMongu team"
    # Create the HTML content with the custom message, hyperlink, and a line break
    html_content = f"""
    <html>
    <head></head>
    <body>
        <p>{custom_message_1}</p>
        <p>{custom_message_2}</p>
        <p><a href="{verify_url}">{hyperlink_text}</a></p>
        <p>{custom_message_3}</p>
        <p>{custom_message_4}<br>{custom_message_5}</p>
    </body>
    </html>
    """

    send_email(subject, email, html_content)


def send_enquiry_email(name, email, phone_number, company_name, content):
    subject = "Hi! Message from client."
    recipient = config("AGNESS_EMAIL")
    # Create a multipart message
    custom_message_1 = "Hi! 👋,"
    custom_message_2 = f"I am {name} from {company_name}."
    custom_message_3 = f"{content}"
    custom_message_4 = f"Contact Number : {phone_number}"
    custom_message_5 = f"Email : {email}"
    custom_message_6 = "Thanks 😊,"

    # Create the HTML content with the custom message, hyperlink, and a line break
    html_content = f"""
    <html>
    <head></head>
    <body>
        <p>{custom_message_1}</p>
        <p>{custom_message_2}</p>
        <p>{custom_message_3}</p>
        <p>{custom_message_4}<br>{company_name}<br>{custom_message_5}<br>{custom_message_6}</p>
    </body>
    </html>
    """

    send_email(subject, recipient, html_content, email)


def send_forget_ps_email(email, reset_password_url):
    subject = "Reset Your Password"
    hyperlink_text = "Reset Password"

    custom_message_1 = "Hi! 👋,"
    custom_message_2 = (
        "You are almost there! Please click the link below to reset your password."
    )
    custom_message_3 = "😊  Thanks,"
    custom_message_4 = "Your iMongu team"
    # Create the HTML content with the custom message, hyperlink, and a line break
    html_content = f"""
    <html>
    <head></head>
    <body>
        <p>{custom_message_1}</p>
        <p>{custom_message_2}</p>
        <p><a href="{reset_password_url}">{hyperlink_text}</a></p>
        <p>{custom_message_3}<br>{custom_message_4}</p>
    </body>
    </html>
    """

    send_email(subject, email, html_content)


def send_activation_email(email):
        subject = "Your Account Has Been Activated"
        hyperlink_text = "Your account has been activated successfully!"
        custom_message_1 = "Hi! 👋,"
        custom_message_2 = "We are happy to inform you that your account has been activated successfully."
        custom_message_3 = "You can now log in and access your account."
        custom_message_4 = "😊 Thanks,"
        custom_message_5 = "Your iMongu team"
        
        html_content = f"""
        <html>
        <head></head>
        <body>
            <p>{custom_message_1}</p>
            <p>{custom_message_2}</p>
            <p>{custom_message_3}</p>
            <p>{custom_message_4}<br>{custom_message_5}</p>
        </body>
        </html>
        """
        send_email(subject, email, html_content)

def send_reactivation_email(username, user_email, admin_email, reactivation_url):
    subject = "Account Reactivation Request"
    hyperlink_text = "Reactivate Account"

    custom_message_1 = f"Hi Admin, 👋"
    custom_message_2 = (
        f"The user '{username}' (Email: {user_email}) has requested to reactivate their account. "
        "Please click the link below to approve the request."
    )
    custom_message_3 = "If you didn’t ask to reactivate this account, you can ignore this email."
    custom_message_4 = "😊 Thanks,"
    custom_message_5 = "Your iMongu team"

    html_content = f"""
    <html>
    <head></head>
    <body>
        <p>{custom_message_1}</p>
        <p>{custom_message_2}</p>
        <p><a href="{reactivation_url}">{hyperlink_text}</a></p>
        <p>{custom_message_3}</p>
        <p>{custom_message_4}<br>{custom_message_5}</p>
    </body>
    </html>
    """

    send_email(subject, admin_email, html_content)
