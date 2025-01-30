from rest_framework.permissions import BasePermission
from rest_framework.exceptions import AuthenticationFailed
from .authencation import JWTAuthentication


class IsValidUser(BasePermission):
    def has_permission(self, request, view):
        auth_header = request.META.get('HTTP_AUTHORIZATION')

        if not auth_header:
            raise AuthenticationFailed('Authorization header is missing.')

        try:
            # No splitting is needed; directly use the token
            token_str = auth_header # Directly take the token
            payload = JWTAuthentication.decode_jwt(token_str)
            user_id = payload.get('user_id')
            user = JWTAuthentication.validate_user(user_id)
            request.user = user
            return True
        except Exception as e:
            raise AuthenticationFailed(str(e))

        
class GetUserId(BasePermission):
    def get_user_id(request):
        return JWTAuthentication.get_user_id_from_request(request)
