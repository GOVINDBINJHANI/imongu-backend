from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from imongu_backend_app.Serializers import ContactSerializer
from rest_framework.exceptions import ValidationError
from django.db import DatabaseError

class ContactCreateView(APIView):
    def post(self, request):
        try:
            serializer = ContactSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    serializer.save()
                    return Response({
                        "message": "Contact created successfully!",
                        "url": "https://imongu.s3.amazonaws.com/A_Complete_Guide_to_Goal-Setting_for_C-Suite_Executives.pdf"
                    }, status=status.HTTP_201_CREATED)
                except DatabaseError as db_err:
                    return Response({
                        "error": "A database error occurred.",
                        "details": str(db_err)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as val_err:
            return Response({
                "error": "Validation failed.",
                "details": str(val_err)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "error": "An unexpected error occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



    