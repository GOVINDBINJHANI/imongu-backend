from django.conf import settings
import datetime , string , secrets
from urllib.parse import urlencode

def verify_email_token(verify_token,user):
    if user:
        # Extract the token and the encoded expiry timestamp
        token, encoded_expiry_timestamp = verify_token.split('-')
        # Convert the encoded expiry timestamp to a datetime object
        expiry_timestamp = float(encoded_expiry_timestamp)
        expiry_time = datetime.datetime.fromtimestamp(expiry_timestamp)
        # Check if the token has expired
        current_time = datetime.datetime.now()
        if current_time > expiry_time:
            # Token has expired
            # return "Reset token has expired"
            return None
        else:
            # Calculate the expiration time for the token (e.g., 24 hours from now)
            token_expiration = current_time - datetime.timedelta(hours=24)
            # Update the reset token with the new expiration time
            updated_token = f'{token}-{token_expiration.timestamp()}'
            user.verify_token = updated_token
            user.save()
            return user  # Assuming 'user_id' as the attribute name for the user ID
    else:
        # return "Invalid verify token"
        return None
    
def generate_varification_token_and_url(user_id):
    characters = string.ascii_letters + string.digits
    reset_token = ''.join(secrets.choice(characters) for _ in range(10))
    current_time = datetime.datetime.now()
    expiry_time = current_time + datetime.timedelta(minutes=1440)
    verify_token = f"{reset_token}-{expiry_time.timestamp()}"
    base_url = settings.VERIFY_EMAIL_URL_BASE
    query_params = {'verify_token': verify_token, 'user_id':user_id}
    verify_url = base_url + '?' + urlencode(query_params)
    return verify_token,verify_url
