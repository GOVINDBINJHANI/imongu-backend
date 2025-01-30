
import jwt
from datetime import datetime, timedelta
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from imongu_backend_app.models import User



class JWTAuthentication:
    """
    Class for handling JWT creation, decoding, and user type checking.
    """

    @staticmethod
    def create_jwt(user_id, expires_in=60):
        """
        Create a JWT token for a user.
        Args:
            user_id (str): The user's ID.
            user_type (str): The type of user (e.g., 'admin', 'employee').
            expires_in (int): Token expiration time in hours. Default is 60 hours.
        Returns:
            str: Encoded JWT token.
        """
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expires_in),
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        # print(token)
        return token

    @staticmethod
    def decode_jwt(token):
        """
        Decode a JWT token and return the payload.
        Args:
            token (str): The JWT token to decode.
        Returns:
            dict: Decoded payload containing user information.
        Raises:
            AuthenticationFailed: If the token is invalid or expired.
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')


    @staticmethod
    def get_user_id_from_request(request):
        """
        Extract and return the user_id from the JWT token in the request.
        Args:
            request (Request): The DRF request object.
        Returns:
            str: The user_id extracted from the token.
        Raises:
            AuthenticationFailed: If the token is invalid or expired.
        """
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                # Directly use the token as there is no "Bearer" prefix
                token = auth_header
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                return payload.get('user_id')
            except jwt.ExpiredSignatureError:
                raise AuthenticationFailed('Token has expired')
            except jwt.InvalidTokenError:
                raise AuthenticationFailed('Invalid token')
        else:
            raise AuthenticationFailed('Authorization header not found')

    @staticmethod
    def validate_user(user_id):
        try:
            user = User.objects.get(user_id=int(user_id))
            return user
        except User.DoesNotExist as e:
            raise AuthenticationFailed('User not found')