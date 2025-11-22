import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import streamlit as st

# Load environment variables
load_dotenv()

def get_env_var(key: str) -> str:
    """Get environment variable from os.environ or st.secrets."""
    val = os.getenv(key)
    if val:
        return val
    if key in st.secrets:
        return st.secrets[key]
    return ""

def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Sends an HTML email to the specified recipient.
    Returns True if successful, False otherwise.
    """
    email_user = get_env_var("EMAIL_USER")
    email_pass = get_env_var("EMAIL_PASS")
    smtp_host = get_env_var("SMTP_HOST")
    smtp_port = get_env_var("SMTP_PORT")

    if not all([email_user, email_pass, smtp_host, smtp_port]):
        print("Missing email configuration.")
        return False

    msg = MIMEText(body, "html")
    msg['Subject'] = subject
    msg['From'] = email_user
    msg['To'] = to_email

    try:
        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            server.login(email_user, email_pass)
            server.sendmail(email_user, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

def send_amount_due_notification(member_name: str, member_email: str, amount: float, category: str, description: str = None) -> bool:
    """
    Sends a specific notification for a new amount due.
    """
    subject = "New amount due - Investia"
    
    desc_html = f"<p><strong>Description:</strong> {description}</p>" if description else ""
    
    body = f"""
    <p>Dear {member_name},</p>
    <p>You have an amount due of <strong>{amount:.2f}€</strong>.</p>
    <p><strong>Category:</strong> {category}</p>
    {desc_html}
    <p>Could you please settle this at your earliest convenience?</p>
    <p>If you believe this is a mistake, please contact the treasurer.</p>
    <p>Best regards,</p>
    <p>The Investia Team</p>
    """
    return send_email(member_email, subject, body)
